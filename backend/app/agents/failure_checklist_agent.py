"""Seven-mode AI research failure checklist."""

import json
import re

from app.llm import ChatMessage, LLMConfig, LLMProvider


MODES = [
    (1, "Implementation bug"),
    (2, "Citation hallucination"),
    (3, "Hallucinated experimental result"),
    (4, "Shortcut reliance"),
    (5, "Bug reframed as insight"),
    (6, "Methodology fabrication"),
    (7, "Frame-lock"),
]

BLOCKING_INSUFFICIENT = {1, 3, 5, 6}


def _can_use_llm(config: LLMConfig | None) -> bool:
    if not config:
        return False
    base_url = (config.base_url or "").lower()
    return bool(config.api_key) or "localhost" in base_url or "127.0.0.1" in base_url


def _fallback_mode(mode: int, name: str, text: str) -> dict:
    lowered = text.lower()
    status = "insufficient_evidence"
    reasoning = "No direct audit evidence was provided for this mode."

    if mode == 2:
        if "citation_verified" in lowered or "verified" in lowered:
            status = "clear"
            reasoning = "The text references citation verification evidence."
        else:
            status = "insufficient_evidence"
            reasoning = "Citation verification evidence is not shown."
    elif mode == 5 and re.search(r"surprisingly|unexpectedly|counterintuitively|反直觉|意外", lowered):
        status = "suspected"
        reasoning = "The text contains surprise framing that needs evidence that the result is genuinely anomalous."
    elif mode == 3 and re.search(r"\b\d+(?:\.\d+)?\s*%|improvement|提升|超过", lowered):
        status = "insufficient_evidence"
        reasoning = "Quantitative improvement claims need raw data, run counts, and traceability."
    elif mode == 4 and re.search(r"ablation|baseline|对照|消融", lowered):
        status = "clear"
        reasoning = "The text mentions ablations or baselines, but strength still requires manual inspection."
    elif mode == 7 and re.search(r"in hindsight|we realized later|回头看|后来意识到", lowered):
        status = "suspected"
        reasoning = "The text contains hindsight framing that may indicate frame-lock."

    return {
        "mode": mode,
        "name": name,
        "status": status,
        "reasoning": reasoning,
        "action_required": status == "suspected" or (status == "insufficient_evidence" and mode in BLOCKING_INSUFFICIENT),
    }


def _apply_blocking(modes: list[dict]) -> tuple[list[dict], bool]:
    blocking = False
    for item in modes:
        mode = int(item.get("mode", 0))
        status = item.get("status", "insufficient_evidence")
        action_required = status == "suspected" or (status == "insufficient_evidence" and mode in BLOCKING_INSUFFICIENT)
        item["action_required"] = action_required
        blocking = blocking or action_required
    return modes, blocking


async def run_failure_checklist(
    text: str,
    provider: LLMProvider | None,
    config: LLMConfig | None,
) -> dict:
    """Run the 7-mode AI research failure checklist."""
    fallback_modes = [_fallback_mode(mode, name, text) for mode, name in MODES]
    fallback_modes, fallback_blocking = _apply_blocking(fallback_modes)
    fallback = {
        "modes": fallback_modes,
        "blocking": fallback_blocking,
        "summary": "Checklist completed with local heuristics. Modes marked insufficient evidence need supporting logs, citations, or experiment traces.",
    }

    if not provider or not _can_use_llm(config):
        return fallback

    prompt = f"""Run the 7-mode AI research failure checklist on this manuscript passage.

Return JSON only:
{{
  "modes": [
    {{"mode": 1, "name": "Implementation bug", "status": "clear|suspected|insufficient_evidence", "reasoning": "...", "action_required": false}}
  ],
  "summary": "..."
}}

Mode guidance:
1 Implementation bug: reproducibility, suspicious round effect sizes, identical error bars.
2 Citation hallucination: are citations S2 verified? If not, insufficient evidence.
3 Hallucinated experimental result: each improvement claim needs raw traceable data and run count.
4 Shortcut reliance: controlled ablations and strong baselines.
5 Bug reframed as insight: surprising/unexpected claims need support.
6 Methodology fabrication: hyperparameters and methods must match actual configs/code.
7 Frame-lock: hindsight framing and unwillingness to revisit direction.

Text:
{text[:16000]}
"""
    try:
        raw = await provider.chat([
            ChatMessage(role="system", content="You audit AI research manuscripts for failure modes."),
            ChatMessage(role="user", content=prompt),
        ], config)
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        parsed = json.loads(match.group(1) if match else raw)
        llm_modes = parsed.get("modes") or fallback_modes
        by_mode = {int(item.get("mode", 0)): item for item in llm_modes}
        merged = []
        for mode, name in MODES:
            item = by_mode.get(mode, {})
            merged.append({
                "mode": mode,
                "name": item.get("name") or name,
                "status": item.get("status") if item.get("status") in {"clear", "suspected", "insufficient_evidence"} else "insufficient_evidence",
                "reasoning": item.get("reasoning", ""),
                "action_required": bool(item.get("action_required", False)),
            })
        merged, blocking = _apply_blocking(merged)
        return {
            "modes": merged,
            "blocking": blocking,
            "summary": parsed.get("summary", fallback["summary"]),
        }
    except Exception:
        return fallback
