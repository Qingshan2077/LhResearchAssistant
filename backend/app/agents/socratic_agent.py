"""Socratic mentor for multi-turn research idea development."""

import json
import re
import uuid
from dataclasses import asdict, dataclass, field

from app.llm import ChatMessage, LLMConfig, LLMProvider


@dataclass
class SocraticSession:
    session_id: str
    project_id: str
    layer: int = 1
    turn_count: int = 0
    insights: list[str] = field(default_factory=list)
    intent: str = "exploratory"
    convergence: dict = field(default_factory=lambda: {"s1": False, "s2": False, "s3": False, "s4": False, "s5": False})
    layer_turns: dict[int, int] = field(default_factory=lambda: {1: 0, 2: 0, 3: 0, 4: 0, 5: 0})
    papers: list[str] = field(default_factory=list)
    probe_fired: bool = False
    is_active: bool = True
    messages: list[dict] = field(default_factory=list)
    rq_history: list[str] = field(default_factory=list)
    no_insight_turns: int = 0
    forced_advance: bool = False


sessions: dict[str, SocraticSession] = {}


LAYER_NAMES = {
    1: "1. 问题定义（Clarification）",
    2: "2. 方法论反思（Probing Assumptions）",
    3: "3. 证据策略（Evidence & Reasoning）",
    4: "4. 批判性自省（Critical Self-Examination）",
    5: "5. 贡献与意义（Significance）",
}

LAYER_DESCRIPTIONS = {
    1: '帮用户从模糊想法变成一个可回答的研究问题。你擅长追问场景边界，而不是空泛地重复宽泛问题。问具体细节，而不是让用户反复说同一件事。',
    2: '帮用户思考怎么回答研究问题。你需要检查方法选择背后的假设：为什么用这种方法而不是其他？弱点在哪？适用边界在哪？',
    3: '帮用户设计证据策略。需要什么数据？怎么搜索？怎么排除最直接的替代解释？',
    4: '帮用户诚实面对研究局限。最可能被审稿人攻击的点在哪？最坏情况是什么？',
    5: '帮用户说清楚\u201c所以呢？\u201d。这项研究对谁产生什么价值？',
}

WORDING_PATTERNS = [
    r"explor(?:e|ing) the (?:impact|effect) of .+ on .+",
    r"investigat(?:e|ing) the relationship between .+ and .+",
    r"examining the role of .+ in .+",
    r"challenges and opportunities of .+ in .+",
    r"toward(?:s)? a (?:framework|model) for .+",
    r"a comprehensive review of .+",
    r"leveraging .+ for .+",
    r"enhancing .+ with .+",
    r"understanding .+ in the age of .+",
    r"the future of .+",
    r"bridging the gap between .+ and .+",
    r"rethinking .+ for .+",
    r"unified framework for .+",
    r"novel approach to .+",
    r"scalable and efficient .+",
    r"robust .+ in .+ settings",
    r"trustworthy .+ for .+",
    r"human centered .+",
    r"data driven .+",
    r"ai powered .+",
]


def _can_use_llm(config: LLMConfig | None) -> bool:
    if not config:
        return False
    base_url = (config.base_url or "").lower()
    return bool(config.api_key) or "localhost" in base_url or "127.0.0.1" in base_url


def _detect_intent(text: str) -> str:
    lowered = text.lower()
    goal_markers = ["deadline", "submit", "submission", "deliverable", "我要写", "帮我规划", "投稿", "截止"]
    exploratory_markers = ["不确定", "探索", "随便聊", "不知道", "why", "what if"]
    if any(marker in lowered for marker in goal_markers):
        return "goal_oriented"
    if any(marker in lowered for marker in exploratory_markers):
        return "exploratory"
    return "exploratory"


def _extract_insights(message: str) -> list[str]:
    tagged = re.findall(r"\[INSIGHT:\s*(.*?)\]", message, re.IGNORECASE | re.DOTALL)
    insights = [re.sub(r"\s+", " ", item).strip() for item in tagged if item.strip()]
    if not insights:
        markers = ["我意识到", "关键是", "真正的问题", "因此我认为", "这说明", "核心矛盾是", "本质上是"]
        for marker in markers:
            if marker in message:
                insights.append(message.strip()[:280])
                break
    return insights


