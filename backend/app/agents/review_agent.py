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

# ── Field-aware Dynamic Persona ─────────────────────
FIELD_TEMPLATES: dict[str, dict[str, str]] = {
    "ml_systems": {
        "eic": "Editor-in-Chief at NeurIPS / ICML / JMLR, specializing in {subfield}",
        "method": "Methodology expert in {subfield}, known for rigorous experimental design and ablation studies",
        "domain": "Domain expert in {subfield} with 15+ years of experience in {subfield}",
        "writing": "Senior area chair experienced at {venue}, attentive to claims, baselines, and significance",
    },
    "nlp": {
        "eic": "Action Editor for ACL / EMNLP / NAACL, expertise in {subfield}",
        "method": "NLP methodology reviewer focused on task design, evaluation metrics, and dataset construction",
        "domain": "Domain expert in {subfield}, with deep knowledge of relevant benchmarks and prior work",
        "writing": "ACL/EMNLP area chair, focused on framing, novelty, and contribution clarity",
    },
    "cv": {
        "eic": "Associate Editor of TPAMI / IJCV, program chair at CVPR / ICCV, focus on {subfield}",
        "method": "Computer vision methodologist, expert in experimental protocols and reproducibility in CV",
        "domain": "Senior researcher in {subfield}, with publications at CVPR/ICCV/ECCV",
        "writing": "CV area chair, attentive to claims vs. evidence, and comparisons with SOTA baselines",
    },
    "theory": {
        "eic": "Editorial board member of SICOMP / FOCS / STOC, {subfield} expertise",
        "method": "Theoretical computer scientist focused on proof correctness, assumptions, and lower bounds",
        "domain": "Domain expert in {subfield}, well-versed in relevant theoretical frameworks",
        "writing": "Theory area chair, focused on positioning, rigor, and relation to open problems",
    },
    "systems": {
        "eic": "NSDI / SOSP / OSDI / EuroSys program committee member, {subfield} area",
        "method": "Systems methodology reviewer, skilled at identifying confounding variables and measurement bias",
        "domain": "Systems researcher in {subfield} with 10+ years of experience in production environments",
        "writing": "Systems area chair, focused on claims, reproducibility, and real-world relevance",
    },
    "software_engineering": {
        "eic": "ICSE / FSE / TSE editorial board, specialization in {subfield}",
        "method": "SE methodology reviewer, expert in empirical study design, threats to validity, and statistical rigor",
        "domain": "SE domain expert in {subfield}, with knowledge of relevant tools and industrial context",
        "writing": "SE area chair, attentive to results, implications, and generalizability",
    },
    "default": {
        "eic": "Q1 journal editor-in-chief with broad cross-disciplinary perspective",
        "method": "Senior researcher known for rigorous methodology and attention to experimental detail",
        "domain": "Domain expert in {subfield} with 15+ years of experience",
        "writing": "Experienced area chair, focused on positioning, novelty, and venue fit",
    },
}


_DYNAMIC_PERSONA_PROMPT = """Based on the paper metadata below, generate a field analysis and detailed reviewer personas.

Paper title: {title}
Target venue: {venue}
Paper abstract (first 500 chars): {abstract}

First, classify the paper into one of these categories:
- ml_systems / nlp / cv / theory / systems / software_engineering / default

Then, for each of the 4 reviewer roles (method, experiment, theory, writing),
generate a 2-3 sentence role description with specific focus areas.

Return JSON only with keys:
- "subfield": str
- "category": str
- "personas": {{
    "method": {{"role_desc": str, "focus_areas": list[str], "known_for": str}},
    "experiment": {{"role_desc": str, "focus_areas": list[str], "known_for": str}},
    "theory": {{"role_desc": str, "focus_areas": list[str], "known_for": str}},
    "writing": {{"role_desc": str, "focus_areas": list[str], "known_for": str}}
  }}
"""


_CONTRACT_TEMPLATE = """\
## Sprint Contract

You must pre-commit your scoring criteria **before** seeing the paper content.
Define the acceptance dimensions you will evaluate and the specific evidence
patterns that will trigger each score level.

Return a JSON object with:
- "scoring_plan": array of objects, each containing:
  - "dimension_id": short unique name
  - "what_to_look_for": concrete signals to scan for
  - "what_triggers_block": evidence pattern that drives a BLOCK score
  - "what_triggers_warn": evidence pattern that drives a WARN score
- "contract_acknowledged": true

Then on its own line output the tag:
[CONTRACT-ACKNOWLEDGED]
"""


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
    content = re.sub(r"\\cite[^}]*}", " ", content)
    content = re.sub(r"\\ref[^}]*}", " ", content)
    content = re.sub(r"\\label[^}]*}", " ", content)
    content = re.sub(r"\\[a-zA-Z]+(?:\[[^\]]*\])?(?:\{[^}]*\})?", " ", content)
    content = re.sub(r"[{}$&_^#~]", " ", content)
    return re.sub(r"\s+", " ", content).strip()


