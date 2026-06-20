"""Tests for Semantic Scholar authentication and rate-limit retries."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.semantic_scholar_api import (
    semantic_scholar_get,
    set_semantic_scholar_api_key,
)


@pytest.mark.asyncio
async def test_semantic_scholar_get_adds_key_and_retries_429():
    limited = MagicMock(status_code=429, headers={})
    success = MagicMock(status_code=200, headers={})
    client = AsyncMock()
    client.get.side_effect = [limited, success]
    set_semantic_scholar_api_key("test-key")
    try:
        with patch("app.services.semantic_scholar_api.asyncio.sleep") as sleep:
            response = await semantic_scholar_get(client, "https://example.test")
        assert response is success
        assert client.get.await_count == 2
        assert client.get.await_args_list[0].kwargs["headers"] == {"x-api-key": "test-key"}
        sleep.assert_awaited_once_with(1.0)
    finally:
        set_semantic_scholar_api_key("")