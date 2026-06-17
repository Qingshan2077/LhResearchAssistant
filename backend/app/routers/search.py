"""搜索路由 — 检索论文 + 导入 + 综述生成"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.database import get_db
from app.database.sqlite import Paper, Project
from app.models import (
    SearchRequest, SearchResponse, ImportRequest, ImportResponse,
    ReviewRequest,
)
from app.services.search_service import search_papers, source_to_paper_dict
from app.agents.paper_agent import generate_review

router = APIRouter()


def _ensure_project(db: Session, project_id: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if project:
        return project

    project = Project(
        id=project_id,
        name="Default" if project_id == "default" else project_id,
        description="Auto-created project for imported papers.",
    )
    db.add(project)
    db.flush()
    return project


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
        "tags": paper.tags or [],
        "notes": paper.notes or "",
        "read_status": paper.read_status or "unread",
        "rating": paper.rating or 0,
        "is_new": is_new,
        "created_at": paper.created_at,
        "updated_at": paper.updated_at,
    }


@router.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest, db: Session = Depends(get_db)):
    """多源检索论文"""
    results, breakdown = await search_papers(
        query=req.query,
        sources=req.sources,
        max_results_per_source=req.max_results_per_source,
        year_from=req.year_from,
        year_to=req.year_to,
    )

    existing_arxiv = set()
    existing_doi = set()
    if req.project_id:
        papers_in_db = db.query(Paper).filter(Paper.project_id == req.project_id).all()
        for paper in papers_in_db:
            if paper.arxiv_id:
                existing_arxiv.add(paper.arxiv_id.lower())
            if paper.doi:
                existing_doi.add(paper.doi.lower())

    papers = []
    for r in results:
        p = source_to_paper_dict(r)
        p["is_new"] = not (
            (r.arxiv_id and r.arxiv_id.lower() in existing_arxiv)
            or (r.doi and r.doi.lower() in existing_doi)
        )
        papers.append(p)

    # 排序
    if req.sort_by == "citations":
        papers.sort(key=lambda p: p.get("citation_count", 0) or 0, reverse=True)
    elif req.sort_by == "date":
        papers.sort(key=lambda p: p.get("year", 0) or 0, reverse=True)
    # "relevance" — 保持原序（API 已按相关性排序）

    return SearchResponse(
        papers=papers,
        total_count=len(papers),
        source_breakdown=breakdown,
    )


@router.post("/search/import", response_model=ImportResponse)
async def import_papers(req: ImportRequest, db: Session = Depends(get_db)):
    """将完整检索结果导入本地知识库。"""
    _ensure_project(db, req.project_id)

    if not req.papers:
        raise HTTPException(
            status_code=400,
            detail="Please provide papers with full metadata. Temporary search paper_ids are not persistent.",
        )

    imported = 0
    skipped = 0
    papers = []

    for req_paper in req.papers:
        project_id = req_paper.project_id or req.project_id
        _ensure_project(db, project_id)
        existing = None

        if req_paper.arxiv_id:
            existing = (
                db.query(Paper)
                .filter(
                    Paper.project_id == project_id,
                    Paper.arxiv_id == req_paper.arxiv_id,
                )
                .first()
            )
        if not existing and req_paper.doi:
            existing = (
                db.query(Paper)
                .filter(
                    Paper.project_id == project_id,
                    Paper.doi == req_paper.doi,
                )
                .first()
            )

        if existing:
            skipped += 1
            papers.append(_paper_to_response(existing))
            continue

        paper = Paper(
            project_id=project_id,
            title=req_paper.title,
            authors=req_paper.authors,
            abstract=req_paper.abstract,
            year=req_paper.year,
            venue=req_paper.venue,
            paper_type=req_paper.paper_type,
            doi=req_paper.doi,
            arxiv_id=req_paper.arxiv_id,
            source=req_paper.source,
            citation_count=req_paper.citation_count,
            keywords=req_paper.keywords,
            url=req_paper.url,
            pdf_url=req_paper.pdf_url,
        )
        db.add(paper)
        db.flush()
        imported += 1
        papers.append(_paper_to_response(paper))

    db.commit()
    return ImportResponse(imported=imported, skipped=skipped, papers=papers)


@router.post("/search/generate-review")
async def generate_review_endpoint(req: ReviewRequest, db: Session = Depends(get_db)):
    """生成文献综述（SSE 流式返回）"""
    papers = db.query(Paper).filter(
        Paper.id.in_(req.paper_ids),
        Paper.project_id == req.project_id,
    ).all()

    if not papers:
        raise HTTPException(status_code=404, detail="No papers found for given IDs")

    return EventSourceResponse(
        generate_review(papers, focus=req.focus, language=req.language, db=db)
    )
