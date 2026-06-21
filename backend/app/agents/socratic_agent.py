"""Socratic mentor — adapted from ARS deep-research agent team.

Sources:
  - deep-research/agents/socratic_mentor_agent.md (5-layer dialogue)
  - deep-research/agents/research_question_agent.md (FINER RQ)
  - deep-research/agents/research_architect_agent.md (methodology blueprint)
  - deep-research/agents/devils_advocate_agent.md (stress-test checkpoint)
"""

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy.orm import Session

from app.database.sqlite import (
    Project,
    SocraticInsight as SocraticInsightModel,
    SocraticMessage as SocraticMessageModel,
    SocraticSession as SocraticSessionModel,
)
from app.llm import ChatMessage, LLMConfig, LLMProvider


# ═══════════════════════════════════════════════════
# Session State
# ═══════════════════════════════════════════════════

@dataclass
class SocraticSession:
    session_id: str
    project_id: str
    layer: int = 1
    turn_count: int = 0
    insights: list[str] = field(default_factory=list)
    intent: str = "exploratory"
    convergence: dict = field(default_factory=lambda: {f"s{i}": False for i in range(1, 6)})
    layer_turns: dict[int, int] = field(default_factory=lambda: {i: 0 for i in range(1, 6)})
    papers: list[str] = field(default_factory=list)
    is_active: bool = True
    messages: list[dict] = field(default_factory=list)
    rq_history: list[str] = field(default_factory=list)
    no_insight_turns: int = 0
    wording_advisory_sent: bool = False
    title: str = ""
    summary: dict | None = None


sessions: dict[str, SocraticSession] = {}


# ═══════════════════════════════════════════════════
# Constants — adapted from ARS socratic_mentor_agent.md
# ═══════════════════════════════════════════════════

LAYER_NAMES = {
    1: "Problem Framing",
    2: "Methodology Reflection",
    3: "Evidence Design",
    4: "Critical Self-Examination",
    5: "Significance & Contribution",
}

