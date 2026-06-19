"""Idea Agent — research idea generation and feasibility evaluation."""

import json
from collections import Counter
from typing import AsyncGenerator

from sqlalchemy.orm import Session

from loguru import logger

from app.database.sqlite import Paper
from app.llm import ChatMessage, LLMConfig, LLMProvider


_IDEA_PARSE_PROMPT = """\
Parse the following research ideas Markdown text into a JSON array of idea objects.
Each object must have: title (string), description (string), novelty (string),
risks (string), first_experiment (string).
If no clear ideas are found, return an empty array.

Text to parse:
{text}
"""

_EVALUATION_PROMPT = """\
Evaluate each of the following research ideas independently.
For each idea, assess novelty (1-5), feasibility (1-5), and cost (1-5).
Provide a brief reasoning for each score.

Return JSON array of objects with keys:
idea_title, novelty, feasibility, cost, reasoning

Do NOT let scores from one idea influence scores for another idea.

Ideas:
{ideas}
"""


def _paper_context(papers: list[Paper]) -> str:
    entries = []
    for index, paper in enumerate(papers, 1):
        entries.append(
            "\n".join([
                f"[{index}] {paper.title}",
                f"Authors: {', '.join(paper.authors or [])}",
                f"Year: {paper.year or 'N/A'}",
                f"Venue: {paper.venue or 'N/A'}",
                f"Abstract: {(paper.abstract or '')[:1200]}",
                f"Extracted: {json.dumps(paper.extracted_data or {}, ensure_ascii=False)[:1600]}",
            ])
        )
    return "\n\n".join(entries)


def _build_prompt(
    papers: list[Paper],
    mode: str,
    custom_prompt: str = "",
    domain_a: str = "",
    domain_b: str = "",
) -> str:
    context = _paper_context(papers)
    year_counts = Counter(p.year for p in papers if p.year)
    trend_summary = ", ".join(f"{year}: {count}" for year, count in sorted(year_counts.items()))

    mode_instruction = {
        "gap_analysis": (
            "Identify contradictions, missing evaluations, scalability limits, and underexplored "
            "assumptions across the papers. Propose 3-5 concrete research ideas."
        ),
        "cross_domain": (
            f"Transfer useful mechanisms between domain A ({domain_a or 'unspecified'}) and "
            f"domain B ({domain_b or 'unspecified'}). Propose 3-5 cross-domain research ideas."
        ),
        "trend_based": (
            "Use the publication-year distribution and topic signals to infer emerging directions. "
            f"Year distribution: {trend_summary or 'unknown'}. Propose 3-5 trend-based ideas."
        ),
    }.get(mode, "Propose 3-5 concrete research ideas grounded in the papers.")

    return f"""You are a senior computer science researcher.

Task:
{mode_instruction}

For each idea, provide:
- Title
- Short description
- Why it is novel
- Main risks
- First experiment to run

Do NOT self-score or self-evaluate. Only generate the raw ideas.

Return Markdown with one section per idea. Be specific and technically actionable.

User custom instruction:
{custom_prompt or 'N/A'}

Papers:
{context or 'No papers selected. Use the custom instruction and available domain fields.'}
"""


def _fallback_ideas(mode: str, papers: list[Paper], domain_a: str = "", domain_b: str = "") -> str:
    topic = papers[0].title if papers else (f"{domain_a} x {domain_b}".strip(" x") or "the selected area")
    if mode == "cross_domain":
        title = f"Transfer mechanisms between {domain_a or 'Domain A'} and {domain_b or 'Domain B'}"
    elif mode == "trend_based":
        title = f"Trend-aware benchmark for {topic}"
    else:
        title = f"Gap-driven extension of {topic}"

    return f"""## Idea 1: {title}

Description: Build a focused study around unresolved assumptions found in the selected literature.

Novelty: 3/5
Feasibility: 4/5
Cost: 2/5
Risks: The gap may already be addressed by newer work; validate with an updated search.
First experiment: Reproduce the strongest baseline and test it on one shifted dataset or setting.
"""


