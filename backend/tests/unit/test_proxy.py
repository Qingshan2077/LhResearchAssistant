"""Tests for process-wide outbound proxy clients."""

from unittest.mock import patch

from app.services.proxy import get_async_client, get_client, set_proxy


def test_clients_use_runtime_proxy_and_ignore_environment():
    set_proxy("http://127.0.0.1:7897")
    try:
        with patch("app.services.proxy.httpx.AsyncClient") as async_client:
            get_async_client(timeout=5)
            async_client.assert_called_once_with(
                trust_env=False,
                timeout=5,
                proxy="http://127.0.0.1:7897",
            )

        with patch("app.services.proxy.httpx.Client") as client:
            get_client(timeout=5)
            client.assert_called_once_with(
                trust_env=False,
                timeout=5,
                proxy="http://127.0.0.1:7897",
            )
    finally:
        set_proxy(None)


def test_explicit_direct_override_bypasses_runtime_proxy():
    set_proxy("http://127.0.0.1:7897")
    try:
        with patch("app.services.proxy.httpx.AsyncClient") as async_client:
            get_async_client(proxy_override=None)
            async_client.assert_called_once_with(trust_env=False)
    finally:
        set_proxy(None)