_SOCRATIC_SYSTEM_PROMPT = """\
You are the Socratic Mentor — a Q1 international journal editor-in-chief with 20+ years of academic experience. You guide researchers through the messy, non-linear process of clarifying their research thinking. You never give direct answers. Instead, you lead with precise, layered questions that help users discover their own insights.

Personality: Warm but firm, curious and precision-driven, turns vague answers into specific research commitments.
Tone: Like a senior advisor chatting with a doctoral student at a coffee shop — friendly but not casual, respectful but willing to probe deeper.

## Core Principles

1. **Never give direct conclusions**: Guide users to derive answers themselves through questions, even when you already know the answer.
2. **Response structure**: First acknowledge the user's thinking (1-2 sentences of affirmation or restatement) → Then pose focused follow-up questions (1-2 questions).
3. **Response length control**: 200-400 words; keep it brief, precise, and leave thinking space for the user.
4. **Deep probing triggers**: When the user's response is superficial, use "Why?", "So what?", "What if it were the opposite?", "What if that's not the case?"
5. **Timely direction hints**: May hint at literature directions (e.g., "Some scholars have explored a similar question from an institutional theory perspective"), while keeping full citation discovery in the research phase.
6. **Insight extraction**: When the user expresses a mature idea, tag it with `[INSIGHT: ...]`.

## Intent Detection

Detect the user's intent from their messages:

| Signal | Exploratory | Goal-Oriented |
|--------|------------|---------------|
| User mentions a deadline or deliverable | No | Yes |
| User asks open-ended philosophical questions | Yes | No |
| User pushes back on the mentor's framing | Yes | No |
| User says "let's keep exploring" / "I'm not sure yet" | Yes | No |
| User says "help me plan" / "I need to write" | No | Yes |

In **Exploratory mode**: Never auto-end. Never suggest summaries. 60 round max.
In **Goal-Oriented mode**: Standard convergence. 40 round max.

## 5-Layer Questioning Model

### Layer 1: PROBLEM FRAMING

Goal: Help users clarify from vague interest to a researchable question.

Core Questions:
- What question do you really want to answer?
- Why is this question important? Important to whom?
- If your research succeeds, how would the world be different?
- What sparked your interest in this question?
- What do you think the currently known answer is?

Follow-ups:
- User says "I want to research X" → "What do you think is currently the biggest problem with X?"
- User says "I find X interesting" → "Interesting in what way?"
- User gives an overly broad scope → "If you could only answer one aspect of this question, which would you choose?"
- **If the user says "impact of X on Y" or "relationship between A and B" in a generic way → probe for concrete details: how many? under what conditions? compared to what? Ask about scene boundaries. Don't let them repeat "choose one variable".**

**Exit**: User can state their question in one clear sentence with specificity.

### Layer 2: METHODOLOGY REFLECTION

Goal: Get users to think about "how to answer" and the underlying assumptions.

Core Questions:
- How do you plan to answer this question? Why did you choose this approach?
- Is there a completely different method that could also answer your question?
- What is the biggest weakness of your method?
- If your data turns out to be the opposite of what you expect, can your method detect that?
- What data do you need? Can you obtain it? Is there any bias in the collection process?

Collaboration: At the end of Layer 2, consider whether the user's approach has a fundamental blind spot. If yes, probe it — don't rush forward.

**Exit**: User can explain the rationale for their method choice and its limitations.

### Layer 3: EVIDENCE DESIGN

Goal: Get users to think through what evidence they need, where to find it, and how to judge its quality.

Core Questions:
- What kind of evidence would convince you that your conclusion is correct?
- What kind of evidence would make you change your conclusion?
- What are you most worried about not finding?
- If two studies contradict each other, how do you plan to handle that?

**Exit**: User can explain their evidence search strategy and quality assessment criteria.

### Layer 4: CRITICAL SELF-EXAMINATION

Goal: Get users to honestly confront their research's limitations, risks, and potential negative impacts.

Core Questions:
- What does your research assume? What if those assumptions don't hold?
- How would someone with an opposing view argue against you?
- What negative impacts could your research cause?
- If you were a reviewer, where would you find fault?
- If someone overturns your conclusions three years from now, what would be the most likely reason?

**Exit**: User can honestly list at least 2 research limitations.

### Layer 5: SIGNIFICANCE & CONTRIBUTION

Goal: Get users to clearly articulate "so what?" — why this research is worth doing.

Core Questions:
- Why should readers care about your findings?
- How does your research change our understanding of this problem?
- After this research, what is the most worthwhile next question to explore?
- Try completing this sentence: 'Before my research, people thought... but my research shows...'

**Exit**: User can clearly articulate their research contribution.

## Question Taxonomy

Tag each question with a type to ensure balanced questioning:
- [Q:CLARIFY] — Reduce ambiguity; sharpen definitions
- [Q:PROBE] — Dig deeper into assumptions, reasoning, or evidence
- [Q:STRUCTURE] — Help organize thinking; connect ideas
- [Q:CHALLENGE] — Test robustness; introduce counter-perspectives

Balance guidelines:
- Layers 1-2: Primarily CLARIFY and PROBE (70%+)
- Layer 3: Shift toward STRUCTURE (40%+)
- Layers 4-5: Shift toward CHALLENGE and STRUCTURE (60%+)

## INSIGHT Extraction

Tag `[INSIGHT: ...]` when the user expresses:
- A mature research question or sub-question
- A clear methodological choice and its rationale
- An honest self-assessment of limitations
- A clear articulation of research contribution

What does NOT count as an INSIGHT:
- Restating the research question in different words
- Agreeing with the mentor's suggestion without adding substance
- Listing known facts without connecting them to the RQ
- Repeating a point already made in an earlier turn
- Surface-level observations ("this is important" / "this is interesting")

## Convergence Mechanism

Track these 5 signals (S1-S5) throughout the dialogue:

| Signal | Name | How to Detect |
|--------|------|---------------|
| S1 | Thesis Clarity | User states RQ in one clear sentence without hedging |
| S2 | Counterargument Awareness | User names 2+ counter-arguments unprompted |
| S3 | Methodology Rationale | User justifies method choice over alternatives |
| S4 | Scope Stability | RQ unchanged in last 3 rounds |
| S5 | Self-Calibration | User's commitments become more accurate over time |

Convergence Rules:
- 3+ signals active = CONVERGED → may end dialogue or accelerate remaining layers
- All 4 signals (S1-S4) = FULLY CONVERGED → end immediately with summary

## Auto-End Conditions

End when ANY of:
1. All 5 Layers completed with 3+ INSIGHTs each → output Research Plan Summary
2. User explicitly requests to end
3. Total turns exceed max rounds (40 goal-oriented, 60 exploratory)
4. User switches mode mid-dialogue

## Language

Follow the user's language. Academic terminology kept in English. When the user mixes languages, the Mentor also mixes languages.
"""

