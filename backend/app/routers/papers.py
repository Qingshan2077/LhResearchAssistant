"""论文管理路由 — CRUD + 上传 + 解析"""

import json
import os
import uuid
from pathlib import Path
from typing import AsyncIterator
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from sse_starlette.sse import EventSourceResponse

from app.database import SessionLocal, get_db
from app.database.chroma_client import collection
from app.database.sqlite import Paper, Project
from app.llm import ChatMessage, LLMConfig
from app.llm.router import get_active_provider
from app.models import (
    AskPapersRequest, ComparisonRequest, PaperCreate, PaperUpdate, PaperResponse, PaperListResponse,
)
from app.config import settings
from app.services.citation_graph import get_citation_graph as fetch_citation_graph
from app.services.comparison_matrix import generate_comparison_table
from app.services.pdf_parser import PDFParser
from app.services.pdf_download import download_pdf
from app.services.s2_client import search_paper_by_title
from app.agents.read_agent import parse_paper_structure

router = APIRouter()


def _ensure_project(db: Session, project_id: str | None) -> str | None:
    if not project_id:
        return None

    project = db.query(Project).filter(Project.id == project_id).first()
    if project:
        return project_id

    db.add(Project(
        id=project_id,
        name="Default" if project_id == "default" else project_id,
        description="Auto-created project for imported papers.",
    ))
    db.flush()
    return project_id


def _paper_to_response(paper: Paper, is_new: bool = False) -> dict:
    return {
        "id": paper.id,
        "project_id": paper.project_id,
        "title": paper.title,
        "authors": paper.authors or [],
        "abstract": paper.abstract or "",
        "year": paper.year,
        "venue": paper.venue or "",
        "paper_type": paper.paper_type or "",
        "doi": paper.doi or "",
        "arxiv_id": paper.arxiv_id or "",
        "source": paper.source or "",
        "citation_count": paper.citation_count or 0,
        "keywords": paper.keywords or [],
        "url": paper.url or "",
        "pdf_url": paper.pdf_url or "",
        "pdf_path": paper.pdf_path or "",
        "extracted_data": paper.extracted_data or {},
        "citation_verified": paper.citation_verified or [],
        "tags": paper.tags or [],
        "notes": paper.notes or "",
        "read_status": paper.read_status or "unread",
        "rating": paper.rating or 0,
        "is_new": is_new,
        "created_at": paper.created_at.isoformat() if paper.created_at else "",
        "updated_at": paper.updated_at.isoformat() if paper.updated_at else "",
    }


def _as_sse(event: dict) -> dict:
    return {"data": json.dumps(event, ensure_ascii=False)}


def _can_use_llm(config: LLMConfig | None) -> bool:
    if not config:
        return False
    base_url = (config.base_url or "").lower()
    return bool(config.api_key) or "localhost" in base_url or "127.0.0.1" in base_url


def _paper_brief(paper: Paper) -> dict:
    return {
        "id": paper.id,
        "title": paper.title,
        "year": paper.year,
        "venue": paper.venue,
        "abstract": paper.abstract,
    }


def _fallback_answer(papers: list[Paper], question: str) -> str:
    titles = ", ".join(f"[{paper.id}] {paper.title}" for paper in papers[:6])
    abstracts = "\n".join(
        f"- [{paper.id}] {(paper.abstract or 'No abstract available.')[:400]}"
        for paper in papers[:6]
    )
    return (
        "LLM is unavailable, so I can only provide source context.\n\n"
        f"Question: {question}\n\n"
        f"Selected papers: {titles or 'None'}\n\n"
        f"Available abstracts:\n{abstracts}"
    )


