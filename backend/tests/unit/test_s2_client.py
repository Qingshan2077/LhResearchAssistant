"""Tests for the Semantic Scholar client with HTTP fully mocked."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.s2_client import search_paper_by_title


def _mock_client(payload: dict, status_code: int = 200):
    response = MagicMock(status_code=status_code)
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    client = AsyncMock()
    client.get.return_value = response
    return client


@pytest.mark.asyncio
async def test_search_by_title_returns_verified_match():
    client = _mock_client({"data": [{
        "paperId": "abc123", "title": "A Complete Test Paper", "year": 2025,
        "authors": [{"name": "Author A"}], "externalIds": {}, "url": "https://example.test",
    }]})
    with patch("app.services.proxy.httpx.AsyncClient") as client_class:
        client_class.return_value.__aenter__.return_value = client
        result = await search_paper_by_title("A Complete Test Paper")
    assert result["status"] == "verified"
    assert result["paperId"] == "abc123"
    assert result["match"]["authors"] == ["Author A"]


@pytest.mark.asyncio
async def test_search_by_title_empty_response_is_not_found():
    client = _mock_client({"data": []})
    with patch("app.services.proxy.httpx.AsyncClient") as client_class:
        client_class.return_value.__aenter__.return_value = client
        result = await search_paper_by_title("Unknown Complete Paper")
    assert result == {"status": "not_found", "match": None, "candidates": []}


@pytest.mark.asyncio
async def test_search_by_title_404_returns_none():
    client = _mock_client({}, status_code=404)
    with patch("app.services.proxy.httpx.AsyncClient") as client_class:
        client_class.return_value.__aenter__.return_value = client
        assert await search_paper_by_title("Unknown Complete Paper") is None


@pytest.mark.asyncio
async def test_search_by_title_propagates_transport_errors():
    client = AsyncMock()
    client.get.side_effect = httpx.ConnectError("offline")
    with patch("app.services.proxy.httpx.AsyncClient") as client_class:
        client_class.return_value.__aenter__.return_value = client
        with pytest.raises(httpx.ConnectError):
            await search_paper_by_title("A Complete Test Paper")
