"""Venue recommendation, format checks, and simulated review routes."""

import json
from pathlib import Path
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.agents.failure_checklist_agent import run_failure_checklist
from app.agents.review_agent import check_writing_quality, generate_cover_letter, generate_rebuttal, review_paper_simulation, score_rebuttal
from app.database import get_db
from app.database.sqlite import WritingProject
from app.llm.router import get_active_provider
from app.models import (
    CoverLetterRequest,
    FailureChecklistRequest,
    FailureChecklistResult,
    FormatCheckRequest,
    FormatCheckResult,
    RebuttalRequest,
    RebuttalScoreRequest,
    RebuttalScoreResponse,
    ReviewSimulateRequest,
    VenueRecommendRequest,
    VenueRecommendResponse,
    WritingQualityCheckRequest,
    WritingQualityCheckResult,
)
from app.services.format_service import check_format
from app.services.venue_service import recommend_venues

router = APIRouter()


async def _as_sse(events: AsyncIterator[dict]):
    async for event in events:
        yield {"data": json.dumps(event, ensure_ascii=False)}


@router.post("/review/recommend-venues", response_model=VenueRecommendResponse)
async def recommend_venues_endpoint(req: VenueRecommendRequest, db: Session = Depends(get_db)):
    """Recommend CS publication venues for a manuscript."""
    provider, config = get_active_provider(db)
    method_keywords = list(req.keywords)
    if req.method_description:
        method_keywords.append(req.method_description)
    venues = await recommend_venues(
        title=req.title,
        abstract=req.abstract,
        method_keywords=method_keywords,
        provider=provider,
        config=config,
    )
    return {"venues": venues}


@router.post("/review/check-format", response_model=FormatCheckResult)
async def check_format_endpoint(req: FormatCheckRequest, db: Session = Depends(get_db)):
    """Check a writing project's LaTeX source against venue rules."""
    project = db.query(WritingProject).filter(WritingProject.id == req.writing_project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Writing project not found")

    issues, total_pages = check_format(project.latex_project_path or "", req.target_venue)
    return {
        "passed": not any(issue["severity"] == "error" for issue in issues),
        "issues": issues,
        "total_pages_estimate": total_pages,
    }


@router.post("/review/simulate")
async def simulate_review(req: ReviewSimulateRequest, db: Session = Depends(get_db)):
    """Stream simulated peer-review cards and a meta-review."""
    provider, config = get_active_provider(db)
    return EventSourceResponse(
        _as_sse(review_paper_simulation(
            project_id=req.writing_project_id,
            venue=req.venue,
            reviewer_count=req.reviewer_count,
            db=db,
            provider=provider,
            config=config,
        ))
    )


@router.post("/review/generate-cover-letter")
async def generate_cover_letter_endpoint(req: CoverLetterRequest, db: Session = Depends(get_db)):
    """Generate an academic cover letter."""
    provider, config = get_active_provider(db)
    content = await generate_cover_letter(
        project_id=req.writing_project_id,
        venue=req.venue,
        editor_name=req.editor_name,
        additional_notes=req.additional_notes,
        db=db,
        provider=provider,
        config=config,
    )
    return {"content": content}


@router.post("/review/generate-rebuttal")
async def generate_rebuttal_endpoint(req: RebuttalRequest, db: Session = Depends(get_db)):
    """Generate a rebuttal letter from review text."""
    provider, config = get_active_provider(db)
    content = await generate_rebuttal(
        project_id=req.writing_project_id,
        review_text=req.review_text,
        response_style=req.response_style,
        db=db,
        provider=provider,
        config=config,
    )
    return {"content": content}


@router.post("/review/check-writing-quality", response_model=WritingQualityCheckResult)
async def check_writing_quality_endpoint(req: WritingQualityCheckRequest, db: Session = Depends(get_db)):
    """Check a writing project's text for AI-typical writing patterns."""
    provider, config = get_active_provider(db)

    if req.text.strip():
        text = req.text
    else:
        project = db.query(WritingProject).filter(WritingProject.id == req.writing_project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Writing project not found")
        if not project.latex_project_path:
            return WritingQualityCheckResult(flags=[], overall_rating="good", message="No LaTeX project path.")
        main_tex = Path(project.latex_project_path) / "main.tex"
        if not main_tex.exists():
            return WritingQualityCheckResult(flags=[], overall_rating="good", message="main.tex not found.")
        text = main_tex.read_text(encoding="utf-8", errors="ignore")

    result = await check_writing_quality(text, provider, config)
    return WritingQualityCheckResult(**result)


@router.post("/review/score-rebuttal", response_model=RebuttalScoreResponse)
async def score_rebuttal_endpoint(req: RebuttalScoreRequest, db: Session = Depends(get_db)):
    """Score author rebuttals against DA criticisms using the 1-5 scoring protocol."""
    provider, config = get_active_provider(db)

    criticisms = [{"id": c.id, "finding": c.finding, "severity": c.severity} for c in req.criticisms]
    rebuttals = [{"criticism_id": r.criticism_id, "response": r.response} for r in req.rebuttals]

    scored = await score_rebuttal(criticisms, rebuttals, provider, config)
    return RebuttalScoreResponse(scored=scored)


@router.post("/review/run-failure-checklist", response_model=FailureChecklistResult)
async def run_failure_checklist_endpoint(req: FailureChecklistRequest, db: Session = Depends(get_db)):
    """Run the 7-mode AI research failure checklist."""
    text = req.text.strip()
    if not text and req.writing_project_id:
        project = db.query(WritingProject).filter(WritingProject.id == req.writing_project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Writing project not found")
        main_tex = Path(project.latex_project_path or "") / "main.tex"
        if main_tex.exists():
            text = main_tex.read_text(encoding="utf-8", errors="ignore")

    if not text:
        raise HTTPException(status_code=400, detail="No text available for checklist")

    provider, config = get_active_provider(db)
    return await run_failure_checklist(text=text, provider=provider, config=config)