async def generate_ideas(
    paper_ids: list[str],
    mode: str,
    db: Session,
    provider: LLMProvider | None = None,
    config: LLMConfig | None = None,
    custom_prompt: str = "",
    domain_a: str = "",
    domain_b: str = "",
) -> AsyncGenerator[dict, None]:
    papers = []
    if paper_ids:
        papers = db.query(Paper).filter(Paper.id.in_(paper_ids)).all()

    yield {"type": "status", "message": f"Loaded {len(papers)} papers"}

    if not provider or not config:
        yield {
            "type": "chunk",
            "content": _fallback_ideas(mode, papers, domain_a=domain_a, domain_b=domain_b),
        }
        yield {"type": "done"}
        return

    prompt = _build_prompt(
        papers,
        mode=mode,
        custom_prompt=custom_prompt,
        domain_a=domain_a,
        domain_b=domain_b,
    )
    messages = [
        ChatMessage(role="system", content="You generate rigorous, testable research ideas."),
        ChatMessage(role="user", content=prompt),
    ]

    # Phase 1: Generate ideas (no self-scoring)
    generated_text = ""
    try:
        async for token in provider.chat_stream(messages, config):
            generated_text += token
            yield {"type": "chunk", "content": token}
    except Exception as exc:
        logger.warning("idea_agent.py operation failed: {}", exc)
        yield {"type": "error", "message": str(exc)}
        generated_text = _fallback_ideas(mode, papers, domain_a=domain_a, domain_b=domain_b)
        yield {"type": "chunk", "content": generated_text}

    yield {"type": "generation_done"}

    # Phase 2: Evaluate generated ideas independently
    try:
        parsed_ideas = await provider.chat([
            ChatMessage(role="system", content="You parse research ideas into structured data."),
            ChatMessage(role="user", content=_IDEA_PARSE_PROMPT.format(text=generated_text)),
        ], config)
        ideas_list = json.loads(parsed_ideas) if parsed_ideas.strip().startswith("[") else []
        if isinstance(parsed_ideas, str):
            stripped = parsed_ideas.strip()
            if stripped.startswith("```"):
                stripped = stripped.strip("`").removeprefix("json").strip()
            ideas_list = json.loads(stripped) if stripped else []
    except Exception as exc:
        logger.warning("idea_agent.py operation failed: {}", exc)
        ideas_list = []

    if ideas_list:
        yield {"type": "status", "message": f"Beginning independent evaluation of {len(ideas_list)} ideas."}
        ideas_json = "\n".join(
            f"- **{i.get('title', 'Untitled')}**: {i.get('description', '')[:300]}"
            for i in ideas_list
        )
        try:
            evaluations_raw = await provider.chat([
                ChatMessage(role="system", content="You evaluate research ideas independently. "
                            "Each idea's scores must be independent of others."),
                ChatMessage(role="user", content=_EVALUATION_PROMPT.format(ideas=ideas_json)),
            ], config)
            stripped = evaluations_raw.strip()
            if stripped.startswith("```"):
                stripped = stripped.strip("`").removeprefix("json").strip()
            evaluations = json.loads(stripped) if stripped else []
            for ev in evaluations:
                yield {"type": "evaluation", "evaluation": ev}
        except Exception as exc:
            logger.warning("idea_agent.py operation failed: {}", exc)
            yield {"type": "status", "message": "Idea evaluation failed — manual review advised."}
    else:
        yield {"type": "status", "message": "Could not parse generated ideas for evaluation. Scores were not in the generation (by design)."}

    yield {"type": "done"}


async def evaluate_feasibility(
    idea: str,
    context_paper_ids: list[str],
    db: Session,
    provider: LLMProvider | None = None,
    config: LLMConfig | None = None,
) -> dict:
    papers = db.query(Paper).filter(Paper.id.in_(context_paper_ids)).all() if context_paper_ids else []
    if not provider or not config:
        return {
            "idea": idea,
            "novelty": 3,
            "feasibility": 3,
            "cost": 3,
            "risk": "medium",
            "report": "No active LLM provider was available. Manual review is recommended.",
        }

    prompt = f"""Evaluate this research idea.

Return JSON with keys: novelty, feasibility, cost, risk, report.
Scores are 1-5. risk is low/medium/high. report is a concise Markdown paragraph.

Idea:
{idea}

Relevant papers:
{_paper_context(papers)}
"""
    try:
        raw = await provider.chat([
            ChatMessage(role="system", content="You evaluate research idea feasibility."),
            ChatMessage(role="user", content=prompt),
        ], config)
        stripped = raw.strip()
        if stripped.startswith("```"):
            stripped = stripped.strip("`")
            stripped = stripped.removeprefix("json").strip()
        parsed = json.loads(stripped)
        return {
            "idea": idea,
            "novelty": int(parsed.get("novelty", 3)),
            "feasibility": int(parsed.get("feasibility", 3)),
            "cost": int(parsed.get("cost", 3)),
            "risk": parsed.get("risk", "medium"),
            "report": parsed.get("report", raw),
        }
    except Exception as exc:
        logger.warning("idea_agent.py operation failed: {}", exc)
        return {
            "idea": idea,
            "novelty": 3,
            "feasibility": 3,
            "cost": 3,
            "risk": "medium",
            "report": f"Evaluation failed: {exc}",
        }
