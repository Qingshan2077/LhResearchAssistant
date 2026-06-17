"""Socratic mentor for multi-turn research idea development."""

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
    pending_gate: bool = False


sessions: dict[str, SocraticSession] = {}


LAYER_NAMES = {
    1: "Problem Framing",
    2: "Methodology Reflection",
    3: "Evidence Design",
    4: "Critical Self-Examination",
    5: "Significance",
}

LAYER_QUESTIONS = {
    1: [
        "你现在最想回答的研究问题是什么？先试着用一句话说清楚。",
        "如果只能保留一个核心变量或机制，你会保留哪一个？为什么？",
    ],
    2: [
        "你打算怎么回答这个问题？先说方法，再说为什么不是别的方法。",
        "这个方法最容易失效的地方在哪里？你准备如何处理？",
    ],
    3: [
        "你需要什么证据才能说服一个严格的审稿人？",
        "你会用什么搜索策略、数据集或实验来排除最直接的替代解释？",
    ],
    4: [
        "你的研究最可能被质疑的两个限制是什么？",
        "如果审稿人不同意你的结论，他最可能抓住哪一点？",
    ],
    5: [
        "所以呢？这项研究对领域里的谁产生什么具体价值？",
        "如果贡献只能写成一句话，你会怎样写？",
    ],
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
    exploratory_markers = ["不确定", "探索", "随便聊", "不知道", "why", "what if", "philosoph"]
    if any(marker in lowered for marker in goal_markers):
        return "goal_oriented"
    if any(marker in lowered for marker in exploratory_markers):
        return "exploratory"
    return "exploratory"


def _extract_insights(message: str) -> list[str]:
    tagged = re.findall(r"\[INSIGHT:\s*(.*?)\]", message, re.IGNORECASE | re.DOTALL)
    insights = [re.sub(r"\s+", " ", item).strip() for item in tagged if item.strip()]
    if not insights:
        markers = ["我意识到", "关键是", "真正的问题", "因此我认为", "这说明"]
        for marker in markers:
            if marker in message:
                insights.append(message.strip()[:280])
                break
    return insights


def _extract_papers(message: str) -> list[str]:
    papers = re.findall(r"\b(?:arXiv:\s*)?\d{4}\.\d{4,5}\b|\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", message, re.IGNORECASE)
    quoted = re.findall(r"[《\"]([^《》\"]{8,120})[》\"]", message)
    return [*papers, *quoted]


def _latest_rq(message: str) -> str:
    match = re.search(r"(?:research question|rq|研究问题)[:：]\s*(.+)", message, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    if "?" in message or "？" in message:
        return re.split(r"[?？]", message)[0].strip()[:240]
    return ""


def _update_convergence(session: SocraticSession, message: str, new_insights: list[str]) -> None:
    rq = _latest_rq(message)
    if rq:
        session.rq_history.append(rq)
    if rq and 18 <= len(rq) <= 240:
        session.convergence["s1"] = True

    counter_markers = re.findall(r"(?:反论|反驳|质疑|limitation|weakness|threat|however|但是|不过)", message, re.IGNORECASE)
    if len(counter_markers) >= 2 or len(re.findall(r"(?:第一|第二|1\.|2\.)", message)) >= 2:
        session.convergence["s2"] = True

    if re.search(r"(?:because|why|rather than|instead of|而不是|原因|理由|局限)", message, re.IGNORECASE):
        session.convergence["s3"] = True

    if len(session.rq_history) >= 3:
        recent = [item.lower() for item in session.rq_history[-3:]]
        tokens = [set(re.findall(r"\w+", item)) for item in recent]
        if tokens[0] and len(tokens[0] & tokens[1] & tokens[2]) >= 3:
            session.convergence["s4"] = True

    if new_insights and re.search(r"(?:我原来以为|现在看来|更准确|修正|calibrat|predict)", message, re.IGNORECASE):
        session.convergence["s5"] = True


def _layer_exit_ready(session: SocraticSession, message: str) -> bool:
    if session.layer_turns.get(session.layer, 0) < 2:
        return False
    if session.layer == 1:
        return session.convergence["s1"]
    if session.layer == 2:
        return session.convergence["s3"]
    if session.layer == 3:
        return bool(re.search(r"(?:证据|搜索|数据|实验|baseline|dataset|ablation)", message, re.IGNORECASE))
    if session.layer == 4:
        return session.convergence["s2"]
    if session.layer == 5:
        return bool(re.search(r"(?:贡献|意义|value|impact|contribution|so what)", message, re.IGNORECASE))
    return False


def _wording_advisory(message: str) -> str:
    lowered = message.lower()
    for pattern in WORDING_PATTERNS:
        if re.search(pattern, lowered):
            return "[WORDING_PATTERN_ADVISORY] 这个研究问题像通用 AI 句式。建议换成本领域术语，明确对象、机制、数据和评价指标。"
    return ""


def _fallback_question(session: SocraticSession, message: str) -> str:
    advisory = _wording_advisory(message)
    questions = LAYER_QUESTIONS.get(session.layer, LAYER_QUESTIONS[1])
    question = questions[session.layer_turns.get(session.layer, 0) % len(questions)]
    if session.pending_gate:
        question = f"在进入 {LAYER_NAMES.get(session.layer + 1, '下一层')} 前，先承诺一个具体做法：你接下来会怎么验证刚才的判断？"
    elif session.probe_fired:
        question = f"我给你一个反向检验：如果一篇强相关论文得出相反结论，你的研究问题还成立吗？{question}"
    if advisory:
        question = f"{advisory}\n\n{question}"
    return question


async def create_session(project_id: str, provider: LLMProvider | None, config: LLMConfig | None, initial_message: str = "") -> str:
    session_id = str(uuid.uuid4())
    session = SocraticSession(session_id=session_id, project_id=project_id, intent=_detect_intent(initial_message))
    sessions[session_id] = session
    return session_id


async def handle_message(session_id: str, message: str, provider: LLMProvider | None, config: LLMConfig | None) -> dict:
    session = sessions.get(session_id)
    if not session or not session.is_active:
        return {"type": "error", "content": "Socratic session not found or inactive."}

    session.turn_count += 1
    session.layer_turns[session.layer] = session.layer_turns.get(session.layer, 0) + 1
    session.messages.append({"role": "user", "content": message})

    if session.turn_count <= 2:
        session.intent = _detect_intent(" ".join(item["content"] for item in session.messages if item["role"] == "user"))

    new_insights = _extract_insights(message)
    for insight in new_insights:
        if insight not in session.insights:
            session.insights.append(insight)
    session.no_insight_turns = 0 if new_insights else session.no_insight_turns + 1
    session.papers.extend([paper for paper in _extract_papers(message) if paper not in session.papers])
    _update_convergence(session, message, new_insights)

    response_type = "question"
    if new_insights:
        response_type = "insight"

    if session.pending_gate:
        session.pending_gate = False
        session.probe_fired = True
    elif _layer_exit_ready(session, message):
        if session.layer < 5:
            session.pending_gate = True
            response_type = "transition"
        else:
            active_signals = sum(1 for value in session.convergence.values() if value)
            if active_signals >= 3:
                session.is_active = False
                summary = await generate_summary(session_id, provider, config)
                return {
                    "type": "converged",
                    "content": "五层讨论已收敛，我已经生成 Research Plan Summary。",
                    "summary": summary,
                    **_session_payload(session),
                }

    if session.pending_gate:
        content = f"{LAYER_NAMES[session.layer]} 已基本成立。进入下一层前：你先说说你准备怎么做，而不是让我替你决定。"
    else:
        if session.probe_fired and session.layer < 5:
            session.layer += 1
            session.probe_fired = False
            response_type = "transition"
            content = f"我们进入第 {session.layer}/5 层：{LAYER_NAMES[session.layer]}。\n\n{_fallback_question(session, message)}"
        else:
            content = _fallback_question(session, message)

    if session.no_insight_turns > 10:
        content += "\n\n你已经超过 10 轮没有形成新 INSIGHT，建议切换到 full 模式直接生成研究计划草案。"

    if provider and _can_use_llm(config):
        content = await _llm_refine_question(session, message, content, provider, config)

    session.messages.append({"role": "assistant", "content": content})
    return {"type": response_type, "content": content, **_session_payload(session)}


async def _llm_refine_question(
    session: SocraticSession,
    message: str,
    fallback: str,
    provider: LLMProvider,
    config: LLMConfig | None,
) -> str:
    if not config:
        return fallback
    prompt = f"""You are a Socratic research mentor.

Current layer: {session.layer}/5 {LAYER_NAMES[session.layer]}
Intent: {session.intent}
Convergence: {session.convergence}
Known insights: {session.insights[-5:]}
User message: {message}

Rewrite the next mentor response in Chinese. Be concise, ask one or two pointed questions, and do not answer for the user.
Base response:
{fallback}
"""
    try:
        return await provider.chat([
            ChatMessage(role="system", content="You ask Socratic research mentoring questions."),
            ChatMessage(role="user", content=prompt),
        ], config)
    except Exception:
        return fallback


async def generate_summary(session_id: str, provider: LLMProvider | None, config: LLMConfig | None) -> dict:
    session = sessions.get(session_id)
    if not session:
        return {"error": "Socratic session not found"}

    user_text = "\n".join(item["content"] for item in session.messages if item["role"] == "user")
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
Return JSON with keys: research_question, methodology, evidence_plan, limitations, significance, insights.

Transcript:
{user_text[-12000:]}

Convergence:
{session.convergence}
"""
    try:
        import json

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
    payload = asdict(session)
    payload.pop("messages", None)
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
        "state": payload,
    }
