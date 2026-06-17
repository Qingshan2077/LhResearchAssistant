"""Venue recommendation helpers."""

import json
import re
from collections import Counter

from app.llm import ChatMessage, LLMConfig, LLMProvider


CCF_VENUES = [
    {
        "name": "NeurIPS",
        "full_name": "Conference on Neural Information Processing Systems",
        "field": "AI/ML",
        "ccf_rank": "A",
        "acceptance_rate": 0.23,
        "avg_review_weeks": 12,
        "paper_types": ["conference"],
        "keywords": ["machine learning", "deep learning", "optimization", "representation", "generative"],
    },
    {
        "name": "ICML",
        "full_name": "International Conference on Machine Learning",
        "field": "AI/ML",
        "ccf_rank": "A",
        "acceptance_rate": 0.27,
        "avg_review_weeks": 12,
        "paper_types": ["conference"],
        "keywords": ["machine learning", "optimization", "learning theory", "reinforcement learning"],
    },
    {
        "name": "AAAI",
        "full_name": "AAAI Conference on Artificial Intelligence",
        "field": "AI",
        "ccf_rank": "A",
        "acceptance_rate": 0.24,
        "avg_review_weeks": 10,
        "paper_types": ["conference"],
        "keywords": ["artificial intelligence", "planning", "reasoning", "agent", "knowledge"],
    },
    {
        "name": "IJCAI",
        "full_name": "International Joint Conference on Artificial Intelligence",
        "field": "AI",
        "ccf_rank": "A",
        "acceptance_rate": 0.18,
        "avg_review_weeks": 10,
        "paper_types": ["conference"],
        "keywords": ["artificial intelligence", "multi-agent", "knowledge", "reasoning"],
    },
    {
        "name": "CVPR",
        "full_name": "IEEE/CVF Conference on Computer Vision and Pattern Recognition",
        "field": "CV",
        "ccf_rank": "A",
        "acceptance_rate": 0.25,
        "avg_review_weeks": 11,
        "paper_types": ["conference"],
        "keywords": ["computer vision", "image", "video", "detection", "segmentation", "vision-language"],
    },
    {
        "name": "ICCV",
        "full_name": "IEEE/CVF International Conference on Computer Vision",
        "field": "CV",
        "ccf_rank": "A",
        "acceptance_rate": 0.26,
        "avg_review_weeks": 11,
        "paper_types": ["conference"],
        "keywords": ["computer vision", "image", "video", "3d", "recognition"],
    },
    {
        "name": "ECCV",
        "full_name": "European Conference on Computer Vision",
        "field": "CV",
        "ccf_rank": "B",
        "acceptance_rate": 0.28,
        "avg_review_weeks": 11,
        "paper_types": ["conference"],
        "keywords": ["computer vision", "image", "video", "detection", "segmentation"],
    },
    {
        "name": "ACL",
        "full_name": "Annual Meeting of the Association for Computational Linguistics",
        "field": "NLP",
        "ccf_rank": "A",
        "acceptance_rate": 0.25,
        "avg_review_weeks": 10,
        "paper_types": ["conference"],
        "keywords": ["nlp", "language model", "translation", "dialogue", "information extraction"],
    },
    {
        "name": "EMNLP",
        "full_name": "Conference on Empirical Methods in Natural Language Processing",
        "field": "NLP",
        "ccf_rank": "B",
        "acceptance_rate": 0.27,
        "avg_review_weeks": 10,
        "paper_types": ["conference"],
        "keywords": ["nlp", "language model", "empirical", "text", "retrieval"],
    },
    {
        "name": "NAACL",
        "full_name": "North American Chapter of the ACL",
        "field": "NLP",
        "ccf_rank": "C",
        "acceptance_rate": 0.28,
        "avg_review_weeks": 10,
        "paper_types": ["conference"],
        "keywords": ["nlp", "language model", "text", "speech", "dialogue"],
    },
    {
        "name": "OSDI",
        "full_name": "USENIX Symposium on Operating Systems Design and Implementation",
        "field": "Systems",
        "ccf_rank": "A",
        "acceptance_rate": 0.18,
        "avg_review_weeks": 14,
        "paper_types": ["conference"],
        "keywords": ["operating system", "distributed system", "storage", "runtime", "kernel"],
    },
    {
        "name": "SOSP",
        "full_name": "ACM Symposium on Operating Systems Principles",
        "field": "Systems",
        "ccf_rank": "A",
        "acceptance_rate": 0.17,
        "avg_review_weeks": 14,
        "paper_types": ["conference"],
        "keywords": ["operating system", "distributed system", "storage", "runtime", "kernel"],
    },
    {
        "name": "SIGCOMM",
        "full_name": "ACM SIGCOMM Conference",
        "field": "Networking",
        "ccf_rank": "A",
        "acceptance_rate": 0.20,
        "avg_review_weeks": 13,
        "paper_types": ["conference"],
        "keywords": ["network", "protocol", "routing", "datacenter", "internet"],
    },
    {
        "name": "SIGMOD",
        "full_name": "ACM SIGMOD International Conference on Management of Data",
        "field": "Database",
        "ccf_rank": "A",
        "acceptance_rate": 0.25,
        "avg_review_weeks": 12,
        "paper_types": ["conference"],
        "keywords": ["database", "query", "transaction", "data management", "index"],
    },
    {
        "name": "VLDB",
        "full_name": "International Conference on Very Large Data Bases",
        "field": "Database",
        "ccf_rank": "A",
        "acceptance_rate": 0.25,
        "avg_review_weeks": 12,
        "paper_types": ["conference"],
        "keywords": ["database", "query", "transaction", "data management", "analytics"],
    },
    {
        "name": "KDD",
        "full_name": "ACM SIGKDD Conference on Knowledge Discovery and Data Mining",
        "field": "Data Mining",
        "ccf_rank": "A",
        "acceptance_rate": 0.20,
        "avg_review_weeks": 12,
        "paper_types": ["conference"],
        "keywords": ["data mining", "graph learning", "recommendation", "analytics", "knowledge discovery"],
    },
    {
        "name": "ICSE",
        "full_name": "International Conference on Software Engineering",
        "field": "Software Engineering",
        "ccf_rank": "A",
        "acceptance_rate": 0.22,
        "avg_review_weeks": 13,
        "paper_types": ["conference"],
        "keywords": ["software engineering", "program analysis", "testing", "developer", "repository"],
    },
    {
        "name": "FSE",
        "full_name": "ACM International Conference on the Foundations of Software Engineering",
        "field": "Software Engineering",
        "ccf_rank": "A",
        "acceptance_rate": 0.25,
        "avg_review_weeks": 13,
        "paper_types": ["conference"],
        "keywords": ["software engineering", "program analysis", "testing", "verification"],
    },
    {
        "name": "ASE",
        "full_name": "IEEE/ACM International Conference on Automated Software Engineering",
        "field": "Software Engineering",
        "ccf_rank": "B",
        "acceptance_rate": 0.25,
        "avg_review_weeks": 12,
        "paper_types": ["conference"],
        "keywords": ["software engineering", "automation", "program repair", "testing"],
    },
    {
        "name": "TPAMI",
        "full_name": "IEEE Transactions on Pattern Analysis and Machine Intelligence",
        "field": "CV/AI",
        "ccf_rank": "A",
        "acceptance_rate": 0.05,
        "avg_review_weeks": 24,
        "paper_types": ["journal"],
        "keywords": ["computer vision", "pattern recognition", "machine learning", "image"],
    },
    {
        "name": "IJCV",
        "full_name": "International Journal of Computer Vision",
        "field": "CV",
        "ccf_rank": "A",
        "acceptance_rate": 0.12,
        "avg_review_weeks": 24,
        "paper_types": ["journal"],
        "keywords": ["computer vision", "image", "video", "3d", "recognition"],
    },
    {
        "name": "JMLR",
        "full_name": "Journal of Machine Learning Research",
        "field": "AI/ML",
        "ccf_rank": "A",
        "acceptance_rate": 0.10,
        "avg_review_weeks": 24,
        "paper_types": ["journal"],
        "keywords": ["machine learning", "learning theory", "optimization", "statistics"],
    },
]


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z][a-zA-Z0-9+-]{2,}", text.lower())}


