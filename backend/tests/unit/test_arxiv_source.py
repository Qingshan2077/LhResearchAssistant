"""Unit tests for the arXiv paper source."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.paper_sources.arxiv import ArxivSource


def test_arxiv_source_name():
    assert ArxivSource().source_name == "arxiv"


@pytest.mark.asyncio
async def test_arxiv_search_maps_results():
    paper = SimpleNamespace(
        title="Test Paper Title",
        authors=[SimpleNamespace(name="Author A"), SimpleNamespace(name="Author B")],
        summary="This is a test abstract.",
        published=SimpleNamespace(year=2025),
        doi="10.1234/test",
        entry_id="http://arxiv.org/abs/2501.00001v1",
        pdf_url="http://arxiv.org/pdf/2501.00001.pdf",
    )
    source = ArxivSource()
    source.client.results = MagicMock(return_value=[paper])

    results = await source.search(query="transformer", max_results=10)

    assert len(results) == 1
    assert results[0].title == "Test Paper Title"
    assert results[0].authors == ["Author A", "Author B"]
    assert results[0].source == "arxiv"
    assert results[0].year == 2025
    assert results[0].doi == "10.1234/test"


@pytest.mark.asyncio
async def test_arxiv_search_applies_year_filter():
    old_paper = SimpleNamespace(
        title="Old Paper", authors=[], summary="", published=SimpleNamespace(year=2019),
        doi=None, entry_id="http://arxiv.org/abs/1901.00001", pdf_url=None,
    )
    source = ArxivSource()
    source.client.results = MagicMock(return_value=[old_paper])

    results = await source.search("test", year_from=2020)

    assert results == []

@pytest.mark.asyncio
async def test_arxiv_fetch_details_maps_result():
    paper = SimpleNamespace(
        title="Detailed Paper", authors=[SimpleNamespace(name="Author A")], summary="Abstract",
        published=SimpleNamespace(year=2024), doi=None,
        entry_id="http://arxiv.org/abs/2401.00001", pdf_url="http://arxiv.org/pdf/2401.00001.pdf",
    )
    source = ArxivSource()
    source.client.results = MagicMock(return_value=iter([paper]))

    result = await source.fetch_details("2401.00001")

    assert result is not None
    assert result.title == "Detailed Paper"
    assert result.arxiv_id == "2401.00001"
