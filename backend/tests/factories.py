"""Factories for concise SQLAlchemy model setup."""

import uuid

from app.database.sqlite import LLMProvider, Paper, Project


def make_project(name: str = "Test Project", description: str = "A test project") -> Project:
    return Project(id=str(uuid.uuid4()), name=name, description=description)


def make_paper(
    project_id: str | None = None,
    title: str = "Test Paper Title",
    authors: list[str] | None = None,
    abstract: str = "This is a test abstract for a research paper.",
    year: int = 2025,
    venue: str = "NeurIPS",
    doi: str = "",
    arxiv_id: str = "",
    source: str = "manual",
    citation_count: int = 10,
    read_status: str = "unread",
    pdf_path: str = "",
    keywords: list[str] | None = None,
) -> Paper:
    return Paper(
        id=str(uuid.uuid4()), project_id=project_id, title=title,
        authors=authors if authors is not None else ["Author A", "Author B"],
        abstract=abstract, year=year, venue=venue, doi=doi, arxiv_id=arxiv_id,
        source=source, citation_count=citation_count,
        keywords=keywords if keywords is not None else ["machine learning", "deep learning"],
        read_status=read_status, pdf_path=pdf_path,
    )


def make_llm_provider(
    name: str = "deepseek", display_name: str = "DeepSeek Mock",
    api_key: str = "mock-key", base_url: str = "https://api.deepseek.com",
    default_model: str = "deepseek-chat", is_active: bool = True, priority: int = 0,
) -> LLMProvider:
    return LLMProvider(
        id=str(uuid.uuid4()), name=name, display_name=display_name, api_key=api_key,
        base_url=base_url, default_model=default_model, is_active=is_active, priority=priority,
    )