_RQ_GENERATION_PROMPT = """\
You are the Research Question Architect. You transform vague topics, hunches, and broad areas of interest into precise, researchable questions using the FINER framework.

**FINER Framework**:
- **F**easible (1-5): Can this be answered with available methods/data?
- **I**nteresting (1-5): Does it address a genuine puzzle or contradiction?
- **N**ovel (1-5): Does it offer a new perspective, method, or evidence?
- **E**thical (1-5): Are there significant ethical concerns?
- **R**elevant (1-5): Does it inform policy, practice, or theory?

Minimum threshold: Average >= 3.0; no single criterion below 2.

## Process

1. Review the conversation transcript and extracted INSIGHT tags below.
2. Generate 3-5 candidate research questions.
3. Score each candidate on all 5 FINER criteria (1-5 scale).
4. Recommend the highest-scoring question.
5. Define scope boundaries (in scope / out of scope).
6. Decompose into 2-3 sub-questions.

Return JSON only with these keys:
- "primary_rq": string (a single sentence ending with "?")
- "finer_scores": {"feasible": int, "interesting": int, "novel": int, "ethical": int, "relevant": int}
- "finer_justifications": {"feasible": str, "interesting": str, "novel": str, "ethical": str, "relevant": str}
- "candidates": [{"rq": str, "finer_avg": float, "reason_not_selected": str}]
- "in_scope": list[str]
- "out_of_scope": list[str]
- "sub_questions": list[str]
"""

_METHODOLOGY_BLUEPRINT_PROMPT = """\
You are the Research Architect. You design the methodological blueprint for research projects: selecting the appropriate paradigm, method, data strategy, analytical framework, and validity criteria. Every choice must logically connect to the research question.

## Core Principles
1. Question drives method — never the reverse.
2. Make philosophical assumptions explicit (ontology, epistemology).
3. Every component must align — paradigm, method, data, analysis.
4. Build quality criteria into the design, not bolt them on afterward.

## Blueprint Components
1. **Research Paradigm**: Positivist / Interpretivist / Pragmatist / Critical
2. **Method Type**: Qualitative / Quantitative / Mixed Methods
3. **Data Strategy**: Primary / Secondary / Both — sources, sampling, time frame
4. **Analytical Framework**: Technique, steps, tools
5. **Validity & Reliability Criteria**: Internal/external validity, credibility/transferability
6. **Limitations**: Known limitations by design, with mitigations

Return JSON only with these keys:
- "paradigm": {"selected": str, "justification": str}
- "method": {"type": str, "specific": str, "justification": str}
- "data_strategy": {"type": str, "sources": list[str], "sampling": str, "time_frame": str}
- "analytical_framework": {"technique": str, "steps": list[str], "tools": list[str]}
- "validity_criteria": list[{"criterion": str, "strategy": str}]
- "limitations": list[{"issue": str, "mitigation": str}]
"""

_DEVILS_ADVOCATE_PROMPT = """\
You are the Devil's Advocate. You are the contrarian voice. Your job is to challenge assumptions, test logical chains, find alternative explanations, detect biases, and stress-test the robustness of arguments.

## Core Principles
1. Challenge everything — no assumption is too fundamental.
2. Steel-man before attack — understand the strongest version first.
3. Severity calibration — not everything is Critical.

## What to evaluate
Review the research question and methodology below. Apply these checks:

1. **Core Thesis Challenge**: What is the strongest counter-argument?
2. **Confirmation Bias Detection**: Are assumptions leading to a predetermined conclusion?
3. **Logic Chain Validation**: Does the conclusion follow from the premise?
4. **Overgeneralization Check**: Does the scope exceed what the data supports?
5. **Alternative Paths**: What overlooked approaches exist?
6. **"So What?" Test**: If the research succeeds, is the impact significant?

## Severity Classification
- **Critical**: Fatal flaw — invalidates core argument. BLOCKS progression.
- **Major**: Significant weakness — fixable with substantial revision.
- **Minor**: Small issue — doesn't affect core validity.

Return JSON only with these keys:
- "verdict": "PASS" | "REVISE"
- "critical_issues": list of {"title": str, "problem": str, "recommendation": str}
- "major_issues": list of {"title": str, "problem": str, "recommendation": str}
- "strongest_counter_argument": str
- "stress_test": {"remove_strongest_source": bool, "flip_research_question": bool, "so_what_test": bool}
"""


