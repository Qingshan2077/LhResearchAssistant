"""Socratic mentor routes."""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.agents.socratic_agent import create_session, generate_methodology_blueprint, generate_research_question, generate_summary, handle_message, run_devils_advocate, sessions
from app.database import SessionLocal, get_db
from app.llm.router import get_active_provider
from app.models import CreateSocraticRequest

router = APIRouter()


@router.post("/ideas/socratic/create")
async def create_socratic_session(req: CreateSocraticRequest, db: Session = Depends(get_db)):
    provider, config = get_active_provider(db)
    session_id = await create_session(req.project_id, provider, config, initial_message=req.initial_message)
    return {"session_id": session_id}


@router.get("/ideas/socratic/{session_id}/summary")
async def get_socratic_summary(session_id: str, db: Session = Depends(get_db)):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Socratic session not found")
    provider, config = get_active_provider(db)
    return await generate_summary(session_id, provider, config)


@router.get("/ideas/socratic/{session_id}/research-question")
async def get_research_question(session_id: str, db: Session = Depends(get_db)):
    """Generate a FINER-scored research question from the Socratic dialogue."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Socratic session not found")
    provider, config = get_active_provider(db)
    return await generate_research_question(session_id, provider, config)


@router.post("/ideas/socratic/methodology")
async def get_methodology_blueprint(rq: str = "", context: str = "", db: Session = Depends(get_db)):
    """Generate a methodology blueprint from a research question."""
    provider, config = get_active_provider(db)
    return await generate_methodology_blueprint(rq=rq, context=context, provider=provider, config=config)


@router.post("/ideas/socratic/devils-advocate")
async def get_devils_advocate(rq: str = "", methodology: str = "", db: Session = Depends(get_db)):
    """Run a Devil's Advocate stress-test on a research plan."""
    provider, config = get_active_provider(db)
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
        provider, config = get_active_provider(db)
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
                await websocket.close()
                return
    except WebSocketDisconnect:
        pass
    finally:
        db.close()
