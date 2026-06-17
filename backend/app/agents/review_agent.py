"""Review Agent — 审稿 + 选刊（Phase 3 实现）"""


async def review_paper(
    paper_text: str,
    venue: str | None = None,
) -> dict:
    """模拟审稿"""
    return {
        "status": "planned",
        "message": "Review module — Phase 3",
    }


async def recommend_venue(paper_title: str, abstract: str) -> list[dict]:
    """选刊推荐"""
    return [
        {"venue": "NeurIPS", "match_score": 0.0, "acceptance_rate": 0.0},
    ]
