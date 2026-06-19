"""Integration tests for the generic WebSocket route."""

from unittest.mock import patch


def test_websocket_chat_returns_chunk(client, mock_llm_provider, mock_llm_config):
    with patch("app.routers.streaming.get_active_provider") as active_provider:
        active_provider.return_value = (mock_llm_provider, mock_llm_config)
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json({
                "type": "chat",
                "messages": [{"role": "user", "content": "Hello"}],
            })
            message = websocket.receive_json()

    assert message["type"] == "chunk"
    assert message["content"]


def test_websocket_ping_returns_pong(client):
    with client.websocket_connect("/api/v1/ws") as websocket:
        websocket.send_json({"type": "ping"})
        message = websocket.receive_json()
    assert message == {"type": "pong"}


def test_websocket_without_provider_returns_error(client):
    with patch("app.routers.streaming.get_active_provider", return_value=None):
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json({
                "type": "chat",
                "messages": [{"role": "user", "content": "Hello"}],
            })
            message = websocket.receive_json()
    assert message["type"] == "error"
    assert "provider" in message["message"].lower()
