"""Semantic Scholar citation verification client."""

import asyncio
import re
from difflib import SequenceMatcher
from typing import Optional

import httpx
from loguru import logger


SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"


def normalize_title(title: str) -> str:
    title = title.lower()
    title = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", title)
    return re.sub(r"\s+", " ", title).strip()


def title_similarity(left: str, right: str) -> float:
    left_norm = normalize_title(left)
    right_norm = normalize_title(right)
    if len(left_norm) <= 5 or len(right_norm) <= 5:
        return 0.0
    return SequenceMatcher(None, left_norm, right_norm).ratio()


def _status_from_score(score: float) -> str:
    if score >= 0.70:
        return "verified"
    if score >= 0.50:
        return "ambiguous"
    return "not_found"


async def search_paper_by_title(title: str) -> Optional[dict]:
    """Search Semantic Scholar by title and classify the best candidate."""
    if len(title.strip()) <= 5:
        return None

    params = {
        "query": title,
        "limit": 3,
        "fields": "paperId,title,year,authors,externalIds,url",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{SEMANTIC_SCHOLAR_BASE}/paper/search", params=params)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()

    candidates = []
    for item in data.get("data", []) or []:
        score = title_similarity(title, item.get("title", ""))
        candidates.append({
            "paperId": item.get("paperId", ""),
            "title": item.get("title", ""),
            "year": item.get("year"),
            "authors": [author.get("name", "") for author in item.get("authors", [])],
            "externalIds": item.get("externalIds") or {},
            "url": item.get("url", ""),
            "score": round(score, 3),
        })

    if not candidates:
        return {"status": "not_found", "match": None, "candidates": []}

    candidates.sort(key=lambda item: item["score"], reverse=True)
    best = candidates[0]
    status = _status_from_score(float(best["score"]))
    return {
        "status": status,
        "match": best if status == "verified" else None,
        "paperId": best.get("paperId") if status == "verified" else "",
        "candidates": candidates if status == "ambiguous" else candidates[:1],
    }


async def verify_by_doi(doi: str) -> Optional[dict]:
    """Verify a paper by DOI."""
    clean_doi = doi.strip()
    if not clean_doi:
        return None

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{SEMANTIC_SCHOLAR_BASE}/paper/DOI:{clean_doi}",
            params={"fields": "paperId,title,year,authors,externalIds,url"},
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        item = resp.json()

    return {
        "status": "verified",
        "match": {
            "paperId": item.get("paperId", ""),
            "title": item.get("title", ""),
            "year": item.get("year"),
            "authors": [author.get("name", "") for author in item.get("authors", [])],
            "externalIds": item.get("externalIds") or {},
            "url": item.get("url", ""),
            "score": 1.0,
        },
        "paperId": item.get("paperId", ""),
        "candidates": [],
    }


async def batch_search(titles: list[str]) -> dict[str, dict]:
    """Search titles one by one with a conservative free-tier delay."""
    results: dict[str, dict] = {}
    for index, title in enumerate(titles):
        if index > 0:
            await asyncio.sleep(1)
        try:
            result = await search_paper_by_title(title)
            results[title] = result or {"status": "not_found", "match": None, "candidates": []}
        except Exception as exc:
            logger.warning("s2_client.py operation failed: {}", exc)
            results[title] = {"status": "error", "message": str(exc), "match": None, "candidates": []}
    return results