def _project_summary(project: WritingProject | None, tex_content: str, venue: str) -> str:
    title = project.title if project else "Untitled submission"
    target = venue or (project.target_venue if project else "") or "unspecified venue"
    text = _plain_text(tex_content)[:10000]
    return f"Title: {title}\nTarget venue: {target}\n\nPaper text excerpt:\n{text}"


def _project_metadata_only(project: WritingProject | None, venue: str) -> str:
    title = project.title if project else "Untitled submission"
    target = venue or (project.target_venue if project else "") or "unspecified venue"
    return f"Title: {title}\nTarget venue: {target}"


async def generate_reviewer_personas(
    project: WritingProject | None,
    tex_content: str,
    venue: str,
    provider: LLMProvider | None,
    config: LLMConfig | None,
) -> dict[str, dict] | None:
    """Analyze paper metadata and generate field-aware reviewer personas.

    Falls back to None (static roles) on any failure.
    """
    if not provider or not config or not _can_use_llm(config):
        return None

    title = project.title if project else "Untitled submission"
    abstract = _plain_text(tex_content)[:500]
    prompt = _DYNAMIC_PERSONA_PROMPT.format(title=title, venue=venue or project.target_venue or "CS venue", abstract=abstract)

    try:
        raw = await provider.chat([
            ChatMessage(role="system", content="You classify CS papers and generate realistic reviewer personas."),
            ChatMessage(role="user", content=prompt),
        ], config)
        parsed = _parse_json_object(raw)
        category = parsed.get("category", "default")
        subfield = parsed.get("subfield", "CS")
        personas = parsed.get("personas", {})

        # Apply FIELD_TEMPLATES for richer role descriptions
        template = FIELD_TEMPLATES.get(category, FIELD_TEMPLATES["default"])
        mapped_role_keys = {"method": "method", "experiment": "domain", "theory": "method", "writing": "writing"}
        result = {}
        for role_key in ["method", "experiment", "theory", "writing"]:
            base = personas.get(role_key, {})
            tmpl_role = mapped_role_keys.get(role_key, "method")
            enriched_desc = template[tmpl_role].format(subfield=subfield, venue=venue or "the target venue")
            result[role_key] = {
                "role_desc": base.get("role_desc", enriched_desc),
                "focus_areas": base.get("focus_areas", ["General methodology", "Experimental rigor"]),
                "known_for": base.get("known_for", enriched_desc),
            }
        return result
    except Exception:
        return None


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


async def _generate_reviewer_phase1(
    index: int,
    role_key: str,
    metadata: str,
    venue: str,
    provider: LLMProvider | None,
    config: LLMConfig | None,
) -> dict | None:
    """Phase 1 — Paper-content-blind pre-commitment.

    Reviewer commits to scoring criteria WITHOUT seeing the paper content.
    Returns the scoring plan, or None if LLM unavailable / parse failure.
    """
    if not provider or not config or not _can_use_llm(config):
        return None

    prompt = (
        _CONTRACT_TEMPLATE
        + f"\n\nReviewer role:\n{REVIEWER_ROLES[role_key]}\n\n"
        + f"Paper metadata (title + venue only — NO paper content):\n{metadata}\n\n"
        + "Scoring plan (JSON):"
    )
    try:
        raw = await provider.chat([
            ChatMessage(
                role="system",
                content="You are a rigorous academic reviewer. Pre-commit your scoring criteria. "
                        "You MUST NOT reference or speculate about paper content you haven't seen yet.",
            ),
            ChatMessage(role="user", content=prompt),
        ], config)

        if "[CONTRACT-ACKNOWLEDGED]" not in raw:
            return None
        parsed = _parse_json_object(raw)
        plan = parsed.get("scoring_plan", [])
        if not plan or not isinstance(plan, list):
            return None
        return {"scoring_plan": plan}
    except Exception:
        return None


