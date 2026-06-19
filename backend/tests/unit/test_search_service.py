"""Tests for search result deduplication."""

from app.services.paper_sources import PaperSourceResult
from app.services.search_service import _deduplicate


def test_identical_doi_is_deduplicated():
    results = _deduplicate([
        PaperSourceResult(title="Paper A", doi="10.1234/test"),
        PaperSourceResult(title="Paper A copy", doi="10.1234/test"),
    ])
    assert len(results) == 1


def test_identical_arxiv_id_is_deduplicated():
    results = _deduplicate([
        PaperSourceResult(title="Paper A", arxiv_id="2401.00001"),
        PaperSourceResult(title="Paper A copy", arxiv_id="2401.00001"),
    ])
    assert len(results) == 1


def test_distinct_identifiers_are_retained():
    results = _deduplicate([
        PaperSourceResult(title="Paper A", doi="10.1234/a"),
        PaperSourceResult(title="Paper B", doi="10.1234/b"),
    ])
    assert len(results) == 2


def test_normalized_title_is_fallback_key():
    results = _deduplicate([
        PaperSourceResult(title="Paper Title."),
        PaperSourceResult(title="paper title"),
    ])
    assert len(results) == 1


def test_empty_results_remain_empty():
    assert _deduplicate([]) == []
