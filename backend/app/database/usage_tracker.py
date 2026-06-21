"""LLM usage tracking wrapper."""

import inspect
import time
from typing import AsyncIterator

from sqlalchemy.orm import Session

from loguru import logger

from app.database import SessionLocal
from app.database.sqlite import LLMUsage
from app.llm import ChatMessage, LLMConfig, LLMProvider
from app.llm.usage_context import clear_response_usage, take_response_usage


def _estimate_tokens(text: str) -> int:
    return max(0, int(len(text or "") / 4))


def _message_tokens(messages: list[ChatMessage]) -> int:
    return sum(_estimate_tokens(message.content) for message in messages)


def _infer_function_name() -> str:
    joined = " ".join(frame.filename.lower() for frame in inspect.stack()[2:12])
    if "paper_agent" in joined or "search" in joined:
        return "search"
    if "review" in joined:
        return "review"
    if "idea" in joined:
        return "idea"
    if "write" in joined or "writing" in joined:
        return "writing"
    if "socratic" in joined:
        return "socratic"
    if "verification" in joined or "citation" in joined:
        return "verification"
    if "read_agent" in joined or "parse_paper" in joined:
        return "read"
    return "chat"


def _record_usage(
    config: LLMConfig,
    function_name: str,
    tokens_in: int,
    tokens_out: int,
    duration_ms: int,
    cache_hit_tokens: int | None = None,
    cache_miss_tokens: int | None = None,
    status: str = "success",
    error_msg: str = "",
    provider_id: str | None = None,
    provider_name: str = "",
) -> None:
    db = SessionLocal()
    try:
        db.add(LLMUsage(
            provider_id=provider_id,
            provider_name=provider_name,
            model=config.model or "",
            function_name=function_name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cache_hit_tokens=cache_hit_tokens,
            cache_miss_tokens=cache_miss_tokens,
            duration_ms=duration_ms,
            status=status,
            error_msg=error_msg[:512],
        ))
        db.commit()
    except Exception as exc:
        logger.warning("usage_tracker.py operation failed: {}", exc)
        db.rollback()
    finally:
        db.close()


class UsageTrackingProvider(LLMProvider):
    """Wrap an LLM provider and record one usage row for each chat call."""

    def __init__(
        self,
        inner: LLMProvider,
        db: Session,
        provider_id: str | None = None,
        provider_name: str = "",
    ):
        self._inner = inner
        self._db = db
        self._provider_id = provider_id
        self._provider_name = provider_name

    async def chat(self, messages: list[ChatMessage], config: LLMConfig) -> str:
        start = time.perf_counter()
        function_name = _infer_function_name()
        estimated_tokens_in = _message_tokens(messages)
        clear_response_usage()
        try:
            result = await self._inner.chat(messages, config)
            duration_ms = int((time.perf_counter() - start) * 1000)
            usage = take_response_usage() or {}
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            cache_hit_tokens = usage.get("prompt_cache_hit_tokens")
            cache_miss_tokens = usage.get("prompt_cache_miss_tokens")
            _record_usage(
                config,
                function_name,
                int(prompt_tokens) if prompt_tokens is not None else estimated_tokens_in,
                int(completion_tokens) if completion_tokens is not None else _estimate_tokens(result),
                duration_ms,
                cache_hit_tokens=int(cache_hit_tokens) if cache_hit_tokens is not None else None,
                cache_miss_tokens=int(cache_miss_tokens) if cache_miss_tokens is not None else None,
                provider_id=self._provider_id,
                provider_name=self._provider_name,
            )
            return result
        except Exception as exc:
            take_response_usage()
            logger.warning("usage_tracker.py operation failed: {}", exc)
            duration_ms = int((time.perf_counter() - start) * 1000)
            _record_usage(
                config,
                function_name,
                estimated_tokens_in,
                0,
                duration_ms,
                status="error",
                error_msg=str(exc),
                provider_id=self._provider_id,
                provider_name=self._provider_name,
            )
            raise

    async def chat_stream(self, messages: list[ChatMessage], config: LLMConfig) -> AsyncIterator[str]:
        start = time.perf_counter()
        function_name = _infer_function_name()
        tokens_in = _message_tokens(messages)
        output_parts: list[str] = []
        try:
            async for token in self._inner.chat_stream(messages, config):
                output_parts.append(token)
                yield token
            duration_ms = int((time.perf_counter() - start) * 1000)
            _record_usage(
                config,
                function_name,
                tokens_in,
                _estimate_tokens("".join(output_parts)),
                duration_ms,
                provider_id=self._provider_id,
                provider_name=self._provider_name,
            )
        except Exception as exc:
            logger.warning("usage_tracker.py operation failed: {}", exc)
            duration_ms = int((time.perf_counter() - start) * 1000)
            _record_usage(
                config,
                function_name,
                tokens_in,
                _estimate_tokens("".join(output_parts)),
                duration_ms,
                status="error",
                error_msg=str(exc),
                provider_id=self._provider_id,
                provider_name=self._provider_name,
            )
            raise

    async def test_connection(self, config: LLMConfig) -> dict:
        return await self._inner.test_connection(config)