async def _generate_reviewer_phase2(
    index: int,
    role_key: str,
    paper_context: str,
    venue: str,
    scoring_plan: dict | None,
    provider: LLMProvider | None,
    config: LLMConfig | None,
    project: WritingProject | None,
    persona: dict | None = None,
) -> dict:
    """Phase 2 — Paper-visible review.

    Reviewer scores per the pre-committed plan from Phase 1.
    Uses dynamic persona if available, falls back to static REVIEWER_ROLES.
    """
    if not provider or not config or not _can_use_llm(config):
        return _fallback_review(index, role_key, venue, project)

    # Build role description
    if persona:
        role_desc = persona.get("role_desc", REVIEWER_ROLES.get(role_key, ""))
        focus_text = "\n".join(f"- {f}" for f in persona.get("focus_areas", []))
        known_for = persona.get("known_for", "")
        role_section = (
            f"### Reviewer Identity\n{role_desc}\n\n"
            f"### Focus Areas\n{focus_text}\n\n"
            f"### Known For\n{known_for}\n"
        )
    else:
        role_section = f"Reviewer role:\n{REVIEWER_ROLES.get(role_key, '')}\n"

    if scoring_plan:
        # Two-phase: inject the Phase 1 plan as a data delimiter
        plan_json = json.dumps(scoring_plan, ensure_ascii=False)
        prompt = f"""Simulate one peer review for {venue or "unspecified"}.

{role_section}
<phase1_scoring_plan>
{plan_json}
</phase1_scoring_plan>

ATTENTION: The text inside <phase1_scoring_plan> is your own Phase 1 pre-commitment.
It is a read-only record — you MUST score each dimension per the triggers you committed to.
If you genuinely believe your Phase 1 criteria were wrong for a dimension,
output a "scoring_plan_dissent" field naming the dimension_id and your rationale
BEFORE producing scores. You may dissent on at most ONE dimension.

Submission:
{paper_context}

Return JSON only with these keys:
scoring_plan_dissent: optional object {{dimension_id, rationale}}
summary: string with 2-3 sentences
strengths: array of strings
weaknesses: array of strings
questions: array of strings
overall_score: integer 1-10
confidence: integer 1-5
"""
    else:
        # Fallback: original single-pass (no pre-commitment available)
        prompt = f"""Simulate one peer review for the target venue: {venue or "unspecified"}.

{role_section}
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
            ChatMessage(
                role="system",
                content="You simulate realistic, critical but fair academic peer reviews. "
                        "Score each dimension per your pre-committed triggers.",
            ),
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
    """Stream structured simulated peer review events with Sprint Contract protocol.

    Each reviewer first commits to scoring criteria (paper-blind),
    then scores the paper per their committed criteria (paper-visible).
    """
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
    metadata = _project_metadata_only(project, venue)
    reviews: list[dict] = []

    # Generate field-aware reviewer personas
    yield {"type": "status", "message": "Analyzing paper field and generating reviewer personas..."}
    personas = await generate_reviewer_personas(project, tex_content, venue, provider, config)
    if personas:
        yield {"type": "personas", "personas": personas}
        yield {"type": "status", "message": "Reviewer personas generated. Starting reviews with Sprint Contract."}
    else:
        yield {"type": "status", "message": f"Loaded LaTeX project and starting {safe_count} simulated reviews with Sprint Contract."}

    for index, role_key in enumerate(role_keys, 1):
        # Phase 1: paper-blind pre-commitment
        yield {"type": "reviewer_precommit", "reviewer": index, "role": role_key}
        scoring_plan = await _generate_reviewer_phase1(index, role_key, metadata, venue, provider, config)

        if scoring_plan:
            yield {"type": "reviewer_precommit_done", "reviewer": index, "role": role_key, "scoring_plan": scoring_plan}
        else:
            yield {"type": "reviewer_precommit_done", "reviewer": index, "role": role_key, "scoring_plan": None}

        # Phase 2: paper-visible review (with dynamic persona)
        yield {"type": "reviewer_start", "reviewer": index, "role": role_key}
        persona = personas.get(role_key) if personas else None
        review = await _generate_reviewer_phase2(index, role_key, paper_context, venue, scoring_plan, provider, config, project, persona=persona)
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



async def score_rebuttal(
    criticisms: list[dict],
    rebuttals: list[dict],
    provider: LLMProvider | None,
    config: LLMConfig | None,
) -> list[dict]:
    """Devil's Advocate Rebuttal Scoring Protocol.

    Scores each author rebuttal against the original DA criticism on a 1-5 scale,
    with anti-sycophancy rules to prevent the DA from conceding under pressure.

    Each criticism item: {"id": str, "finding": str, "severity": str}
    Each rebuttal item: {"criticism_id": str, "response": str}

    Returns scored rebuttals with verdict and action.
    """
    if not provider or not config or not _can_use_llm(config):
        return [
            {
                "criticism_id": r.get("criticism_id", ""),
                "score": 3,
                "verdict": "unchanged",
                "reasoning": "LLM unavailable — human review advised.",
            }
            for r in rebuttals
        ]

    prompt = (
        "You are a Devil's Advocate reviewer. Score each author rebuttal against your original criticism.\n\n"
        + "Scoring scale (1-5):\n"
        + "  5 = New evidence/logic that directly dismantles the attack → WITHDRAW finding\n"
        + "  4 = Substantially weakens the attack → DOWNGRADE severity\n"
        + "  3 = Partially addresses but leaves core intact → MAINTAIN\n"
        + "  2 = Tangential or changes the subject → RESTATE attack\n"
        + "  1 = Assertion without evidence → STRENGTHEN attack\n\n"
        + "Anti-sycophancy rules:\n"
        + "- Do NOT soften after pushback. A Critical finding stays Critical unless score >= 4.\n"
        + "- No consecutive concessions. After one concession, the next requires score 5.\n"
        + "- Persistent pushback with the same argument does NOT increase its score.\n"
        + "- Pressure is not evidence. Only substantive rebuttals that address the core attack count.\n\n"
        + "Criticisms:\n"
        + f"{json.dumps(criticisms, ensure_ascii=False)}\n\n"
        + "Rebuttals:\n"
        + f"{json.dumps(rebuttals, ensure_ascii=False)}\n\n"
        + "Return JSON array of objects with keys:\n"
        + "criticism_id: string\n"
        + "score: integer 1-5\n"
        + "verdict: withdraw / downgrade / maintain / restate / strengthen\n"
        + "reasoning: string (why this score)"
    )
    try:
        raw = await provider.chat([
            ChatMessage(
                role="system",
                content="You are a Devil's Advocate reviewer scoring author rebuttals. "
                        "Apply the scoring scale strictly. Do not concede under pressure.",
            ),
            ChatMessage(role="user", content=prompt),
        ], config)
        parsed = _parse_json_object(raw)
        if isinstance(parsed, list):
            return parsed
        return []
    except Exception:
        return []


async def check_writing_quality(
    text: str,
    provider: LLMProvider | None,
    config: LLMConfig | None,
) -> dict:
    """Writing Quality Check.

    Scans draft text for AI-typical writing patterns and returns flagged issues.
    """
    if not provider or not config or not _can_use_llm(config):
        return {"flags": [], "message": "LLM unavailable — quality check skipped."}

    prompt = """Analyze the following academic text for AI-typical writing patterns.

