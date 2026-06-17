"""搜索服务 — 多数据源并行检索 + 去重合并"""

import asyncio
import httpx
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
) -> tuple[list[PaperSourceResult], dict[str, int], dict[str, str]]:
    """Multi-source search, returning results, per-source counts, and per-source errors."""
    if sources is None:
        sources = list(SOURCES.keys())

    async def _search_one(name: str) -> tuple[str, list[PaperSourceResult], str | None]:
        source_cls = SOURCES.get(name)
        if not source_cls:
            return name, [], "Unknown source."
        try:
            instance = source_cls()
            results = await instance.search(
                query=query,
                max_results=max_results_per_source,
                year_from=year_from,
                year_to=year_to,
            )
            for result in results:
                _fill_pdf_url(result)
            return name, results, None
        except httpx.ConnectError:
            return name, [], "Connection failed: network unreachable."
        except httpx.TimeoutException:
            return name, [], "Request timed out."
        except httpx.HTTPStatusError as exc:
            return name, [], f"HTTP {exc.response.status_code} from source."
        except Exception as exc:
            return name, [], f"Search failed: {str(exc)[:80]}"

    tasks = [_search_one(name) for name in sources]
    source_results = await asyncio.gather(*tasks)

    # 合并
    all_results: list[PaperSourceResult] = []
    breakdown: dict[str, int] = {}
    source_errors: dict[str, str] = {}
    for name, results, error in source_results:
        all_results.extend(results)
        breakdown[name] = len(results)
        if error:
            source_errors[name] = error

    # 去重
    deduped = _deduplicate(all_results)

    return deduped, breakdown, source_errors


def _fill_pdf_url(result: PaperSourceResult) -> None:
    """Fill obvious PDF URLs from arXiv ids when upstream sources omit them."""
    if not result.pdf_url and result.arxiv_id:
        arxiv_id = result.arxiv_id.removesuffix(".pdf")
        result.pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"


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
        "pdf_download_error": "",
        "extracted_data": {},
        "citation_verified": [],
        "citation_data": "",
        "citation_cached_at": None,
        "tags": [],
        "notes": "",
        "read_status": "unread",
        "rating": 0,
        "created_at": None,
        "updated_at": None,
        "is_new": True,
    }
