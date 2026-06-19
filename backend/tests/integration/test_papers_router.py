"""Paper CRUD endpoint integration tests."""

from tests.factories import make_paper, make_project


def test_list_papers_is_empty(client):
    response = client.get("/api/v1/papers")
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0


def test_list_filters_and_paginates(client, db_session):
    project = make_project()
    db_session.add(project)
    db_session.flush()
    db_session.add_all([
        make_paper(project.id, title="Transformer One", read_status="read"),
        make_paper(project.id, title="Transformer Two", read_status="read"),
        make_paper(project.id, title="Vision Paper", read_status="unread"),
    ])
    db_session.commit()
    response = client.get(
        f"/api/v1/papers?project_id={project.id}&search=Transformer&read_status=read&page_size=1"
    )
    data = response.json()
    assert response.status_code == 200
    assert data["total"] == 2
    assert len(data["items"]) == 1
    assert data["page_size"] == 1


def test_create_paper_with_full_metadata(client, db_session):
    project = make_project()
    db_session.add(project)
    db_session.commit()
    response = client.post("/api/v1/papers", json={
        "project_id": project.id, "title": "Full Paper", "authors": ["Alice", "Bob"],
        "abstract": "Complete test", "year": 2025, "venue": "NeurIPS",
        "doi": "10.1234/test", "arxiv_id": "2501.00001", "source": "arxiv",
        "citation_count": 42, "keywords": ["test"],
        "url": "https://example.test/paper", "pdf_url": "https://example.test/paper.pdf",
    })
    data = response.json()
    assert response.status_code == 200
    assert data["title"] == "Full Paper"
    assert data["citation_count"] == 42


def test_get_existing_and_missing_paper(client, db_session):
    paper = make_paper(title="Specific Paper")
    db_session.add(paper)
    db_session.commit()
    response = client.get(f"/api/v1/papers/{paper.id}")
    assert response.status_code == 200
    assert response.json()["title"] == "Specific Paper"
    assert client.get("/api/v1/papers/missing-id").status_code == 404


def test_update_paper_persists(client, db_session):
    paper = make_paper()
    db_session.add(paper)
    db_session.commit()
    response = client.patch(f"/api/v1/papers/{paper.id}", json={
        "tags": ["tag1", "tag2"], "read_status": "reading", "rating": 4,
    })
    assert response.status_code == 200
    db_session.refresh(paper)
    assert paper.tags == ["tag1", "tag2"]
    assert paper.read_status == "reading"
    assert paper.rating == 4


def test_update_missing_paper_returns_404(client):
    assert client.patch("/api/v1/papers/missing", json={"tags": ["x"]}).status_code == 404
