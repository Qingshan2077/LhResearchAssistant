"""Idea endpoint integration tests with the LLM provider mocked."""

from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_generate_returns_sse_stream(async_client, mock_llm_provider, mock_llm_config):
    with patch("app.routers.ideas.get_active_provider") as active_provider:
        active_provider.return_value = (mock_llm_provider, mock_llm_config)
        response = await async_client.post("/api/v1/ideas/generate", json={
            "project_id": "default", "paper_ids": [], "mode": "gap_analysis",
        })
    assert response.status_code == 200
    assert "data:" in response.text
    assert "done" in response.text


@pytest.mark.asyncio
async def test_evaluate_returns_json(async_client, mock_llm_provider, mock_llm_config):
    mock_llm_provider.response = (
        '{"novelty": 4, "feasibility": 3, "cost": 2, '
        '"risk": "medium", "report": "Promising."}'
    )
    with patch("app.routers.ideas.get_active_provider") as active_provider:
        active_provider.return_value = (mock_llm_provider, mock_llm_config)
        response = await async_client.post("/api/v1/ideas/evaluate", json={
            "idea": "Test research idea", "context_paper_ids": [],
        })
    assert response.status_code == 200
    assert response.json()["novelty"] == 4
