"""Knowledge-base endpoint integration tests."""

from tests.factories import make_paper


def test_empty_mindmap_for_unparsed_paper(client, db_session):
    paper = make_paper()
    db_session.add(paper)
    db_session.commit()
    response = client.get(f"/api/v1/knowledge/mindmap/{paper.id}")
    assert response.status_code == 200
    assert response.json() == {"nodes": []}


def test_missing_paper_mindmap_returns_404(client):
    assert client.get("/api/v1/knowledge/mindmap/missing").status_code == 404


def test_graph_uses_stored_and_extracted_keywords(client, db_session):
    paper = make_paper(keywords=["stored keyword"])
    paper.extracted_data = {
        "keywords": ["extracted keyword"],
        "method": {"components": [{"name": "not a graph concept"}]},
    }
    db_session.add(paper)
    db_session.commit()

    graph = client.get("/api/v1/knowledge/graph").json()
    concept_labels = {node["label"] for node in graph["nodes"] if node["type"] == "concept"}
    assert "stored keyword" in concept_labels
    assert "extracted keyword" in concept_labels
    assert "not a graph concept" not in concept_labels