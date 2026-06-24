"""搜索服务 — 多数据源并行检索 + 去重合并"""

import asyncio
import httpx
from loguru import logger
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


def _safe_lower(value) -> str:
    return str(value or "").strip().lower()


def _deduplicate(results: list[PaperSourceResult]) -> list[PaperSourceResult]:
    """Deduplicate by DOI/arXiv/title without trusting upstream field types."""
    seen_ids: set[tuple[str, str]] = set()
    seen_titles: set[str] = set()
    deduped: list[PaperSourceResult] = []

    for result in results:
        doi = _safe_lower(getattr(result, "doi", ""))
        arxiv_id = _safe_lower(getattr(result, "arxiv_id", ""))
        title_key = _safe_lower(getattr(result, "title", "")).rstrip(".")

        dedup_key = None
        if doi:
            dedup_key = ("doi", doi)
        elif arxiv_id:
            dedup_key = ("arxiv", arxiv_id)

        if dedup_key and dedup_key in seen_ids:
            continue
        if title_key and title_key in seen_titles:
            continue

        if dedup_key:
            seen_ids.add(dedup_key)
        if title_key:
            seen_titles.add(title_key)

        deduped.append(result)

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
            results = await asyncio.wait_for(
                instance.search(
                    query=query,
                    max_results=max_results_per_source,
                    year_from=year_from,
                    year_to=year_to,
                ),
                timeout=45,
            )
            if not isinstance(results, list):
                logger.warning("Search source {} returned non-list result: {}", name, type(results).__name__)
                return name, [], "Source returned an invalid result."
            safe_results = [result for result in results if result is not None]
            for result in safe_results:
                _fill_pdf_url(result)
            return name, safe_results, None
        except asyncio.TimeoutError:
            logger.warning("Search source {} timed out", name)
            return name, [], "Source timed out after 45 seconds."
        except httpx.ConnectError:
            logger.warning("Search source {} is unreachable", name)
            return name, [], "Connection failed: network unreachable."
        except httpx.TimeoutException:
            logger.warning("Search source {} request timed out", name)
            return name, [], "Request timed out."
        except httpx.HTTPStatusError as exc:
            logger.warning("Search source {} returned HTTP {}", name, exc.response.status_code)
            return name, [], f"HTTP {exc.response.status_code} from source."
        except Exception as exc:
            logger.exception("Search source {} failed", name)
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
    pdf_url = str(getattr(result, "pdf_url", "") or "").strip()
    arxiv_id = str(getattr(result, "arxiv_id", "") or "").strip().removesuffix(".pdf")
    if not pdf_url and arxiv_id:
        result.pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"


def _as_text(value) -> str:
    if value is None:
        return ""
    return str(value)


def _as_text_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _as_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def source_to_paper_dict(source: PaperSourceResult) -> dict:
    """Convert a PaperSourceResult into a response-safe API dictionary."""
    import uuid
    return {
        "id": str(uuid.uuid4()),
        "project_id": None,
        "title": _as_text(source.title) or "Untitled paper",
        "authors": _as_text_list(source.authors),
        "abstract": _as_text(source.abstract),
        "year": source.year if isinstance(source.year, int) else None,
        "venue": _as_text(source.venue),
        "paper_type": _as_text(source.paper_type),
        "doi": _as_text(source.doi),
        "arxiv_id": _as_text(source.arxiv_id),
        "source": _as_text(source.source),
        "citation_count": _as_int(source.citation_count),
        "keywords": _as_text_list(source.keywords),
        "url": _as_text(source.url),
        "pdf_url": _as_text(source.pdf_url),
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
