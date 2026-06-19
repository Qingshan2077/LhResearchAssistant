"""Unit tests for the DBLP paper source."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.paper_sources.dblp import DBLPSource


def _dblp_response(payload: dict):
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def test_dblp_source_name_and_fetch_details():
    source = DBLPSource()
    assert source.source_name == "dblp"


@pytest.mark.asyncio
async def test_dblp_search_maps_metadata_and_links():
    payload = {"result": {"hits": {"hit": [{"info": {
        "title": "DBLP Paper",
        "authors": {"author": ["Author A", "Author B"]},
        "year": "2025",
        "venue": "ICML",
        "url": "https://dblp.org/rec/conf/test/paper",
        "links": {"link": [
            {"href": "https://doi.org/10.1234/test"},
            {"href": "https://arxiv.org/abs/2501.00001"},
        ]},
    }}]}}}
    client = AsyncMock()
    client.get.return_value = _dblp_response(payload)

    with patch("app.services.paper_sources.dblp.httpx.AsyncClient") as client_class:
        client_class.return_value.__aenter__.return_value = client
        results = await DBLPSource().search("database", max_results=5)

    assert len(results) == 1
    assert results[0].title == "DBLP Paper"
    assert results[0].authors == ["Author A", "Author B"]
    assert results[0].doi == "10.1234/test"
    assert results[0].arxiv_id == "2501.00001"
    assert results[0].source == "dblp"


@pytest.mark.asyncio
async def test_dblp_search_applies_year_filter():
    payload = {"result": {"hits": {"hit": [{"info": {
        "title": "Old Paper", "authors": {"author": "Author A"}, "year": "2018",
    }}]}}}
    client = AsyncMock()
    client.get.return_value = _dblp_response(payload)

    with patch("app.services.paper_sources.dblp.httpx.AsyncClient") as client_class:
        client_class.return_value.__aenter__.return_value = client
        results = await DBLPSource().search("database", year_from=2020)

    assert results == []

@pytest.mark.asyncio
async def test_dblp_fetch_details_is_unsupported():
    assert await DBLPSource().fetch_details("conf/test/paper") is None
