"""Tests for SQLAlchemy model defaults and relationships."""

from app.database.sqlite import Paper
from tests.factories import make_paper, make_project


def test_paper_uuid_and_defaults_are_applied_on_flush(db_session):
    paper = Paper(title="Test")
    db_session.add(paper)
    db_session.flush()
    assert len(paper.id) == 36
    assert paper.authors == []
    assert paper.abstract == ""
    assert paper.read_status == "unread"
    assert paper.citation_count == 0
    assert paper.tags == []
    assert paper.rating == 0


def test_project_paper_relationship(db_session):
    project = make_project()
    db_session.add(project)
    db_session.flush()
    paper1 = make_paper(project_id=project.id, title="Paper 1")
    paper2 = make_paper(project_id=project.id, title="Paper 2")
    db_session.add_all([paper1, paper2])
    db_session.flush()
    assert {paper.title for paper in project.papers} == {"Paper 1", "Paper 2"}
    assert paper1.project is project


def test_delete_project_cascades_papers(db_session):
    project = make_project()
    paper = make_paper(title="Child")
    project.papers.append(paper)
    db_session.add(project)
    db_session.flush()
    paper_id = paper.id
    db_session.delete(project)
    db_session.flush()
    assert db_session.get(Paper, paper_id) is None
