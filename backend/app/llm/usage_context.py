"""Per-call LLM usage transport that is safe across concurrent async tasks."""

from contextvars import ContextVar
from typing import Any


_current_usage: ContextVar[dict[str, int | None] | None] = ContextVar(
    "llm_response_usage",
    default=None,
)


def clear_response_usage() -> None:
    _current_usage.set(None)


def capture_response_usage(usage: Any) -> None:
    """Copy OpenAI-compatible usage fields from an SDK response."""
    if usage is None:
        clear_response_usage()
        return

    dumped: dict[str, Any] = {}
    model_dump = getattr(usage, "model_dump", None)
    if callable(model_dump):
        try:
            dumped = model_dump()
        except Exception:
            dumped = {}
    model_extra = getattr(usage, "model_extra", None)
    if isinstance(model_extra, dict):
        dumped.update(model_extra)

    def value(name: str) -> int | None:
        raw = getattr(usage, name, None)
        if raw is None:
            raw = dumped.get(name)
        try:
            return int(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    _current_usage.set({
        "prompt_tokens": value("prompt_tokens"),
        "completion_tokens": value("completion_tokens"),
        "total_tokens": value("total_tokens"),
        "prompt_cache_hit_tokens": value("prompt_cache_hit_tokens"),
        "prompt_cache_miss_tokens": value("prompt_cache_miss_tokens"),
    })


def take_response_usage() -> dict[str, int | None] | None:
    usage = _current_usage.get()
    _current_usage.set(None)
    return usage
