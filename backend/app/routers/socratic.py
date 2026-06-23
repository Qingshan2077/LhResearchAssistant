"""Socratic mentor routes."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from loguru import logger
from sqlalchemy.orm import Session

from app.agents.socratic_agent import (
    create_session,
    generate_methodology_blueprint,
    generate_research_question,
    generate_summary,
    handle_message,
    load_from_db,
    run_devils_advocate,
    save_to_db,
    session_history_payload,
    sessions,
)
from app.database import SessionLocal, get_db
from app.database.sqlite import (
    SocraticInsight as SocraticInsightModel,
    SocraticMessage as SocraticMessageModel,
    SocraticSession as SocraticSessionModel,
)
from app.llm.router import get_active_provider
from app.models import CreateSocraticRequest, SocraticSaveRequest

router = APIRouter()


@router.post("/ideas/socratic/create")
async def create_socratic_session(req: CreateSocraticRequest, db: Session = Depends(get_db)):
    provider, config = get_active_provider(db, function_name="socratic")
    session_id = await create_session(req.project_id, provider, config, initial_message=req.initial_message)
    return {"session_id": session_id}


def _utc_isoformat(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


@router.post("/ideas/socratic/{session_id}/save")
def save_socratic_session(
    session_id: str,
    req: SocraticSaveRequest,
    db: Session = Depends(get_db),
):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Socratic session not found")
    record = save_to_db(session_id, db, end_session=req.end_session)
    payload = {
        "id": record.id,
        "title": record.title or "",
        "updated_at": _utc_isoformat(record.updated_at),
    }
    if req.release_session:
        sessions.pop(session_id, None)
    return payload


@router.get("/ideas/socratic/history")
def list_socratic_history(
    project_id: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(SocraticSessionModel)
    if project_id:
        query = query.filter(SocraticSessionModel.project_id == project_id)
    rows = query.order_by(SocraticSessionModel.updated_at.desc()).limit(100).all()
    return [
        {
            "id": row.id,
            "title": row.title or "Socratic Session",
            "turn_count": row.turn_count or 0,
            "message_count": db.query(SocraticMessageModel).filter(SocraticMessageModel.session_id == row.id).count(),
            "layer": row.layer or 1,
            "insights_count": len(row.insights_list or []),
            "has_summary": bool(row.summary_json),
            "created_at": _utc_isoformat(row.created_at),
            "updated_at": _utc_isoformat(row.updated_at),
        }
        for row in rows
    ]


@router.get("/ideas/socratic/history/{session_id}")
def get_socratic_history(session_id: str, db: Session = Depends(get_db)):
    session = load_from_db(session_id, db)
    if session is None:
        raise HTTPException(status_code=404, detail="Socratic history not found")
    return session_history_payload(session)


@router.delete("/ideas/socratic/history/{session_id}")
def delete_socratic_history(session_id: str, db: Session = Depends(get_db)):
    record = db.get(SocraticSessionModel, session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Socratic history not found")
    db.query(SocraticMessageModel).filter(SocraticMessageModel.session_id == session_id).delete(synchronize_session=False)
    db.query(SocraticInsightModel).filter(SocraticInsightModel.session_id == session_id).delete(synchronize_session=False)
    db.delete(record)
    db.commit()
    sessions.pop(session_id, None)
    return {"deleted": True}

@router.get("/ideas/socratic/{session_id}/summary")
async def get_socratic_summary(session_id: str, db: Session = Depends(get_db)):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Socratic session not found")
    provider, config = get_active_provider(db, function_name="socratic")
    summary = await generate_summary(session_id, provider, config)
    save_to_db(session_id, db)
    return summary


@router.get("/ideas/socratic/{session_id}/research-question")
async def get_research_question(session_id: str, db: Session = Depends(get_db)):
    """Generate a FINER-scored research question from the Socratic dialogue."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Socratic session not found")
    provider, config = get_active_provider(db, function_name="socratic")
    return await generate_research_question(session_id, provider, config)


@router.post("/ideas/socratic/methodology")
async def get_methodology_blueprint(rq: str = "", context: str = "", db: Session = Depends(get_db)):
    """Generate a methodology blueprint from a research question."""
    provider, config = get_active_provider(db, function_name="socratic")
    return await generate_methodology_blueprint(rq=rq, context=context, provider=provider, config=config)


@router.post("/ideas/socratic/devils-advocate")
async def get_devils_advocate(rq: str = "", methodology: str = "", db: Session = Depends(get_db)):
    """Run a Devil's Advocate stress-test on a research plan."""
    provider, config = get_active_provider(db, function_name="socratic")
    return await run_devils_advocate(rq=rq, methodology=methodology, provider=provider, config=config)


@router.websocket("/ideas/socratic/{session_id}")
async def socratic_chat(websocket: WebSocket, session_id: str):
    await websocket.accept()
    if session_id not in sessions:
        await websocket.send_json({"type": "error", "content": "Socratic session not found"})
        await websocket.close()
        return

    db = SessionLocal()
    try:
        provider, config = get_active_provider(db, function_name="socratic")
        await websocket.send_json({
            "type": "ready",
            "content": "Socratic Mentor 已连接。先告诉我你现在的研究想法或困惑。",
            "layer": sessions[session_id].layer,
            "insights": sessions[session_id].insights,
            "convergence": sessions[session_id].convergence,
            "turn_count": sessions[session_id].turn_count,
            "is_active": sessions[session_id].is_active,
        })
        while True:
            payload = await websocket.receive_json()
            message = str(payload.get("message", "")).strip()
            if not message:
                await websocket.send_json({"type": "error", "content": "Empty message"})
                continue

            result = await handle_message(session_id, message, provider, config)
            await websocket.send_json(result)

            if result.get("type") == "converged":
                save_to_db(session_id, db, end_session=True)
                await websocket.close()
                return
    except WebSocketDisconnect:
        pass
    finally:
        if session_id in sessions:
            try:
                save_to_db(session_id, db)
            except Exception as exc:
                logger.warning("Could not persist Socratic session {}: {}", session_id, exc)
                db.rollback()
        db.close()
