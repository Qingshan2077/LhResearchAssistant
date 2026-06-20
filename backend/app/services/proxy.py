"""Process-wide HTTP proxy configuration for outbound research requests."""

from typing import Any

import httpx


_UNSET = object()
_proxy_url: str | None = None


def set_proxy(url: str | None) -> None:
    """Set the proxy used by clients created after this call."""
    global _proxy_url
    _proxy_url = url.strip() if url and url.strip() else None


def get_proxy() -> str | None:
    return _proxy_url


def _client_kwargs(proxy_override: object, kwargs: dict[str, Any]) -> dict[str, Any]:
    options = {"trust_env": False, **kwargs}
    proxy_url = _proxy_url if proxy_override is _UNSET else proxy_override
    if proxy_url:
        options.setdefault("proxy", proxy_url)
    return options


def get_async_client(
    *, proxy_override: str | None | object = _UNSET, **kwargs: Any
) -> httpx.AsyncClient:
    return httpx.AsyncClient(**_client_kwargs(proxy_override, kwargs))


def get_client(
    *, proxy_override: str | None | object = _UNSET, **kwargs: Any
) -> httpx.Client:
    return httpx.Client(**_client_kwargs(proxy_override, kwargs))