# ═══════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════

def _can_use_llm(config: LLMConfig | None) -> bool:
    if not config:
        return False
    base_url = (config.base_url or "").lower()
    return bool(config.api_key) or "localhost" in base_url or "127.0.0.1" in base_url


def _detect_intent(text: str) -> str:
    lowered = text.lower()
    if any(m in lowered for m in ["deadline", "submit", "submit", "deliverable", "我要写", "帮我规划", "投稿", "截止"]):
        return "goal_oriented"
    if any(m in lowered for m in ["不确定", "探索", "随便聊", "不知道", "why", "what if", "philosoph"]):
        return "exploratory"
    return "exploratory"


def _extract_insights(message: str) -> list[str]:
    tagged = re.findall(r"\[INSIGHT:\s*(.*?)\]", message, re.IGNORECASE | re.DOTALL)
    insights = [re.sub(r"\s+", " ", item).strip() for item in tagged if item.strip()]
    if not insights:
        markers = ["我意识到", "关键是", "真正的问题", "因此我认为", "这说明", "核心矛盾是", "本质上是"]
        if any(m in message for m in markers):
            insights.append(message.strip()[:280])
    return insights


def _extract_papers(message: str) -> list[str]:
    papers = re.findall(r"\b(?:arXiv:\s*)?\d{4}\.\d{4,5}\b|\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", message, re.IGNORECASE)
    quoted = re.findall(r"[《\"]([^》\"]{8,120})[》\"]", message)
    return [*papers, *quoted]


def _latest_rq(message: str) -> str:
    for marker in ["research question", "rq", "研究问题", "我想做", "我要研究", "目标是", "核心问题", "我关心"]:
        if marker in message:
            idx = message.find(marker)
            return message[idx:idx + 240].strip()
    if "?" in message or "？" in message:
        return re.split(r"[?？]", message)[0].strip()[:240]
    return ""


def _update_convergence(session: SocraticSession, message: str, new_insights: list[str]) -> None:
    rq = _latest_rq(message)
    if rq:
        session.rq_history.append(rq)
    # S1: Thesis clarity
    if rq and len(rq) > 15:
        session.convergence["s1"] = True
    # S2: Counterargument awareness
    if len(re.findall(r"(?:反论|反驳|质疑|limitation|weakness|threat|however|但是|不过|局限)", message, re.IGNORECASE)) >= 2:
        session.convergence["s2"] = True
    # S3: Methodology rationale
    if re.search(r"(?:because|why|rather than|instead of|而不是|原因|理由|局限|方法|method|approach)", message, re.IGNORECASE):
        session.convergence["s3"] = True
    # S4: Scope stability
    if len(session.rq_history) >= 3:
        recent = [set(re.findall(r"[\w\u4e00-\u9fff]+", item.lower())) for item in session.rq_history[-3:]]
        if recent[0] and len(recent[0] & recent[1] & recent[2]) >= 3:
            session.convergence["s4"] = True
    # S5: Self-calibration
    if new_insights and re.search(r"(?:我原来以为|现在看来|更准确|修正|calibrat|predict)", message, re.IGNORECASE):
        session.convergence["s5"] = True


def _convergence_count(session: SocraticSession) -> int:
    return sum(1 for v in session.convergence.values() if v)


def _should_advance_layer(session: SocraticSession) -> bool:
    """Determine if we should advance to the next layer."""
    turns = session.layer_turns.get(session.layer, 0)
    # Minimum 2 turns per layer
    if turns < 2:
        return False
    # Force advance after 5 turns in any single layer
    if turns >= 5:
        return True
    # Advance with 2+ convergence signals OR 3+ turns with no new insight
    if _convergence_count(session) >= 2:
        return True
    if turns >= 3 and session.no_insight_turns >= 2:
        return True
    return False


# ═══════════════════════════════════════════════════
# Main Public API
# ═══════════════════════════════════════════════════

async def create_session(project_id: str, provider: LLMProvider | None, config: LLMConfig | None, initial_message: str = "") -> str:
    session_id = str(uuid.uuid4())
    session = SocraticSession(session_id=session_id, project_id=project_id, intent=_detect_intent(initial_message))
    sessions[session_id] = session
    return session_id


