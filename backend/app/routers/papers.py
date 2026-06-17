"""论文管理路由 — CRUD + 上传 + 解析"""

import os
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from sse_starlette.sse import EventSourceResponse

from app.database import get_db
from app.database.sqlite import Paper, Project
from app.models import (
    PaperCreate, PaperUpdate, PaperResponse, PaperListResponse,
)
from app.config import settings
from app.services.pdf_parser import PDFParser
from app.services.pdf_download import download_pdf
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
