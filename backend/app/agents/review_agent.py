"""Review Agent — venue-aware simulated peer review."""

import json
import re
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.orm import Session

from app.database.sqlite import WritingProject
from app.llm import ChatMessage, LLMConfig, LLMProvider


REVIEWER_ROLES = {
    "method": (
        "You are a rigorous reviewer who focuses on methodological novelty, "
        "correctness, proof obligations, and technical depth."
    ),
    "experiment": (
        "You are an experimental reviewer who focuses on evaluation completeness, "
        "dataset choices, baseline fairness, ablations, and reproducibility."
    ),
    "theory": (
        "You are a theory-oriented reviewer who focuses on problem formulation, "
        "assumptions, limitations, and theoretical grounding."
    ),
    "writing": (
        "You are a senior area chair who focuses on positioning, clarity, "
        "claims, and whether the submission fits the target venue."
    ),
}


def _load_project_text(project_id: str, db: Session | None) -> tuple[WritingProject | None, str]:
    if not db:
        return None, ""
    project = db.query(WritingProject).filter(WritingProject.id == project_id).first()
    if not project or not project.latex_project_path:
        return project, ""
    main_tex = Path(project.latex_project_path) / "main.tex"
    if not main_tex.exists():
        return project, ""
    return project, main_tex.read_text(encoding="utf-8", errors="ignore")


def _plain_text(tex_content: str) -> str:
    content = re.sub(r"%.*", " ", tex_content)
    content = re.sub(r"\\(?:cite|ref|label)\*?(?:\[[^\]]*\])?\{[^}]*\}", " ", content)
    content = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{([^{}]*)\})?", r" \1 ", content)
    content = re.sub(r"[{}$&_^#~]", " ", content)
    return re.sub(r"\s+", " ", content).strip()


def _project_summary(project: WritingProject | None, tex_content: str, venue: str) -> str:
    title = project.title if project else "Untitled submission"
    target = venue or (project.target_venue if project else "") or "unspecified venue"
    text = _plain_text(tex_content)[:10000]
    return f"Title: {title}\nTarget venue: {target}\n\nPaper text excerpt:\n{text}"


def _fallback_review(index: int, role_key: str, venue: str, project: WritingProject | None) -> dict:
    title = project.title if project else "the submission"
    role_label = {
        "method": "Method-focused reviewer",
        "experiment": "Experiment-focused reviewer",
        "theory": "Theory-focused reviewer",
        "writing": "Writing and positioning reviewer",
    }.get(role_key, "Reviewer")
    return {
        "reviewer": index,
        "role": role_label,
        "summary": f"This review is a local fallback because no usable LLM response was available. The submission '{title}' should be checked against {venue or 'the target venue'} requirements before submission.",
        "strengths": [
            "The work appears to have a concrete research direction.",
            "The manuscript structure can be assessed from the LaTeX project.",
        ],
        "weaknesses": [
            "Novelty, evaluation strength, and related-work positioning still require human verification.",
            "Claims should be tied to evidence, ablations, and limitations before submission.",
        ],
        "questions": [
            "What is the strongest baseline and why is it sufficient?",
            "Which assumptions limit the method's applicability?",
        ],
        "overall_score": 5,
        "confidence": 2,
    }


def _fallback_meta(reviews: list[dict]) -> dict:
    if not reviews:
        avg = 5
    else:
        avg = sum(float(review.get("overall_score", 5)) for review in reviews) / len(reviews)
    if avg >= 8:
        decision = "accept"
    elif avg >= 6.5:
        decision = "weak accept"
    elif avg >= 5:
        decision = "borderline"
    elif avg >= 3.5:
        decision = "weak reject"
    else:
        decision = "reject"
    return {
        "decision": decision,
        "average_score": round(avg, 1),
        "summary": "The decision is estimated from reviewer scores. Treat this as a planning aid, not a real acceptance prediction.",
        "action_items": [
            "Tighten the contribution statement and venue fit.",
            "Add or strengthen experiments and ablations for the central claim.",
            "Clarify limitations and assumptions before submission.",
        ],
    }


def _parse_json_object(raw: str) -> dict:
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if match:
        raw = match.group(1)
    return json.loads(raw)


def _can_use_llm(config: LLMConfig) -> bool:
    base_url = (config.base_url or "").lower()
    return bool(config.api_key) or "localhost" in base_url or "127.0.0.1" in base_url


async def _generate_reviewer(
    index: int,
    role_key: str,
    paper_context: str,
    venue: str,
    provider: LLMProvider | None,
    config: LLMConfig | None,
    project: WritingProject | None,
) -> dict:
    if not provider or not config or not _can_use_llm(config):
        return _fallback_review(index, role_key, venue, project)

    prompt = f"""Simulate one peer review for the target venue: {venue or "unspecified"}.

Reviewer role:
{REVIEWER_ROLES[role_key]}

Submission:
{paper_context}

Return JSON only with these keys:
summary: string with 2-3 sentences
strengths: array of strings
weaknesses: array of strings
questions: array of strings
overall_score: integer 1-10
confidence: integer 1-5
"""
    try:
        raw = await provider.chat([
            ChatMessage(role="system", content="You simulate realistic, critical but fair academic peer reviews."),
            ChatMessage(role="user", content=prompt),
        ], config)
        parsed = _parse_json_object(raw)
        return {
            "reviewer": index,
            "role": role_key,
            "summary": str(parsed.get("summary", "")),
            "strengths": list(parsed.get("strengths", []))[:6],
            "weaknesses": list(parsed.get("weaknesses", []))[:6],
            "questions": list(parsed.get("questions", []))[:6],
            "overall_score": max(1, min(10, int(parsed.get("overall_score", 5)))),
            "confidence": max(1, min(5, int(parsed.get("confidence", 3)))),
        }
    except Exception:
        return _fallback_review(index, role_key, venue, project)


