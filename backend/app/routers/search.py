"""搜索路由 — 检索论文 + 导入 + 综述生成"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.database import get_db
from app.database.sqlite import Paper, Project
from app.models import (
    SearchRequest, SearchResponse, ImportRequest, ImportResponse,
    PaperResponse, ReviewRequest,
)
from app.services.search_service import search_papers, source_to_paper_dict
from app.agents.paper_agent import generate_review

router = APIRouter()


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

    # 检查本地库中是否已存在
    existing_ids = set()
    if req.project_id:
        existing_ids = {
            row[0] for row in db.query(Paper.arxiv_id, Paper.doi).filter(
                Paper.project_id == req.project_id
            ).all()
        }

    papers = []
    for r in results:
        p = source_to_paper_dict(r)
        is_new = True
        if r.arxiv_id and r.arxiv_id in existing_ids:
            is_new = False
        if r.doi and r.doi in existing_ids:
            is_new = False
        p["is_new"] = is_new
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
    """将检索结果导入本地知识库"""
    project = db.query(Project).filter(Project.id == req.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    imported = 0
    skipped = 0
    papers = []

    # 检索结果通过 query 参数传入，这里简化：直接通过 paper_id 查找
    # 实际使用中，前端应在 search 后把完整 paper 对象传给后端
    # 这里提供一个兜底：如果 paper_id 是临时 id，返回错误
    raise HTTPException(
        status_code=400,
        detail="Please provide full paper data via POST /papers/batch for import. "
               "The search result temporary IDs are not persistent.",
    )


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
