"""Citation verification routes backed by Semantic Scholar."""

import json
import re
from pathlib import Path
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.database import get_db, SessionLocal
from app.database.sqlite import Paper
from app.models import CitationVerificationStatus
from app.services.pdf_parser import PDFParser
from app.services.s2_client import search_paper_by_title

router = APIRouter()


def _as_sse(event: dict) -> dict:
    return {"data": json.dumps(event, ensure_ascii=False)}


def _extract_text_for_citations(paper: Paper) -> str:
    extracted = paper.extracted_data or {}
    chunks = [
        paper.title or "",
        paper.abstract or "",
        paper.notes or "",
        json.dumps(extracted, ensure_ascii=False),
    ]
    if paper.pdf_path and Path(paper.pdf_path).exists():
        try:
            chunks.append(PDFParser.extract_text_fast(paper.pdf_path))
        except Exception:
            pass
    return "\n".join(chunks)


def _extract_citations(text: str) -> list[str]:
    citations: list[str] = []

    for cite_match in re.finditer(r"\\cite\w*\{([^}]+)\}", text):
        for key in cite_match.group(1).split(","):
            cleaned = key.strip()
            if cleaned:
                citations.append(cleaned)

    for title_match in re.finditer(r"title\s*=\s*[\{\"]([^}\"]{8,220})[\}\"]", text, re.IGNORECASE):
        citations.append(title_match.group(1).strip())

    references_match = re.search(r"(?:references|bibliography)\s*\n(?P<body>.+)$", text, re.IGNORECASE | re.DOTALL)
    if references_match:
        for line in references_match.group("body").splitlines()[:80]:
            line = re.sub(r"^\s*(?:\[\d+\]|\d+\.|-)\s*", "", line).strip()
            if len(line) < 20:
                continue
            quoted = re.search(r"[\"“](.{8,180})[\"”]", line)
            if quoted:
                citations.append(quoted.group(1).strip())
                continue
            sentence = re.split(r"\.\s+", line)
            if sentence:
                candidate = sentence[0].strip()
                if 20 <= len(candidate) <= 180:
                    citations.append(candidate)

    seen: set[str] = set()
    unique: list[str] = []
    for citation in citations:
        normalized = re.sub(r"\s+", " ", citation).strip(" .;:,")
        key = normalized.lower()
        if len(normalized) > 5 and key not in seen:
            seen.add(key)
            unique.append(normalized)
    return unique[:80]


def _summarize(citations: list[dict]) -> dict:
    return {
        "total": len(citations),
        "verified": sum(1 for item in citations if item.get("status") == "verified"),
        "not_found": sum(1 for item in citations if item.get("status") == "not_found"),
        "ambiguous": sum(1 for item in citations if item.get("status") == "ambiguous"),
        "citations": citations,
    }


async def _verify_stream(paper_id: str) -> AsyncIterator[dict]:
    db = SessionLocal()
    try:
        paper = db.query(Paper).filter(Paper.id == paper_id).first()
        if not paper:
            yield _as_sse({"type": "error", "message": "Paper not found"})
            return

        existing = {item.get("citation"): item for item in (paper.citation_verified or [])}
        citations = _extract_citations(_extract_text_for_citations(paper))
        yield _as_sse({"type": "start", "total": len(citations)})

        results: list[dict] = []
        for index, citation in enumerate(citations, 1):
            if citation in existing:
                result = existing[citation]
            else:
                try:
                    s2_result = await search_paper_by_title(citation)
                    result = {
                        "citation": citation,
                        "status": (s2_result or {}).get("status", "not_found"),
                        "match": (s2_result or {}).get("match"),
                        "paperId": (s2_result or {}).get("paperId", ""),
                        "candidates": (s2_result or {}).get("candidates", []),
                    }
                except Exception as exc:
                    result = {"citation": citation, "status": "error", "message": str(exc), "match": None, "candidates": []}
            results.append(result)
            yield _as_sse({
                "type": "citation_status",
                "current": index,
                "total": len(citations),
                **result,
            })

        paper.citation_verified = results
        db.commit()
        yield _as_sse({"type": "summary", **_summarize(results)})
        yield _as_sse({"type": "done"})
    finally:
        db.close()


@router.post("/papers/{paper_id}/verify-citations")
async def verify_citations(paper_id: str, db: Session = Depends(get_db)):
    """Extract citations from a paper and stream Semantic Scholar verification progress."""
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return EventSourceResponse(_verify_stream(paper_id))


@router.get("/papers/{paper_id}/verification-status", response_model=CitationVerificationStatus)
async def get_verification_status(paper_id: str, db: Session = Depends(get_db)):
    """Return current citation verification summary for a paper."""
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return _summarize(paper.citation_verified or [])
