"""Idea generation routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.agents.idea_agent import evaluate_feasibility, generate_ideas
from app.database import get_db
from app.llm.router import get_active_provider
from app.models import IdeaEvaluateRequest, IdeaRequest

router = APIRouter()


@router.post("/ideas/generate")
async def generate_ideas_endpoint(req: IdeaRequest, db: Session = Depends(get_db)):
    """生成研究 Idea（SSE 流式）。"""
    provider, config = get_active_provider(db)
    return EventSourceResponse(
        generate_ideas(
            paper_ids=req.paper_ids,
            mode=req.mode,
            db=db,
            provider=provider,
            config=config,
            custom_prompt=req.custom_prompt,
            domain_a=req.domain_a,
            domain_b=req.domain_b,
        )
    )


@router.post("/ideas/evaluate")
async def evaluate_idea(req: IdeaEvaluateRequest, db: Session = Depends(get_db)):
    """评估单个 Idea 可行性。"""
    provider, config = get_active_provider(db)
    return await evaluate_feasibility(
        idea=req.idea,
        context_paper_ids=req.context_paper_ids,
        db=db,
        provider=provider,
        config=config,
    )