def _keyword_score(text: str, venue: dict) -> tuple[float, list[str]]:
    paper_tokens = _tokens(text)
    keyword_hits = []
    for keyword in venue.get("keywords", []):
        keyword_tokens = _tokens(keyword)
        if keyword_tokens and keyword_tokens.issubset(paper_tokens):
            keyword_hits.append(keyword)

    field_hits = [part for part in re.split(r"[/\s]+", venue.get("field", "").lower()) if part and part in paper_tokens]
    raw_score = min(1.0, (len(keyword_hits) * 0.18) + (len(field_hits) * 0.12))
    return raw_score, keyword_hits + field_hits


def _rank_boost(rank: str) -> float:
    return {"A": 0.08, "B": 0.04, "C": 0.01}.get(rank.upper(), 0.0)


def _fallback_recommendations(title: str, abstract: str, method_keywords: list[str]) -> list[dict]:
    text = " ".join([title, abstract, " ".join(method_keywords)])
    scored = []
    for venue in CCF_VENUES:
        keyword_score, hits = _keyword_score(text, venue)
        score = max(0.18, min(0.95, keyword_score + _rank_boost(venue["ccf_rank"])))
        reason = (
            f"关键词匹配: {', '.join(hits[:4])}。"
            if hits
            else f"根据题目和摘要的通用主题，{venue['field']} 方向存在潜在匹配。"
        )
        scored.append(_venue_result(venue, score, reason))

    scored.sort(key=lambda item: item["match_score"], reverse=True)
    return scored[:5]


