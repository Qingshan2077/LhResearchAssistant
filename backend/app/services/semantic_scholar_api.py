"""Shared Semantic Scholar authentication and rate-limit handling."""

import asyncio

import httpx
from loguru import logger


_api_key = ""


def set_semantic_scholar_api_key(api_key: str | None) -> None:
    global _api_key
    _api_key = (api_key or "").strip()


def get_semantic_scholar_api_key() -> str:
    return _api_key


def semantic_scholar_headers() -> dict[str, str]:
    return {"x-api-key": _api_key} if _api_key else {}


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("retry-after", "").strip()
    try:
        return min(max(float(retry_after), 0.0), 30.0) if retry_after else float(2**attempt)
    except ValueError:
        return float(2**attempt)


async def semantic_scholar_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_retries: int = 2,
    **kwargs,
) -> httpx.Response:
    """GET an S2 endpoint with API-key auth and bounded 429 backoff."""
    headers = dict(kwargs.pop("headers", {}) or {})
    headers.update({
        key: value
        for key, value in semantic_scholar_headers().items()
        if key not in headers
    })
    if headers:
        kwargs["headers"] = headers

    for attempt in range(max_retries + 1):
        response = await client.get(url, **kwargs)
        if response.status_code != 429 or attempt >= max_retries:
            return response
        delay = _retry_delay(response, attempt)
        logger.warning(
            "Semantic Scholar rate limited request; retrying in {} seconds ({}/{})",
            delay,
            attempt + 1,
            max_retries,
        )
        await asyncio.sleep(delay)

    raise RuntimeError("Semantic Scholar retry loop ended unexpectedly")