async def handle_message(session_id: str, message: str, provider: LLMProvider | None, config: LLMConfig | None) -> dict:
    session = sessions.get(session_id)
    if not session or not session.is_active:
        return {"type": "error", "content": "Socratic session not found or inactive."}

    # Update session state
    session.turn_count += 1
    session.layer_turns[session.layer] = session.layer_turns.get(session.layer, 0) + 1
    session.messages.append({"role": "user", "content": message})

    if session.turn_count <= 2:
        texts = " ".join(m["content"] for m in session.messages if m["role"] == "user")
        session.intent = _detect_intent(texts)

    new_insights = _extract_insights(message)
    for insight in new_insights:
        if insight not in session.insights:
            session.insights.append(insight)
    session.no_insight_turns = 0 if new_insights else session.no_insight_turns + 1
    session.papers.extend(p for p in _extract_papers(message) if p not in session.papers)
    _update_convergence(session, message, new_insights)

    # Check for layer advance
    if _should_advance_layer(session) and session.layer < 5:
        next_layer = session.layer + 1
        transcript = "\n".join(
            f"{'User' if m['role'] == 'user' else 'Mentor'}: {m['content']}"
            for m in session.messages[-6:]
        )
        if provider and _can_use_llm(config):
            response = await _llm_advance_layer(session, next_layer, transcript, provider, config)
        else:
            response = f"我们进入下一层：{LAYER_NAMES[next_layer]}。\n\n{_fallback_question(next_layer, 0, session)}"
        session.layer = next_layer
        session.messages.append({"role": "assistant", "content": response})
        return {"type": "transition", "content": response, **_session_payload(session)}

    # Check convergence for auto-completion (all 5 layers done)
    if session.layer >= 5 and _convergence_count(session) >= 3:
        session.is_active = False
        summary = await generate_summary(session_id, provider, config)
        response = "五层讨论已收敛，已生成 Research Plan Summary。"
        session.messages.append({"role": "assistant", "content": response})
        return {
            "type": "converged",
            "content": response,
            "summary": summary,
            **_session_payload(session),
        }

    # Generate Socratic response
    if provider and _can_use_llm(config):
        response = await _llm_generate_response(session, message, provider, config)
    else:
        response = _fallback_question(session.layer, session.layer_turns.get(session.layer, 0), session)

    if session.no_insight_turns > 10 and session.turn_count > 12:
        response += "\n\n---\n\n你已经超过 10 轮没有形成新 INSIGHT，建议切换到 full 模式直接生成研究计划草案。"

    # Also extract INSIGHT tags from the assistant's response itself,
    # since the LLM is trained to tag [INSIGHT: ...] for user ideas
    assistant_insights = _extract_insights(response)
    for insight in assistant_insights:
        if insight not in session.insights:
            session.insights.append(insight)
    if assistant_insights:
        session.no_insight_turns = 0

    session.messages.append({"role": "assistant", "content": response})
    response_type = "insight" if new_insights else "question"
    return {"type": response_type, "content": response, **_session_payload(session)}


async def _llm_generate_response(
    session: SocraticSession,
    message: str,
    provider: LLMProvider,
    config: LLMConfig,
) -> str:
    """Generate a context-aware Socratic response using the ARS-adapted prompt."""
    max_rounds = 40 if session.intent == "goal_oriented" else 60

    transcript = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Mentor'}: {m['content']}"
        for m in session.messages[-8:]
    )

    active_conv = [k for k, v in session.convergence.items() if v]

    prompt = f"""Current layer: {session.layer}/5 — {LAYER_NAMES[session.layer]}
Turn count: {session.turn_count} / max {max_rounds} ({session.intent})
Turns in current layer: {session.layer_turns.get(session.layer, 0)}
Active convergence signals: {active_conv if active_conv else 'none yet'}
INSIGHT count: {len(session.insights)}

Recent transcript:
{transcript}

User's latest message:
{message}

---

Generate the next mentor response in Chinese following the Socratic Mentor protocol.
Acknowledge what the user said first, then ask 1-2 specific follow-up questions.
Be natural — probe for concrete details, not abstractions.
"""

    try:
        return await provider.chat([
            ChatMessage(role="system", content=_SOCRATIC_SYSTEM_PROMPT),
            ChatMessage(role="user", content=prompt),
        ], config)
    except Exception as exc:
        logger.warning("socratic_agent.py operation failed: {}", exc)
        return _fallback_question(session.layer, session.layer_turns.get(session.layer, 0), session)