def _extract_papers(message: str) -> list[str]:
    papers = re.findall(r"\b(?:arXiv:\s*)?\d{4}\.\d{4,5}\b|\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", message, re.IGNORECASE)
    quoted = re.findall(r"[《\"]([^》\"]{8,120})[》\"]", message)
    return [*papers, *quoted]


def _update_convergence(session: SocraticSession, message: str, new_insights: list[str]) -> None:
    """Update S1-S5 convergence signals based on user's message."""
    # S1: Thesis clarity — user states a clear, specific research question
    rq_markers = ["研究问题", "希望回答", "我想做的是", "核心是", "问题在于", "目标是"]
    for marker in rq_markers:
        if marker in message:
            session.convergence["s1"] = True
            break
    if len(message) > 30 and "?" not in message and "？" not in message:
        # User is making a statement, not asking a question — likely answering the RQ prompt
        words = len(re.findall(r"[\w\u4e00-\u9fff]+", message))
        if words >= 6:
            session.convergence["s1"] = True

    # S2: Counterargument awareness
    counter_markers = re.findall(r"(?:反论|反驳|质疑|limitation|weakness|threat|however|但是|不过|局限)", message, re.IGNORECASE)
    if len(counter_markers) >= 2 or len(re.findall(r"(?:第一|第二|1\.|2\.)", message)) >= 2:
        session.convergence["s2"] = True

    # S3: Methodology rationale
    if re.search(r"(?:because|why|rather than|instead of|而不是|原因|理由|局限|方法|method|approach)", message, re.IGNORECASE):
        session.convergence["s3"] = True

    # S4: Scope stability
    rq = _latest_rq(message)
    if rq:
        session.rq_history.append(rq)
    if len(session.rq_history) >= 3:
        recent = [item.lower() for item in session.rq_history[-3:]]
        tokens = [set(re.findall(r"[\w\u4e00-\u9fff]+", item)) for item in recent]
        if tokens[0] and len(tokens[0] & tokens[1] & tokens[2]) >= 3:
            session.convergence["s4"] = True

    # S5: Self-calibration
    if new_insights and re.search(r"(?:我原来以为|现在看来|更准确|修正|calibrat|predict)", message, re.IGNORECASE):
        session.convergence["s5"] = True


