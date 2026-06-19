"""Integration tests for citation verification routes."""

import json
from unittest.mock import patch

import pytest

from tests.factories import make_paper


def test_empty_verification_status(client, db_session):
    paper = make_paper()
    db_session.add(paper)
    db_session.commit()

    response = client.get(f"/api/v1/papers/{paper.id}/verification-status")

    assert response.status_code == 200
    assert response.json() == {
        "total": 0,
        "verified": 0,
        "not_found": 0,
        "ambiguous": 0,
        "citations": [],
    }


def test_missing_paper_verification_returns_404(client):
    assert client.get("/api/v1/papers/missing/verification-status").status_code == 404
    assert client.post("/api/v1/papers/missing/verify-citations").status_code == 404


@pytest.mark.asyncio
async def test_verify_citations_returns_sse(async_client, db_session):
    paper = make_paper()
    db_session.add(paper)
    db_session.commit()

    async def events():
        yield {"data": json.dumps({"type": "start", "total": 0})}
        yield {"data": json.dumps({"type": "done"})}

    with patch("app.routers.verification._verify_stream", return_value=events()):
        response = await async_client.post(f"/api/v1/papers/{paper.id}/verify-citations")

    assert response.status_code == 200
    assert "data:" in response.text
    assert '"type": "done"' in response.text