def _venue_result(venue: dict, score: float, reason: str) -> dict:
    paper_types = venue.get("paper_types") or ["conference"]
    return {
        "name": venue["name"],
        "full_name": venue.get("full_name", ""),
        "field": venue.get("field", ""),
        "ccf_rank": venue.get("ccf_rank", ""),
        "acceptance_rate": venue.get("acceptance_rate", 0),
        "match_score": round(max(0.0, min(1.0, score)), 2),
        "match_reason": reason,
        "avg_review_weeks": venue.get("avg_review_weeks", 0),
        "paper_type": paper_types[0],
    }


def _parse_llm_json(raw: str) -> list[dict]:
    match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", raw, re.DOTALL)
    if match:
        raw = match.group(1)
    parsed = json.loads(raw)
    return parsed if isinstance(parsed, list) else []


def _can_use_llm(config: LLMConfig) -> bool:
    base_url = (config.base_url or "").lower()
    return bool(config.api_key) or "localhost" in base_url or "127.0.0.1" in base_url


async def recommend_venues(
    title: str,
    abstract: str,
    method_keywords: list[str],
    provider: LLMProvider | None,
    config: LLMConfig | None,
) -> list[dict]:
    """Recommend the best matching CS venues."""
    fallback = _fallback_recommendations(title, abstract, method_keywords)
    if not provider or not config or not _can_use_llm(config):
        return fallback

    candidate_names = [item["name"] for item in fallback[:10]]
    candidate_map = {venue["name"].lower(): venue for venue in CCF_VENUES}
    prompt = f"""Match this computer science paper to the best 5 venues.

Paper title:
{title}

Abstract:
{abstract or "N/A"}

Method keywords:
{", ".join(method_keywords) or "N/A"}

Candidate venues:
{json.dumps([v for v in CCF_VENUES if v["name"] in candidate_names], ensure_ascii=False)}

Return JSON only. Use this schema:
[
  {{"name": "NeurIPS", "match_score": 0.86, "match_reason": "short reason"}}
]
"""
    try:
        raw = await provider.chat([
            ChatMessage(role="system", content="You recommend rigorous CS publication venues."),
            ChatMessage(role="user", content=prompt),
        ], config)
        recommendations = []
        for item in _parse_llm_json(raw):
            venue = candidate_map.get(str(item.get("name", "")).lower())
            if not venue:
                continue
            score = float(item.get("match_score", 0.5))
            reason = str(item.get("match_reason", "") or "LLM judged this venue as a strong topical fit.")
            recommendations.append(_venue_result(venue, score, reason))

        if recommendations:
            seen = {item["name"] for item in recommendations}
            recommendations.extend([item for item in fallback if item["name"] not in seen])
            return recommendations[:5]
    except Exception:
        pass

    if method_keywords:
        counts = Counter(method_keywords)
        keyword_hint = ", ".join(keyword for keyword, _ in counts.most_common(3))
        for item in fallback:
            item["match_reason"] = f"{item['match_reason']} 兜底规则参考关键词: {keyword_hint}。"
    return fallback