def _latest_rq(message: str) -> str:
    """Extract research question from a user message."""
    match = re.search(r"(?:research question|rq|研究问题)[:：]\s*(.+)", message, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    if "?" in message or "？" in message:
        return re.split(r"[?？]", message)[0].strip()[:240]
    # Also extract if message is a statement about what they want to research
    for marker in ["我想做", "我要研究", "目标是", "核心问题", "我关心"]:
        if marker in message:
            idx = message.find(marker)
            return message[idx:idx + 240].strip()
    return ""


def _active_convergence_count(session: SocraticSession) -> int:
    return sum(1 for v in session.convergence.values() if v)


def _should_force_advance(session: SocraticSession) -> bool:
    """Force advance if user has engaged meaningfully but layer exit never triggered."""
    turns = session.layer_turns.get(session.layer, 0)
    # After 4+ turns in the same layer, force advance
    if turns >= 4:
        return True
    # After 3 turns with no new insight AND at least 1 convergence signal
    if turns >= 3 and session.no_insight_turns >= 2 and _active_convergence_count(session) >= 1:
        return True
    return False


def _wording_advisory(message: str) -> str:
    lowered = message.lower()
    for pattern in WORDING_PATTERNS:
        if re.search(pattern, lowered):
            return "[WORDING_PATTERN_ADVISORY] 这个研究问题像通用 AI 句式。建议换成本领域术语，明确对象、机制、数据和评价指标。"
    return ""


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

    # Determine response
    if provider and _can_use_llm(config):
        # Primary path: LLM generates context-aware response from scratch
        content = await _generate_llm_response(session, message, provider, config)
    else:
        # Fallback: use templated questions
        content = _fallback_question(session, message)

    # Check convergence for auto-completion
    if session.layer >= 5:
        active = _active_convergence_count(session)
        if active >= 3:
            session.is_active = False
            summary = await generate_summary(session_id, provider, config)
            # Include the last response before converging
            session.messages.append({"role": "assistant", "content": content})
            return {
                "type": "converged",
                "content": content + "\n\n---\n\n五层讨论已收敛，已生成 Research Plan Summary。",
                "summary": summary,
                **_session_payload(session),
            }

    if session.no_insight_turns > 10 and session.turn_count > 12:
        content += "\n\n---\n\n你已经超过 10 轮没有形成新 INSIGHT，建议切换到 full 模式直接生成研究计划草案。"

    session.messages.append({"role": "assistant", "content": content})
    response_type = "question"
    if new_insights:
        response_type = "insight"

    return {"type": response_type, "content": content, **_session_payload(session)}


_SOCRATIC_SYSTEM_PROMPT = """\
You are a Socratic Mentor — a Q1 journal editor-in-chief with 20+ years of academic experience.
You guide researchers through clarifying their research thinking. You NEVER give direct answers.
Instead, you lead with precise, layered questions that help users discover their own insights.

Identity: Editor-in-chief of a Q1 international journal with cross-disciplinary expertise.
Tone: Like a senior advisor chatting with a doctoral student — warm but precise, friendly not casual.

Core rules:
1. **Never give direct conclusions.** Guide through questions, even when you know the answer.
2. **Response structure:** First acknowledge what the user said (1-2 sentences of sincere understanding).
   Then ask 1-2 focused follow-up questions. Keep total response to 2-4 short paragraphs.
3. **Variety of questions:** Mix clarifying, probing, structuring, and challenging questions.
   Do NOT repeat the same question multiple times or the same pattern.
4. **Listen to what the user already answered.** If they gave a clear answer, don't ask the same question again — build on it.
5. **Probe specifics, not abstractions.** Ask about concrete details: how many? how often? under what conditions? compared to what?
6. **Don't ask the user to "choose one variable" repeatedly.** That's not Socratic mentoring.
7. **Only advance layers when genuinely ready.** A good answer deserves a deeper follow-up in the same layer.
   Don't rush to the next layer just because a minimum turn count is met.
"""


async def _generate_llm_response(
    session: SocraticSession,
    message: str,
    provider: LLMProvider,
    config: LLMConfig | None,
) -> str:
    """Generate a context-aware Socratic response using LLM."""

    if not config:
        return _fallback_question(session, message)

    # Check if we should advance layer
    at_convergence = _active_convergence_count(session) >= 2
    force_advance = _should_force_advance(session)

    transcript = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Mentor'}: {m['content']}"
        for m in session.messages[-8:]
    )

    user_goal = ""
    if session.rq_history:
        user_goal = session.rq_history[-1]

    prompt = f"""You are in Layer {session.layer}: {LAYER_NAMES[session.layer]}

Layer goal: {LAYER_DESCRIPTIONS[session.layer]}

User's research area: {session.rq_history[-1] if session.rq_history else 'Not yet articulated'}
Session turns: {session.turn_count}
Turns in current layer: {session.layer_turns.get(session.layer, 0)}
Convergence signals: {[k for k, v in session.convergence.items() if v]}
Insights so far: {session.insights[-3:]}
Intent: {session.intent}

{'[CONVERGENCE DETECTED] Consider advancing to next layer soon.' if at_convergence else ''}
{'[FORCE ADVANCE] User has been in this layer too long. Advance to next layer.' if force_advance else ''}

Recent transcript:
{transcript}

User's latest message:
{message}

---

Based on the transcript above, write the next mentor response in Chinese.
Follow the Socratic rules: acknowledge what the user said, then ask 1-2 specific follow-up questions.
Do NOT repeat a question the user already answered.
Do NOT ask the user to "choose one variable" — that was already answered.
Probe concrete details that the user HASN'T shared yet.
Keep each question specific and grounded in the user's actual research context (AGV scheduling, warehouse layout, etc.).
"""

    if force_advance and session.layer < 5:
        next_layer = session.layer + 1
        prompt += f"\n\nThe user seems to have exhausted the current layer. Prepare a concise summary of what was discussed in Layer {session.layer}, then naturally transition to Layer {next_layer}: {LAYER_NAMES[next_layer]}. Use the transition to build on what the user has already said, don't start from scratch."

    try:
        return await provider.chat([
            ChatMessage(role="system", content=_SOCRATIC_SYSTEM_PROMPT),
            ChatMessage(role="user", content=prompt),
        ], config)
    except Exception:
        return _fallback_question(session, message)


