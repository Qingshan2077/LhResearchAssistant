"""Idea generation routes."""

import json
import re
from datetime import datetime, timezone
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.agents.idea_agent import evaluate_feasibility, generate_ideas
from app.database import get_db
from app.database.sqlite import IdeaHistory, Project
from app.llm.router import get_active_provider
from app.models import IdeaEvaluateRequest, IdeaHistorySaveRequest, IdeaRequest

router = APIRouter()


def _as_sse(event: dict) -> dict:
    """Wrap an application event as a valid server-sent event."""
    return {"data": json.dumps(event, ensure_ascii=False)}


async def _generate_ideas_sse(req: IdeaRequest, db: Session) -> AsyncIterator[dict]:
    """Adapt idea-agent events to the wire format expected by sse-starlette."""
    provider, config = get_active_provider(db, function_name="idea")
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


def _ensure_project(db: Session, project_id: str | None) -> str | None:
    if not project_id:
        return None
    if db.get(Project, project_id) is None:
        db.add(Project(
            id=project_id,
            name="Default" if project_id == "default" else project_id,
            description="Auto-created project for idea history.",
        ))
        db.flush()
    return project_id


def _utc_isoformat(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def _idea_title(title: str, content: str) -> str:
    if title.strip():
        return title.strip()[:255]
    match = re.search(r"^#{1,3}\s+(.+)$", content, re.MULTILINE)
    return (match.group(1).strip() if match else "Generated Ideas")[:255]


def _history_payload(row: IdeaHistory, *, include_content: bool = False) -> dict:
    payload = {
        "id": row.id,
        "project_id": row.project_id,
        "title": row.title or "Generated Ideas",
        "created_at": _utc_isoformat(row.created_at),
        "mode": row.mode,
        "paper_ids": list(row.paper_ids or []),
        "custom_prompt": row.custom_prompt or "",
        "domain_a": row.domain_a or "",
        "domain_b": row.domain_b or "",
        "evaluations_count": len(row.evaluations or []),
    }
    if include_content:
        payload["generated_content"] = row.generated_content or ""
        payload["evaluations"] = list(row.evaluations or [])
    return payload


@router.post("/ideas/history/save")
def save_idea_history(req: IdeaHistorySaveRequest, db: Session = Depends(get_db)):
    if not req.generated_content.strip():
        raise HTTPException(status_code=400, detail="Generated content is required")
    row = IdeaHistory(
        project_id=_ensure_project(db, req.project_id),
        title=_idea_title(req.title, req.generated_content),
        mode=req.mode,
        paper_ids=list(req.paper_ids),
        custom_prompt=req.custom_prompt,
        domain_a=req.domain_a,
        domain_b=req.domain_b,
        generated_content=req.generated_content,
        evaluations=list(req.evaluations),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _history_payload(row, include_content=True)


@router.get("/ideas/history")
def list_idea_history(project_id: str | None = None, db: Session = Depends(get_db)):
    query = db.query(IdeaHistory)
    if project_id:
        query = query.filter(IdeaHistory.project_id == project_id)
    rows = query.order_by(IdeaHistory.created_at.desc()).limit(100).all()
    return [_history_payload(row) for row in rows]


@router.get("/ideas/history/{history_id}")
def get_idea_history(history_id: str, db: Session = Depends(get_db)):
    row = db.get(IdeaHistory, history_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Idea history not found")
    return _history_payload(row, include_content=True)


@router.delete("/ideas/history/{history_id}")
def delete_idea_history(history_id: str, db: Session = Depends(get_db)):
    row = db.get(IdeaHistory, history_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Idea history not found")
    db.delete(row)
    db.commit()
    return {"deleted": True}

@router.post("/ideas/generate")
async def generate_ideas_endpoint(req: IdeaRequest, db: Session = Depends(get_db)):
    """Generate research ideas as an SSE stream."""
    return EventSourceResponse(_generate_ideas_sse(req, db))


@router.post("/ideas/evaluate")
async def evaluate_idea(req: IdeaEvaluateRequest, db: Session = Depends(get_db)):
    """Evaluate the feasibility of one research idea."""
    provider, config = get_active_provider(db, function_name="idea")
    return await evaluate_feasibility(
        idea=req.idea,
        context_paper_ids=req.context_paper_ids,
        db=db,
        provider=provider,
        config=config,
    )