async def _ask_papers_stream(req: AskPapersRequest) -> AsyncIterator[dict]:
    db = SessionLocal()
    try:
        paper_ids = list(dict.fromkeys(req.paper_ids))
        papers = db.query(Paper).filter(Paper.id.in_(paper_ids)).all() if paper_ids else []
        yield _as_sse({"type": "status", "message": f"Loaded {len(papers)} papers."})

        if not papers:
            yield _as_sse({"type": "error", "message": "No papers found."})
            yield _as_sse({"type": "done"})
            return

        provider, config = get_active_provider(db)
        top_k = max(1, min(req.top_k, 20))
        chunks: list[str] = []
        try:
            results = collection.query(
                query_texts=[req.question],
                n_results=top_k * 3,
            )
            docs = results.get("documents", [[]])[0] or []
            metas = results.get("metadatas", [[]])[0] or []
            paper_id_set = set(paper_ids)
            for doc, meta in zip(docs, metas):
                if meta.get("paper_id") in paper_id_set:
                    chunks.append(f"[{meta.get('paper_id')}] {doc}")
                    if len(chunks) >= top_k:
                        break
        except Exception:
            yield _as_sse({"type": "status", "message": "Vector search unavailable; using abstracts only."})

        yield _as_sse({"type": "status", "message": f"Retrieved {len(chunks)} relevant passages."})

        if not provider or not _can_use_llm(config):
            yield _as_sse({"type": "chunk", "content": _fallback_answer(papers, req.question)})
            yield _as_sse({"type": "done"})
            return

        paper_context = "\n\n".join(
            f"[{paper.id}] {paper.title} ({paper.year or 'N/A'}) - {paper.venue or 'N/A'}"
            for paper in papers
        )
        chunks_text = "\n\n".join(chunks) if chunks else "No retrieved full-text chunks."
        abstracts_text = "\n\n".join(
            f"[{paper.id}] {paper.abstract or '(No abstract)'}" for paper in papers
        )
        prompt = f"""You are answering a research question based on multiple papers.

Question: {req.question}

Relevant papers:
{paper_context}

Relevant passages:
{chunks_text}

Paper abstracts:
{abstracts_text}

Instructions:
- Answer concisely based only on the provided sources.
- Cite source paper IDs in brackets like [paper_id] for each concrete claim.
- If sources disagree, mention the disagreement.
- If the sources are insufficient, say so clearly.
"""
        try:
            async for token in provider.chat_stream(
                [
                    ChatMessage(role="system", content="You synthesize answers across research papers."),
                    ChatMessage(role="user", content=prompt),
                ],
                config,
            ):
                yield _as_sse({"type": "chunk", "content": token})
        except Exception as exc:
            yield _as_sse({"type": "error", "message": str(exc)})
        yield _as_sse({"type": "done"})
    finally:
        db.close()


def _normalize_key(value: str | None) -> str:
    return " ".join((value or "").lower().split())


def _match_local_paper(node: dict, papers: list[Paper]) -> Paper | None:
    external_ids = node.get("external_ids") or {}
    node_doi = _normalize_key(external_ids.get("DOI"))
    node_arxiv = _normalize_key(external_ids.get("ArXiv"))
    node_title = _normalize_key(node.get("title") or node.get("label"))

    for paper in papers:
        if node_doi and _normalize_key(paper.doi) == node_doi:
            return paper
        if node_arxiv and _normalize_key(paper.arxiv_id) == node_arxiv:
            return paper
        if node_title and _normalize_key(paper.title) == node_title:
            return paper
    return None


def _merge_local_graph_data(graph: dict, local_papers: list[Paper]) -> dict:
    for node in graph.get("graph", {}).get("nodes", []):
        match = _match_local_paper(node, local_papers)
        if not match:
            continue
        node["local_id"] = match.id
        node["tags"] = match.tags or []
        node["notes"] = match.notes or ""
        node["read_status"] = match.read_status or "unread"
    return graph


async def _resolve_s2_identifier(paper: Paper) -> str | None:
    extracted = paper.extracted_data if isinstance(paper.extracted_data, dict) else {}
    s2_id = (
        extracted.get("s2_paper_id")
        or extracted.get("paperId")
        or extracted.get("semantic_scholar_id")
    )
    if s2_id:
        return str(s2_id)
    if paper.doi:
        return f"DOI:{paper.doi}"
    if paper.arxiv_id:
        return f"ARXIV:{paper.arxiv_id}"

    result = await search_paper_by_title(paper.title)
    if result and result.get("paperId"):
        return str(result["paperId"])
    return None