def _fallback_question(session: SocraticSession, message: str) -> str:
    """Fallback when LLM is unavailable — use templated questions."""
    advisory = _wording_advisory(message)

    if session.forced_advance:
        session.forced_advance = False
        if session.layer < 5:
            session.layer += 1
            return f"我们进入下一层：{LAYER_NAMES[session.layer]}。\n\n{_get_user_context_note(session)}"

    # Check if stuck — force advance after 4 turns
    if session.layer_turns.get(session.layer, 0) >= 4 and session.layer < 5:
        session.forced_advance = True
        return f"看起来这一层我们聊得差不多了。我想推进到下一层看看你的想法。\n\n{_get_user_context_note(session, include_transition=True)}"

    if session.layer == 1:
        if session.layer_turns.get(session.layer, 0) <= 1:
            q = "用一句话说说你现在最想研究的问题是什么。不用太精确，先用你自己的话表达。"
        else:
            q = f"你说的「{message[:60]}」很有意思。能多描述一下场景边界吗？比如涉及多少台设备、多大规模的仓库、多少订单量？"
    elif session.layer == 2:
        questions = [
            "你打算用什么方法来回答这个研究问题？为什么选这个方法而不是别的？",
            "这个方法最容易出问题的地方在哪？你准备怎么应对？",
        ]
        idx = min(session.layer_turns.get(session.layer, 0) - 1, len(questions) - 1)
        q = questions[idx]
    elif session.layer == 3:
        q = "要说服审稿人，你需要什么类型的证据？数据从哪里来？"
    elif session.layer == 4:
        q = "你最怕审稿人质疑你哪个环节？那个质疑合理吗？"
    elif session.layer == 5:
        q = "假设你做成了，这项研究对谁有具体价值？一句话说得清吗？"
    else:
        q = "继续说说你的想法，目前进展到哪里了？"

    if advisory:
        q = f"{advisory}\n\n{q}"
    return q


def _get_user_context_note(session: SocraticSession, include_transition: bool = False) -> str:
    """Generate a brief note about what the user has said, to maintain continuity."""
    if session.rq_history:
        return f"从你之前说的「{session.rq_history[-1]}」出发，我们来换个角度思考。"
    return ""


async def generate_summary(session_id: str, provider: LLMProvider | None, config: LLMConfig | None) -> dict:
    session = sessions.get(session_id)
    if not session:
        return {"error": "Socratic session not found"}

    user_text = "\n".join(m["content"] for m in session.messages if m["role"] == "user")
    fallback = {
        "research_question": session.rq_history[-1] if session.rq_history else "待定 Research Question",
        "methodology": "根据对话补全方法选择、对照方案和局限。",
        "evidence_plan": "列出数据、baseline、ablation 和检索策略。",
        "insights": session.insights,
        "convergence": session.convergence,
        "intent": session.intent,
        "turn_count": session.turn_count,
    }

    if not provider or not _can_use_llm(config):
        return fallback

    prompt = f"""Generate a Research Plan Summary from this Socratic mentoring transcript.
Return JSON with keys: research_question (string), methodology (string), evidence_plan (string), limitations (string), significance (string), insights (array).

Transcript:
{user_text[-12000:]}

Convergence:
{session.convergence}
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
        parsed["intent"] = session.intent
        parsed["turn_count"] = session.turn_count
        return parsed
    except Exception:
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
