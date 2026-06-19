"""Idea generation routes."""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.agents.idea_agent import evaluate_feasibility, generate_ideas
from app.database import get_db
from app.llm.router import get_active_provider
from app.models import IdeaEvaluateRequest, IdeaRequest

router = APIRouter()


def _as_sse(event: dict) -> dict:
    """Wrap an application event as a valid server-sent event."""
    return {"data": json.dumps(event, ensure_ascii=False)}


async def _generate_ideas_sse(req: IdeaRequest, db: Session) -> AsyncIterator[dict]:
    """Adapt idea-agent events to the wire format expected by sse-starlette."""
    provider, config = get_active_provider(db)
    async for event in generate_ideas(
        paper_ids=req.paper_ids,
        mode=req.mode,
        db=db,
        provider=provider,
        config=config,
        custom_prompt=req.custom_prompt,
        domain_a=req.domain_a,
        domain_b=req.domain_b,
    ):
        yield _as_sse(event)


@router.post("/ideas/generate")
async def generate_ideas_endpoint(req: IdeaRequest, db: Session = Depends(get_db)):
    """Generate research ideas as an SSE stream."""
    return EventSourceResponse(_generate_ideas_sse(req, db))


@router.post("/ideas/evaluate")
async def evaluate_idea(req: IdeaEvaluateRequest, db: Session = Depends(get_db)):
    """Evaluate the feasibility of one research idea."""
    provider, config = get_active_provider(db)
    return await evaluate_feasibility(
        idea=req.idea,
        context_paper_ids=req.context_paper_ids,
        db=db,
        provider=provider,
        config=config,
    )