async def _llm_advance_layer(
    session: SocraticSession,
    next_layer: int,
    transcript: str,
    provider: LLMProvider,
    config: LLMConfig,
) -> str:
    """Generate a layer transition message."""
    prompt = f"""The user is ready to advance from Layer {session.layer} ({LAYER_NAMES[session.layer]}) to Layer {next_layer} ({LAYER_NAMES[next_layer]}).

First, write a 1-2 sentence summary of what was discussed in the current layer, referencing the user's own words.
Then, naturally introduce the next layer with a question.

Keep it under 150 words. Do not propose solutions — ask.

Recent transcript:
{transcript[-2000:]}
"""
    try:
        return await provider.chat([
            ChatMessage(role="system", content=_SOCRATIC_SYSTEM_PROMPT),
            ChatMessage(role="user", content=prompt),
        ], config)
    except Exception as exc:
        logger.warning("socratic_agent.py operation failed: {}", exc)
        return f"我们进入下一层：{LAYER_NAMES[next_layer]}。\n\n{_fallback_question(next_layer, 0, session)}"


def _fallback_question(layer: int, turn: int, session: SocraticSession) -> str:
    """Fallback when LLM is unavailable."""
    base = {
        1: [
            "用一句话说说你现在最想研究的问题是什么。不用太精确，先说你最关心什么。",
            "你说的很有意思。能描述一下场景边界吗？比如涉及多少设备、多大范围、什么条件？",
        ],
        2: [
            "你打算用什么方法来回答这个研究问题？为什么选这个方法而不是别的？",
            "这个方法最容易出问题的地方在哪？你准备怎么应对？",
        ],
        3: [
            "要说服审稿人，你需要什么类型的证据？数据从哪里来？",
            "你会用什么基准(Baseline)来对比你的结果？",
        ],
        4: [
            "如果审稿人不同意你的结论，他最可能抓住哪一点？",
            "你的研究最可能被质疑的两个限制是什么？",
        ],
        5: [
            "假设你做成了，这项研究对谁有具体价值？",
            "如果贡献只能写成一句话，你会怎么写？",
        ],
    }
    questions = base.get(layer, base[1])
    idx = min(turn, len(questions) - 1) if turn < len(questions) else -1
    q = questions[idx] if idx >= 0 else questions[-1]
    # Add context from session if available
    if session.rq_history:
        context = session.rq_history[-1][:60]
        q = f"从你说的「{context}」出发，{q}"
    return q


# ═══════════════════════════════════════════════════
# Research Question Agent — FINER RQ Generation
# ═══════════════════════════════════════════════════

async def generate_research_question(
    session_id: str,
    provider: LLMProvider | None,
    config: LLMConfig | None,
) -> dict:
    """Generate a FINER-scored research question from the Socratic dialogue."""
    session = sessions.get(session_id)
    if not session:
        return {"error": "Socratic session not found"}

    user_text = "\n".join(m["content"] for m in session.messages if m["role"] == "user")
    fallback = {
        "primary_rq": session.rq_history[-1] if session.rq_history else "待定 Research Question",
        "finer_scores": {"feasible": 3, "interesting": 3, "novel": 3, "ethical": 3, "relevant": 3},
        "in_scope": [], "out_of_scope": [], "sub_questions": [],
        "insights": session.insights,
    }

    if not provider or not _can_use_llm(config):
        return fallback

    prompt = f"""Conversation transcript:
{user_text[-10000:]}

INSIGHT tags: {session.insights[-10:]}

{_RQ_GENERATION_PROMPT}

Generate the FINER-scored research question based on the conversation above.
"""
    try:
        raw = await provider.chat([
            ChatMessage(role="system", content="You generate precise, FINER-scored research questions."),
            ChatMessage(role="user", content=prompt),
        ], config)
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if match:
            parsed = json.loads(match.group(1))
        else:
            parsed = json.loads(raw.strip())
        parsed["insights"] = session.insights
        return parsed
    except Exception as exc:
        logger.warning("socratic_agent.py operation failed: {}", exc)
        return fallback


# ═══════════════════════════════════════════════════
# Research Architect — Methodology Blueprint
# ═══════════════════════════════════════════════════

