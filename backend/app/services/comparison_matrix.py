"""Structured comparison table generation for selected papers."""

import json
import re
from typing import Any

from loguru import logger

from app.llm import ChatMessage, LLMConfig, LLMProvider


DEFAULT_DIMENSIONS = ["method", "dataset", "metric", "code_available", "key_finding"]

COMPARISON_PROMPT = """\
You are creating a structured comparison table of research papers.

Papers (each tagged with an ID in [brackets]):
{papers}

Comparison dimensions:
{dimensions}

For each paper, extract information for each dimension based on the paper's abstract and available data.
If a specific dimension's information is not clearly present in the paper, write "Not specified".
Do not fabricate information.

Return JSON only:
{{
  "table": [
    {{
      "id": "paper_id",
      "title": "Paper Title",
      "year": 2024,
      "venue": "...",
      "values": {{
        "dimension_1": "value",
        "dimension_2": "value"
      }}
    }}
  ],
  "notes": "Any important caveats or observations about the comparison."
}}
"""


def _can_use_llm(config: LLMConfig | None) -> bool:
    if not config:
        return False
    base_url = (config.base_url or "").lower()
    return bool(config.api_key) or "localhost" in base_url or "127.0.0.1" in base_url


def _fallback_table(papers: list[dict[str, Any]], dimensions: list[str]) -> dict[str, Any]:
    return {
        "table": [
            {
                "id": paper.get("id", str(index)),
                "title": paper.get("title", "Unknown"),
                "year": paper.get("year"),
                "venue": paper.get("venue", ""),
                "values": {dimension: "LLM unavailable for extraction" for dimension in dimensions},
            }
            for index, paper in enumerate(papers)
        ],
        "notes": "Generated from local metadata only because LLM extraction was unavailable.",
    }


def _parse_json_object(raw: str) -> dict[str, Any]:
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if match:
        raw = match.group(1)
    parsed = json.loads(raw)
    return parsed if isinstance(parsed, dict) else {}


async def generate_comparison_table(
    papers: list[dict[str, Any]],
    dimensions: list[str] | None = None,
    provider: LLMProvider | None = None,
    config: LLMConfig | None = None,
) -> dict[str, Any]:
    """Generate a structured comparison table from paper metadata and abstracts."""
    active_dimensions = dimensions or DEFAULT_DIMENSIONS
    fallback = _fallback_table(papers, active_dimensions)

    if not papers:
        return {"table": [], "notes": "No papers were provided."}
    if not provider or not _can_use_llm(config):
        return fallback

    papers_text = "\n\n".join(
        f"[{paper.get('id', index)}] {paper.get('title', '')} ({paper.get('year') or 'N/A'})\n"
        f"Venue: {paper.get('venue') or 'N/A'}\n"
        f"Abstract: {(paper.get('abstract') or '')[:1500]}"
        for index, paper in enumerate(papers)
    )
    dimensions_text = "\n".join(f"- {dimension}" for dimension in active_dimensions)
    prompt = COMPARISON_PROMPT.format(papers=papers_text, dimensions=dimensions_text)

    try:
        raw = await provider.chat(
            [
                ChatMessage(role="system", content="You extract structured data from research papers."),
                ChatMessage(role="user", content=prompt),
            ],
            config,
        )
        parsed = _parse_json_object(raw)
        table = parsed.get("table")
        if not isinstance(table, list):
            return fallback
        return {
            "table": table,
            "notes": str(parsed.get("notes") or ""),
        }
    except Exception as exc:
        logger.warning("comparison_matrix.py operation failed: {}", exc)
        return fallback
