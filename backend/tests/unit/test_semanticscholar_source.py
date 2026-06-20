"""Unit tests for the Semantic Scholar paper source."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.paper_sources.semanticscholar import SemanticScholarSource


def _response(payload: dict, status_code: int = 200):
    response = MagicMock(status_code=status_code)
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def test_semantic_scholar_source_name():
    assert SemanticScholarSource().source_name == "semantic_scholar"


@pytest.mark.asyncio
async def test_semantic_scholar_search_maps_results():
    response = _response({"data": [{
        "paperId": "abc123",
        "title": "S2 Paper",
        "authors": [{"name": "Author A"}],
        "year": 2025,
        "venue": "NeurIPS",
        "citationCount": 42,
        "abstract": "Test abstract.",
        "externalIds": {"DOI": "10.1234/test", "ArXiv": "2501.00001"},
        "openAccessPdf": {"url": "https://pdf.example.test/paper.pdf"},
        "url": "https://example.test/paper/abc123",
    }]})
    client = AsyncMock()
    client.get.return_value = response

    with patch(
        "app.services.proxy.httpx.AsyncClient"
    ) as client_class:
        client_class.return_value.__aenter__.return_value = client
        results = await SemanticScholarSource().search("attention", max_results=5)

    assert len(results) == 1
    assert results[0].title == "S2 Paper"
    assert results[0].authors == ["Author A"]
    assert results[0].citation_count == 42
    assert results[0].doi == "10.1234/test"
    assert results[0].pdf_url == "https://pdf.example.test/paper.pdf"


@pytest.mark.asyncio
async def test_semantic_scholar_transport_error_is_propagated():
    client = AsyncMock()
    client.get.side_effect = httpx.ConnectError("offline")

    with patch(
        "app.services.proxy.httpx.AsyncClient"
    ) as client_class:
        client_class.return_value.__aenter__.return_value = client
        with pytest.raises(httpx.ConnectError):
            await SemanticScholarSource().search("attention", max_results=5)

@pytest.mark.asyncio
async def test_semantic_scholar_fetch_missing_returns_none():
    client = AsyncMock()
    client.get.return_value = _response({}, status_code=404)

    with patch(
        "app.services.proxy.httpx.AsyncClient"
    ) as client_class:
        client_class.return_value.__aenter__.return_value = client
        result = await SemanticScholarSource().fetch_details("missing")

    assert result is None