async def _generate_meta_review(
    reviews: list[dict],
    venue: str,
    provider: LLMProvider | None,
    config: LLMConfig | None,
) -> dict:
    fallback = _fallback_meta(reviews)
    if not provider or not config or not _can_use_llm(config):
        return fallback

    prompt = f"""Write an area-chair style meta-review for a {venue or "CS"} submission.

Reviewer JSON:
{json.dumps(reviews, ensure_ascii=False)}

Return JSON only with keys:
decision: accept / weak accept / borderline / weak reject / reject
average_score: number
summary: string
action_items: array of strings
"""
    try:
        raw = await provider.chat([
            ChatMessage(role="system", content="You are an experienced academic area chair."),
            ChatMessage(role="user", content=prompt),
        ], config)
        parsed = _parse_json_object(raw)
        return {
            "decision": str(parsed.get("decision", fallback["decision"])),
            "average_score": float(parsed.get("average_score", fallback["average_score"])),
            "summary": str(parsed.get("summary", fallback["summary"])),
            "action_items": list(parsed.get("action_items", fallback["action_items"]))[:8],
        }
    except Exception:
        return fallback


async def review_paper_simulation(
    project_id: str,
    venue: str,
    reviewer_count: int = 3,
    db: Session | None = None,
    provider: LLMProvider | None = None,
    config: LLMConfig | None = None,
) -> AsyncGenerator[dict, None]:
    """Stream structured simulated peer review events."""
    project, tex_content = _load_project_text(project_id, db)
    if not project:
        yield {"type": "error", "message": "Writing project not found"}
        yield {"type": "done"}
        return
    if not tex_content.strip():
        yield {"type": "error", "message": "main.tex not found or empty"}
        yield {"type": "done"}
        return

    safe_count = max(1, min(5, reviewer_count, len(REVIEWER_ROLES)))
    role_keys = list(REVIEWER_ROLES.keys())[:safe_count]
    paper_context = _project_summary(project, tex_content, venue)
    reviews: list[dict] = []

    yield {"type": "status", "message": f"Loaded LaTeX project and started {safe_count} simulated reviews."}
    for index, role_key in enumerate(role_keys, 1):
        yield {"type": "reviewer_start", "reviewer": index, "role": role_key}
        review = await _generate_reviewer(index, role_key, paper_context, venue, provider, config, project)
        reviews.append(review)
        yield {"type": "reviewer", "review": review}

    meta_review = await _generate_meta_review(reviews, venue, provider, config)
    yield {"type": "meta_review", "meta_review": meta_review}
    yield {"type": "done"}


async def generate_cover_letter(
    project_id: str,
    venue: str,
    editor_name: str,
    additional_notes: str,
    db: Session,
    provider: LLMProvider | None,
    config: LLMConfig | None,
) -> str:
    project, tex_content = _load_project_text(project_id, db)
    if not project:
        return "Writing project not found."
    fallback = f"""Dear {editor_name or "Editor"},

Please consider our manuscript, "{project.title}", for submission to {venue or project.target_venue or "your venue"}. The paper presents a focused research contribution and has been prepared according to the selected LaTeX project.

{additional_notes.strip() if additional_notes.strip() else ""}

Sincerely,
The Authors
"""
    if not provider or not config or not _can_use_llm(config):
        return fallback

    prompt = f"""Generate a concise academic cover letter.

Editor: {editor_name or "Editor"}
Venue: {venue or project.target_venue or "unspecified"}
Title: {project.title}
Additional notes: {additional_notes or "N/A"}

Paper excerpt:
{_plain_text(tex_content)[:6000]}

Return only the letter text.
"""
    try:
        return await provider.chat([
            ChatMessage(role="system", content="You write professional academic cover letters."),
            ChatMessage(role="user", content=prompt),
        ], config)
    except Exception:
        return fallback


async def generate_rebuttal(
    project_id: str,
    review_text: str,
    response_style: str,
    db: Session,
    provider: LLMProvider | None,
    config: LLMConfig | None,
) -> str:
    project, tex_content = _load_project_text(project_id, db)
    if not project:
        return "Writing project not found."
    fallback = f"""Dear Reviewers,

Thank you for the constructive feedback on "{project.title}". We will address the main concerns by clarifying the contribution, strengthening experimental evidence, and revising the manuscript text where the review identifies ambiguity.

Point-by-point response:
1. We will map each concern to a concrete manuscript revision.
2. We will add evidence or clarify limitations where claims are currently under-supported.
3. We will keep the response {response_style or "detailed"} and focused on verifiable changes.
"""
    if not provider or not config or not _can_use_llm(config):
        return fallback

    prompt = f"""Generate a rebuttal letter for an academic paper.

Response style: {response_style}
Paper title: {project.title}

Review text:
{review_text}

Paper excerpt:
{_plain_text(tex_content)[:5000]}

Requirements:
- Be respectful and specific.
- Organize by reviewer concern when possible.
- Do not promise experiments that are impossible from the evidence.

Return only the rebuttal letter.
"""
    try:
        return await provider.chat([
            ChatMessage(role="system", content="You write precise academic rebuttal letters."),
            ChatMessage(role="user", content=prompt),
        ], config)
    except Exception:
        return fallback
