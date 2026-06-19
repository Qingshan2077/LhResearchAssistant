"""Search endpoint integration tests with external sources mocked."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.paper_sources import PaperSourceResult


@pytest.mark.asyncio
async def test_search_returns_mocked_results(async_client):
    result = PaperSourceResult(
        title="Paper A", authors=["A"], abstract="Abstract A", year=2025,
        venue="NeurIPS", doi="10.1234/a", arxiv_id="2501.00001",
        source="arxiv", citation_count=5,
    )
    with patch("app.routers.search.search_papers", new_callable=AsyncMock) as search:
        search.return_value = ([result], {"arxiv": 1}, {})
        response = await async_client.post("/api/v1/search", json={
            "query": "machine learning", "sources": ["arxiv"], "max_results_per_source": 10,
        })
    assert response.status_code == 200
    assert response.json()["papers"][0]["title"] == "Paper A"
    assert response.json()["source_breakdown"] == {"arxiv": 1}


def test_import_papers_creates_records(client):
    response = client.post("/api/v1/search/import", json={
        "project_id": "test-project",
        "papers": [{
            "title": "Imported Paper", "authors": ["Author X"],
            "abstract": "Imported abstract", "year": 2025, "venue": "ICML",
            "source": "arxiv", "arxiv_id": "2501.99999",
        }],
    })
    assert response.status_code == 200
    assert response.json()["imported"] == 1
    assert response.json()["papers"][0]["project_id"] == "test-project"


def test_import_empty_papers_returns_400(client):
    response = client.post("/api/v1/search/import", json={"project_id": "test", "papers": []})
    assert response.status_code == 400