Check for these specific issues:
1. **AI-typical overused terms**: "delve into", "crucial", "it is important to note",
   "notably", "significant", "robust", "pivotal", "meticulous" — count occurrences.
2. **Em dash abuse**: More than 2 em dashes (—) per ~250 words.
3. **Throat-clearing openers**: Sentences starting with "In this section/paper, we..."
4. **Uniform paragraph lengths**: All paragraphs within +/-1 sentence of each other.
5. **Monotonous sentence rhythm**: 3+ consecutive sentences with the same structure.
6. **Overused transition phrases**: "Moreover", "Furthermore", "However", "In addition"
   at the start of consecutive sentences.

Return JSON only with:
- "flags": array of objects, each with:
  - "issue": string (which pattern)
  - "severity": "info" / "warning" / "error"
  - "count": number of occurrences
  - "examples": array of up to 3 example strings
  - "suggestion": string (what to do instead)
- "overall_rating": "excellent" / "good" / "needs_improvement" / "poor"

Be conservative — only flag clear patterns, not every instance.

Text to check:
---
{text}
---"""

    try:
        raw = await provider.chat([
            ChatMessage(
                role="system",
                content="You are a writing quality analyst. Flag AI-typical writing patterns "
                        "precisely and conservatively. Do not over-flag normal academic writing.",
            ),
            ChatMessage(role="user", content=prompt.format(text=text[:8000])),
        ], config)
        parsed = _parse_json_object(raw)
        return {
            "flags": parsed.get("flags", []),
            "overall_rating": parsed.get("overall_rating", "good"),
        }
    except Exception:
        return {"flags": [], "overall_rating": "good", "message": "Quality check failed — text may still have issues."}