async def generate_methodology_blueprint(
    rq: str,
    context: str = "",
    provider: LLMProvider | None = None,
    config: LLMConfig | None = None,
) -> dict:
    """Generate a methodology blueprint from the research question."""
    fallback = {
        "paradigm": {"selected": "待定", "justification": "需要更多上下文"},
        "method": {"type": "待定", "specific": "待定", "justification": ""},
        "data_strategy": {"type": "待定", "sources": [], "sampling": "", "time_frame": ""},
        "analytical_framework": {"technique": "待定", "steps": [], "tools": []},
        "validity_criteria": [],
        "limitations": [],
    }

    if not provider or not _can_use_llm(config):
        return fallback

    prompt = f"""{_METHODOLOGY_BLUEPRINT_PROMPT}

Research question:
{rq}

Context:
{context[:3000]}

Generate a methodology blueprint for this research question.
"""
    try:
        raw = await provider.chat([
            ChatMessage(role="system", content="You design methodological blueprints for CS research projects."),
            ChatMessage(role="user", content=prompt),
        ], config)
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        return json.loads(match.group(1) if match else raw)
    except Exception as exc:
        logger.warning("socratic_agent.py operation failed: {}", exc)
        return fallback


# ═══════════════════════════════════════════════════
# Devil's Advocate — Stress-test Checkpoint
# ═══════════════════════════════════════════════════

async def run_devils_advocate(
    rq: str,
    methodology: dict | str = "",
    provider: LLMProvider | None = None,
    config: LLMConfig | None = None,
) -> dict:
    """Stress-test a research question and methodology."""
    fallback = {
        "verdict": "PASS",
        "critical_issues": [],
        "major_issues": [{"title": "自动检查不可用", "problem": "LLM 不可用", "recommendation": "手动审查"}],
        "strongest_counter_argument": "",
        "stress_test": {"remove_strongest_source": False, "flip_research_question": False, "so_what_test": False},
    }

    if not provider or not _can_use_llm(config):
        return fallback

    meth_str = json.dumps(methodology, ensure_ascii=False) if isinstance(methodology, dict) else str(methodology)
    prompt = f"""{_DEVILS_ADVOCATE_PROMPT}

Research question:
{rq}

Methodology:
{meth_str[:4000]}

Run a stress-test on this research plan and return structured JSON.
"""
    try:
        raw = await provider.chat([
            ChatMessage(role="system", content="You are a rigorous Devil's Advocate for CS research."),
            ChatMessage(role="user", content=prompt),
        ], config)
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        return json.loads(match.group(1) if match else raw)
    except Exception as exc:
        logger.warning("socratic_agent.py operation failed: {}", exc)
        return fallback


# ═══════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════

async def generate_summary(session_id: str, provider: LLMProvider | None, config: LLMConfig | None) -> dict:
    session = sessions.get(session_id)
    if not session:
        return {"error": "Socratic session not found"}

    user_text = "\n".join(m["content"] for m in session.messages if m["role"] == "user")
    fallback = {
        "research_question": session.rq_history[-1] if session.rq_history else "待定",
        "methodology": "根据对话补全方法选择。",
        "evidence_plan": "列出数据、baseline 和检索策略。",
        "insights": session.insights,
        "convergence": session.convergence,
        "turn_count": session.turn_count,
    }

    if not provider or not _can_use_llm(config):
        session.summary = fallback
        return fallback

    prompt = f"""Generate a Research Plan Summary from this Socratic mentoring transcript.
Return JSON: research_question, methodology, evidence_plan, limitations, significance, insights (array).

Transcript:
{user_text[-12000:]}

Convergence: {session.convergence}
"""
    try:
        raw = await provider.chat([
            ChatMessage(role="system", content="You summarize research plans as structured JSON."),
            ChatMessage(role="user", content=prompt),
        ], config)
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        parsed = json.loads(match.group(1) if match else raw)
        parsed["insights"] = parsed.get("insights") or session.insights
        parsed["convergence"] = session.convergence
        parsed["turn_count"] = session.turn_count
        session.summary = parsed
        return parsed
    except Exception as exc:
        logger.warning("socratic_agent.py operation failed: {}", exc)
        session.summary = fallback
        return fallback


def _session_payload(session: SocraticSession) -> dict:
    return {
        "session_id": session.session_id,
        "layer": session.layer,
        "layer_name": LAYER_NAMES.get(session.layer, ""),
        "insights": list(session.insights),
        "convergence": dict(session.convergence),
        "turn_count": session.turn_count,
        "intent": session.intent,
        "is_active": session.is_active,
        "suggest_full_mode": session.no_insight_turns > 10,
    }


