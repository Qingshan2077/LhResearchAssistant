"""Integration tests for the Socratic mentor routes."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("initial_message", ["A new attention mechanism", ""])
async def test_create_socratic_session(
    async_client,
    mock_llm_provider,
    mock_llm_config,
    initial_message,
):
    with (
        patch("app.routers.socratic.get_active_provider") as active_provider,
        patch(
            "app.routers.socratic.create_session",
            new_callable=AsyncMock,
            return_value="test-session",
        ) as create_session,
    ):
        active_provider.return_value = (mock_llm_provider, mock_llm_config)
        response = await async_client.post("/api/v1/ideas/socratic/create", json={
            "project_id": "default",
            "initial_message": initial_message,
        })

    assert response.status_code == 200
    assert response.json() == {"session_id": "test-session"}
    create_session.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_socratic_summary_returns_404(async_client):
    response = await async_client.get("/api/v1/ideas/socratic/missing-session/summary")
    assert response.status_code == 404


def test_missing_socratic_websocket_session_returns_error(client):
    with client.websocket_connect("/api/v1/ideas/socratic/missing-session") as websocket:
        message = websocket.receive_json()
    assert message["type"] == "error"
    assert "not found" in message["content"].lower()
