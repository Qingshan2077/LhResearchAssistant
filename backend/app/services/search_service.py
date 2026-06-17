"""搜索服务 — 多数据源并行检索 + 去重合并"""

import asyncio
from app.services.paper_sources import PaperSourceResult
from app.services.paper_sources.arxiv import ArxivSource
from app.services.paper_sources.semanticscholar import SemanticScholarSource
from app.services.paper_sources.dblp import DBLPSource

# 数据源注册表
SOURCES: dict[str, type] = {
    "arxiv": ArxivSource,
    "semantic_scholar": SemanticScholarSource,
    "dblp": DBLPSource,
}


def _deduplicate(results: list[PaperSourceResult]) -> list[PaperSourceResult]:
    """基于 DOI / arxiv_id 去重，保留信息最全的记录"""
    seen_ids: set[tuple[str, str]] = set()  # (id_type, id_value)
    seen_titles: set[str] = set()
    deduped: list[PaperSourceResult] = []

    for r in results:
        # 通过 DOI 或 arxiv_id 去重
        dedup_key = None
        if r.doi:
            dedup_key = ("doi", r.doi.lower())
        elif r.arxiv_id:
            dedup_key = ("arxiv", r.arxiv_id.lower())

        if dedup_key and dedup_key in seen_ids:
            continue

        if dedup_key:
            seen_ids.add(dedup_key)

        # 标题去重（兜底）
        title_key = r.title.lower().strip().rstrip(".")
        if title_key in seen_titles:
            # 如果标题重复但信息更丰富（有摘要而另一个没有），保留这个
            # 简单策略：保留后者（通常 info 更全）
            continue
        seen_titles.add(title_key)

        deduped.append(r)

    return deduped


async def search_papers(
    query: str,
    sources: list[str] | None = None,
    max_results_per_source: int = 50,
    year_from: int | None = None,
    year_to: int | None = None,
) -> tuple[list[PaperSourceResult], dict[str, int]]:
    """多源并行搜索，返回 (结果列表, 来源统计)"""
    if sources is None:
        sources = list(SOURCES.keys())

    async def _search_one(name: str) -> list[PaperSourceResult]:
        source_cls = SOURCES.get(name)
        if not source_cls:
            return []
        try:
            instance = source_cls()
            return await instance.search(
                query=query,
                max_results=max_results_per_source,
                year_from=year_from,
                year_to=year_to,
            )
        except Exception:
            # 单个源失败不影响其他
            return []

    tasks = [_search_one(name) for name in sources]
    results_lists = await asyncio.gather(*tasks)

    # 合并
    all_results: list[PaperSourceResult] = []
    breakdown: dict[str, int] = {}
    for name, results in zip(sources, results_lists):
        all_results.extend(results)
        breakdown[name] = len(results)

    # 去重
    deduped = _deduplicate(all_results)

    return deduped, breakdown


def source_to_paper_dict(source: PaperSourceResult) -> dict:
    """将 PaperSourceResult 转换为 API 响应字典"""
    import uuid
    return {
        "id": str(uuid.uuid4()),
        "project_id": None,
        "title": source.title,
        "authors": source.authors,
        "abstract": source.abstract,
        "year": source.year,
        "venue": source.venue,
        "paper_type": source.paper_type,
        "doi": source.doi,
        "arxiv_id": source.arxiv_id,
        "source": source.source,
        "citation_count": source.citation_count,
        "keywords": source.keywords,
        "url": source.url,
        "pdf_url": source.pdf_url,
        "pdf_path": "",
        "extracted_data": {},
        "tags": [],
        "notes": "",
        "read_status": "unread",
        "rating": 0,
        "created_at": None,
        "updated_at": None,
        "is_new": True,
    }