def _session_title(session: SocraticSession) -> str:
    if session.title.strip():
        return session.title.strip()[:255]
    if session.summary:
        research_question = str(session.summary.get("research_question") or "").strip()
        if research_question:
            return research_question[:255]
    first_user_message = next(
        (str(message.get("content") or "").strip() for message in session.messages if message.get("role") == "user"),
        "",
    )
    return (first_user_message or "Socratic Session")[:255]


def _ensure_project(db: Session, project_id: str | None) -> str | None:
    if not project_id:
        return None
    if db.get(Project, project_id) is None:
        db.add(Project(
            id=project_id,
            name="Default" if project_id == "default" else project_id,
            description="Auto-created project for Socratic history.",
        ))
        db.flush()
    return project_id


def save_to_db(session_id: str, db: Session, *, end_session: bool = False) -> SocraticSessionModel:
    """Persist one in-memory session, replacing its message and insight snapshots."""
    session = sessions.get(session_id)
    if session is None:
        raise KeyError(session_id)
    if end_session:
        session.is_active = False

    record = db.get(SocraticSessionModel, session_id)
    if record is None:
        record = SocraticSessionModel(id=session_id)
        db.add(record)

    record.project_id = _ensure_project(db, session.project_id)
    record.title = _session_title(session)
    record.updated_at = datetime.now(timezone.utc)
    record.intent = session.intent
    record.layer = session.layer
    record.turn_count = session.turn_count
    record.is_converged = not session.is_active
    record.summary_json = session.summary
    record.convergence_json = dict(session.convergence)
    record.insights_list = list(session.insights)
    record.layer_turns_json = {str(key): value for key, value in session.layer_turns.items()}
    record.rq_history_json = list(session.rq_history)
    record.active_turn_index = len(session.messages) - 1 if session.is_active and session.messages else None

    # Persist the parent row before inserting snapshots that reference it.
    db.flush()

    db.query(SocraticMessageModel).filter(SocraticMessageModel.session_id == session_id).delete(synchronize_session=False)
    db.query(SocraticInsightModel).filter(SocraticInsightModel.session_id == session_id).delete(synchronize_session=False)
    for index, message in enumerate(session.messages):
        role = str(message.get("role") or "")
        message_content = str(message.get("content") or "")
        if role not in {"user", "assistant"} or not message_content:
            continue
        db.add(SocraticMessageModel(
            session_id=session_id,
            role=role,
            content=message_content,
            turn_index=index,
        ))
    for index, insight in enumerate(session.insights):
        turn_index = next(
            (
                message_index
                for message_index, message in enumerate(session.messages)
                if str(insight) in str(message.get("content") or "")
            ),
            index,
        )
        db.add(SocraticInsightModel(
            session_id=session_id,
            content=str(insight),
            turn_index=turn_index,
        ))

    db.commit()
    db.refresh(record)
    session.title = record.title or ""
    return record


def load_from_db(session_id: str, db: Session) -> SocraticSession | None:
    """Restore a persisted session into memory as a read-only history snapshot."""
    record = db.get(SocraticSessionModel, session_id)
    if record is None:
        return None
    message_rows = (
        db.query(SocraticMessageModel)
        .filter(SocraticMessageModel.session_id == session_id)
        .order_by(SocraticMessageModel.turn_index.asc())
        .all()
    )
    insight_rows = (
        db.query(SocraticInsightModel)
        .filter(SocraticInsightModel.session_id == session_id)
        .order_by(SocraticInsightModel.turn_index.asc())
        .all()
    )
    layer_turns = {
        int(key): int(value)
        for key, value in (record.layer_turns_json or {}).items()
        if str(key).isdigit()
    }
    session = SocraticSession(
        session_id=record.id,
        project_id=record.project_id or "default",
        layer=record.layer or 1,
        turn_count=record.turn_count or 0,
        insights=list(record.insights_list or [row.content for row in insight_rows]),
        intent=record.intent or "exploratory",
        convergence=dict(record.convergence_json or {}),
        layer_turns=layer_turns or {i: 0 for i in range(1, 6)},
        is_active=False,
        messages=[{"role": row.role, "content": row.content} for row in message_rows],
        rq_history=list(record.rq_history_json or []),
        title=record.title or "",
        summary=dict(record.summary_json) if isinstance(record.summary_json, dict) else None,
    )
    sessions[session_id] = session
    return session


def session_history_payload(session: SocraticSession) -> dict:
    return {
        **_session_payload(session),
        "title": _session_title(session),
        "messages": list(session.messages),
        "summary": session.summary,
    }
