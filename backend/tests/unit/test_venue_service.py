"""Tests for fallback venue recommendations."""

import pytest

from app.services.venue_service import (
    _fallback_recommendations,
    _keyword_score,
    _rank_boost,
    recommend_venues,
)


def test_exact_keyword_match_scores_positive():
    score, hits = _keyword_score(
        "machine learning optimization",
        {"keywords": ["machine learning", "optimization"], "field": "AI/ML"},
    )
    assert score > 0
    assert "machine learning" in hits


def test_empty_text_scores_zero():
    assert _keyword_score("", {"keywords": ["machine learning"], "field": "AI"}) == (0, [])


@pytest.mark.parametrize(
    ("title", "abstract", "keywords", "expected"),
    [
        ("Image Segmentation", "A method for images", ["segmentation"], {"CVPR", "ICCV", "ECCV"}),
        ("Machine Translation", "A language model", ["translation"], {"ACL", "EMNLP", "NAACL"}),
        ("Distributed Storage", "A distributed system", ["storage"], {"OSDI", "SOSP"}),
    ],
)
def test_domain_specific_venues_appear_in_top_five(title, abstract, keywords, expected):
    results = _fallback_recommendations(title, abstract, keywords)
    assert len(results) == 5
    assert expected.intersection(item["name"] for item in results)
    assert all(0 <= item["match_score"] <= 1 for item in results)


@pytest.mark.asyncio
async def test_missing_provider_uses_fallback():
    results = await recommend_venues(
        "Machine Learning", "Optimization research", ["deep learning"], None, None
    )
    assert len(results) == 5
    assert all(isinstance(item["match_reason"], str) for item in results)


def test_rank_boost_orders_known_ranks():
    assert _rank_boost("A") > _rank_boost("B") > _rank_boost("C") > _rank_boost("X")