@router.get("/papers", response_model=PaperListResponse)
def list_papers(
    project_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "date",
    sort_order: str = "desc",
    search: str = "",
    read_status: str = "",
    db: Session = Depends(get_db),
):
    """论文列表（分页 + 过滤 + 排序）"""
    query = db.query(Paper)

    if project_id:
        query = query.filter(Paper.project_id == project_id)
    if search:
        query = query.filter(Paper.title.contains(search))
    if read_status:
        query = query.filter(Paper.read_status == read_status)

    # 排序
    if sort_by == "date":
        order_col = Paper.created_at
    elif sort_by == "citations":
        order_col = Paper.citation_count
    elif sort_by == "year":
        order_col = Paper.year
    else:
        order_col = Paper.created_at

    if sort_order == "asc":
        query = query.order_by(order_col.asc())
    else:
        query = query.order_by(order_col.desc())

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return PaperListResponse(
        items=[_paper_to_response(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/papers/ask")
async def ask_papers(req: AskPapersRequest):
    """Stream a synthesized answer across selected papers."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question is required")
    if not req.paper_ids:
        raise HTTPException(status_code=400, detail="paper_ids is required")
    return EventSourceResponse(_ask_papers_stream(req))


@router.post("/papers/compare")
async def compare_papers(req: ComparisonRequest, db: Session = Depends(get_db)):
    """Generate a structured comparison table for selected papers."""
    if len(req.paper_ids) < 2:
        raise HTTPException(status_code=400, detail="Select at least two papers")

    paper_ids = list(dict.fromkeys(req.paper_ids))
    papers = db.query(Paper).filter(Paper.id.in_(paper_ids)).all()
    paper_by_id = {paper.id: paper for paper in papers}
    ordered = [paper_by_id[paper_id] for paper_id in paper_ids if paper_id in paper_by_id]
    if not ordered:
        raise HTTPException(status_code=404, detail="No papers found")

    provider, config = get_active_provider(db)
    return await generate_comparison_table(
        [_paper_brief(paper) for paper in ordered],
        req.dimensions,
        provider,
        config,
    )


@router.get("/papers/{paper_id}/citation-graph")
async def get_citation_graph_endpoint(paper_id: str, db: Session = Depends(get_db)):
    """Fetch citation graph data from Semantic Scholar and mark local matches."""
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    s2_id = await _resolve_s2_identifier(paper)
    if not s2_id:
        return {"error": "Cannot determine Semantic Scholar ID for this paper."}

    try:
        graph = await fetch_citation_graph(s2_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Semantic Scholar request failed: {exc}") from exc

    if graph.get("error"):
        return graph

    graph = _merge_local_graph_data(graph, db.query(Paper).all())
    for node in graph.get("graph", {}).get("nodes", []):
        if node.get("is_seed"):
            node["local_id"] = paper.id
    return graph


@router.get("/papers/{paper_id}")
def get_paper(paper_id: str, db: Session = Depends(get_db)):
    """论文详情"""
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return _paper_to_response(paper)


@router.post("/papers")
def create_paper(req: PaperCreate, db: Session = Depends(get_db)):
    """手动创建论文"""
    project_id = _ensure_project(db, req.project_id)
    paper = Paper(
        project_id=project_id,
        title=req.title,
        authors=req.authors,
        abstract=req.abstract,
        year=req.year,
        venue=req.venue,
        paper_type=req.paper_type,
        doi=req.doi,
        arxiv_id=req.arxiv_id,
        source=req.source,
        citation_count=req.citation_count,
        keywords=req.keywords,
        url=req.url,
        pdf_url=req.pdf_url,
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)
    return _paper_to_response(paper)


@router.post("/papers/batch")
async def batch_create_papers(papers: list[PaperCreate], db: Session = Depends(get_db)):
    """批量导入论文（从检索结果导入时使用），自动下载 PDF。"""
    created = []
    imported = 0
    skipped = 0

    for req in papers:
        project_id = _ensure_project(db, req.project_id)

        # 检查是否已存在（通过 arxiv_id 或 doi）
        existing = None
        if req.arxiv_id:
            existing = (
                db.query(Paper)
                .filter(Paper.project_id == project_id, Paper.arxiv_id == req.arxiv_id)
                .first()
            )
        if not existing and req.doi:
            existing = (
                db.query(Paper)
                .filter(Paper.project_id == project_id, Paper.doi == req.doi)
                .first()
            )
        if existing:
            created.append(_paper_to_response(existing))
            skipped += 1
            continue

        paper = Paper(
            project_id=project_id,
            title=req.title,
            authors=req.authors,
            abstract=req.abstract,
            year=req.year,
            venue=req.venue,
            paper_type=req.paper_type,
            doi=req.doi,
            arxiv_id=req.arxiv_id,
            source=req.source,
            citation_count=req.citation_count,
            keywords=req.keywords,
            url=req.url,
            pdf_url=req.pdf_url,
        )
        db.add(paper)
        db.flush()

        # 自动下载 PDF
        if req.pdf_url and not paper.pdf_path:
            local_path = await download_pdf(req.pdf_url, req.title)
            if local_path:
                paper.pdf_path = local_path
                db.flush()

        created.append(_paper_to_response(paper))
        imported += 1

    db.commit()
    return {"imported": imported, "skipped": skipped, "papers": created}


@router.patch("/papers/{paper_id}")
def update_paper(paper_id: str, req: PaperUpdate, db: Session = Depends(get_db)):
    """更新论文（标签、笔记、阅读状态等）"""
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    if req.tags is not None:
        paper.tags = req.tags
    if req.notes is not None:
        paper.notes = req.notes
    if req.read_status is not None:
        paper.read_status = req.read_status
    if req.rating is not None:
        paper.rating = req.rating

    db.commit()
    db.refresh(paper)
    return _paper_to_response(paper)


@router.delete("/papers/{paper_id}")
def delete_paper(paper_id: str, db: Session = Depends(get_db)):
    """删除论文"""
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    db.delete(paper)
    db.commit()
    return {"deleted": True}


@router.post("/papers/upload")
async def upload_paper(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    db: Session = Depends(get_db),
):
    """上传 PDF 文件，提取元数据并创建论文记录"""
    project_id = _ensure_project(db, project_id or "default") or "default"

    # 保存文件
    cache_dir = Path(settings.papers_cache_dir)
    file_ext = Path(file.filename).suffix if file.filename else ".pdf"
    saved_name = f"{uuid.uuid4()}{file_ext}"
    saved_path = cache_dir / saved_name

    content = await file.read()
    with open(saved_path, "wb") as f:
        f.write(content)

    # 提取元数据
    try:
        meta = PDFParser.extract_metadata(str(saved_path))
        title = meta.get("title") or file.filename or "Untitled"
        author = meta.get("author") or ""
    except Exception:
        title = file.filename or "Untitled"
        author = ""

    # 创建论文记录
    paper = Paper(
        project_id=project_id,
        title=title,
        authors=[author] if author else [],
        source="manual",
        pdf_path=str(saved_path),
        read_status="unread",
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)

    return _paper_to_response(paper)


@router.post("/papers/{paper_id}/parse")
async def parse_paper(paper_id: str, db: Session = Depends(get_db)):
    """解析论文 PDF，用 LLM 提取结构化信息（SSE 流式）"""
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    if not paper.pdf_path or not Path(paper.pdf_path).exists():
        raise HTTPException(status_code=400, detail="PDF file not found")

    return EventSourceResponse(parse_paper_structure(paper, db))


@router.get("/papers/{paper_id}/pdf")
async def get_paper_pdf(paper_id: str, db: Session = Depends(get_db)):
    """返回论文 PDF 文件流。"""
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper or not paper.pdf_path:
        raise HTTPException(status_code=404, detail="PDF file not found")

    pdf_path = Path(paper.pdf_path)
    if not pdf_path.exists() or not pdf_path.is_file():
        raise HTTPException(status_code=404, detail="PDF file not found")

    return FileResponse(pdf_path, media_type="application/pdf", filename=pdf_path.name)


@router.post("/papers/{paper_id}/download-pdf")
async def download_paper_pdf(paper_id: str, db: Session = Depends(get_db)):
    """从外部 URL 下载 PDF 到本地缓存。"""
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    if paper.pdf_path and Path(paper.pdf_path).exists():
        return {"status": "exists", "pdf_path": paper.pdf_path}

    if not paper.pdf_url:
        raise HTTPException(status_code=400, detail="No PDF URL available for this paper")

    local_path = await download_pdf(paper.pdf_url, paper.title)
    if not local_path:
        raise HTTPException(status_code=502, detail="Failed to download PDF from source")

    paper.pdf_path = local_path
    db.commit()
    return {"status": "downloaded", "pdf_path": local_path}


@router.post("/papers/{paper_id}/relations")
async def discover_relations(paper_id: str, db: Session = Depends(get_db)):
    """发现当前论文与知识库中其他论文的关系"""
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    # Phase 1 占位：返回空关系列表（Phase 2 实现完整的关系发现）
    return {"relations": []}
