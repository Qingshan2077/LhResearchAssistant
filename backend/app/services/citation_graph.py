"""Semantic Scholar citation graph retrieval."""

import asyncio
from typing import Any
from urllib.parse import quote

import httpx
from loguru import logger

from app.services.proxy import get_async_client


SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"
PAPER_FIELDS = "paperId,title,year,authors,venue,externalIds,citationCount,url"


def _paper_path_id(paper_id: str) -> str:
    return quote(str(paper_id).strip(), safe="")


def _authors(item: dict[str, Any]) -> list[str]:
    return [str(author.get("name", "")) for author in item.get("authors", []) if author.get("name")]


def _paper_item(item: dict[str, Any], group: str, is_seed: bool = False) -> dict[str, Any]:
    paper_id = item.get("paperId") or item.get("id") or item.get("title") or "unknown"
    return {
        "id": str(paper_id),
        "title": item.get("title") or "Untitled",
        "label": item.get("title") or "Untitled",
        "year": item.get("year"),
        "authors": _authors(item),
        "venue": item.get("venue") or "",
        "external_ids": item.get("externalIds") or {},
        "citation_count": item.get("citationCount") or 0,
        "url": item.get("url") or "",
        "is_seed": is_seed,
        "group": group,
    }


async def _get_paper(client: httpx.AsyncClient, paper_id: str) -> dict[str, Any] | None:
    resp = await client.get(
        f"{SEMANTIC_SCHOLAR_BASE}/paper/{_paper_path_id(paper_id)}",
        params={"fields": PAPER_FIELDS},
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


async def _get_relation_page(
    client: httpx.AsyncClient,
    paper_id: str,
    relation: str,
    item_key: str,
) -> list[dict[str, Any]]:
    resp = await client.get(
        f"{SEMANTIC_SCHOLAR_BASE}/paper/{_paper_path_id(paper_id)}/{relation}",
        params={"limit": 50, "fields": PAPER_FIELDS},
    )
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    rows = resp.json().get("data", []) or []
    return [row.get(item_key) for row in rows if row.get(item_key)]


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        item_id = str(item.get("id") or "")
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        unique.append(item)
    return unique


async def get_citation_graph(paper_id: str) -> dict[str, Any]:
    """Return seed paper, references, citations and ReactFlow-ready graph data."""
    try:
        async with get_async_client(timeout=30) as client:
            seed_raw = await _get_paper(client, paper_id)
            if not seed_raw:
                return {"error": "Paper not found on Semantic Scholar."}

            canonical_id = seed_raw.get("paperId") or paper_id
            await asyncio.sleep(1)
            reference_raw = await _get_relation_page(client, canonical_id, "references", "citedPaper")
            await asyncio.sleep(1)
            citation_raw = await _get_relation_page(client, canonical_id, "citations", "citingPaper")
    except httpx.HTTPStatusError as exc:
        logger.warning("Semantic Scholar graph request returned HTTP {}", exc.response.status_code)
        status_code = exc.response.status_code
        if status_code == 429:
            return {"error": "Semantic Scholar rate limit reached. Please retry later."}
        return {"error": f"Semantic Scholar returned HTTP {status_code}."}
    except httpx.RequestError as exc:
        logger.warning("Semantic Scholar graph request failed: {}", exc)
        return {"error": f"Cannot reach Semantic Scholar: {exc}"}

    seed = _paper_item(seed_raw, "seed", True)
    references = _dedupe([_paper_item(item, "reference") for item in reference_raw])
    citations = _dedupe([_paper_item(item, "citation") for item in citation_raw])

    nodes = _dedupe([seed, *references, *citations])
    edges = [
        {"source": seed["id"], "target": item["id"], "type": "cites"}
        for item in references
        if item["id"] != seed["id"]
    ]
    edges.extend(
        {"source": item["id"], "target": seed["id"], "type": "cites"}
        for item in citations
        if item["id"] != seed["id"]
    )

    return {
        "paper": seed,
        "references": references,
        "citations": citations,
        "graph": {
            "nodes": nodes,
            "edges": edges,
        },
    }
