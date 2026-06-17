"""DBLP API 数据源 — CS 领域专属"""

import httpx
import xml.etree.ElementTree as ET

from app.services.paper_sources import PaperSource, PaperSourceResult


class DBLPSource(PaperSource):
    source_name = "dblp"

    SEARCH_URL = "https://dblp.org/search/publ/api"

    async def search(
        self,
        query: str,
        max_results: int = 50,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[PaperSourceResult]:
        params = {
            "q": query,
            "h": min(max_results, 200),
            "format": "json",
        }

        async with httpx.AsyncClient() as client:
            resp = await client.get(self.SEARCH_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

        results = []
        hits = (
            data.get("result", {})
            .get("hits", {})
            .get("hit", [])
        )

        for hit in hits:
            info = hit.get("info", {})
            year_str = info.get("year", "")
            year = int(year_str) if year_str and year_str.isdigit() else None

            # 年份过滤
            if year_from and year and year < year_from:
                continue
            if year_to and year and year > year_to:
                continue

            # DBLP 的 authors 可能是 dict 或 list
            authors_raw = info.get("authors", {})
            if isinstance(authors_raw, dict):
                author_list = authors_raw.get("author", [])
                if isinstance(author_list, str):
                    author_list = [author_list]
            else:
                author_list = []

            # 提取 DOI/arxiv
            doi = ""
            arxiv_id = ""
            links = info.get("links", {}).get("link", [])
            if isinstance(links, dict):
                links = [links]
            for link in links:
                if isinstance(link, dict):
                    url = link.get("href", "")
                    if "doi.org" in url:
                        doi = url.split("doi.org/")[-1]
                    elif "arxiv.org" in url:
                        arxiv_id = url.split("/abs/")[-1] if "/abs/" in url else ""

            results.append(PaperSourceResult(
                title=info.get("title", ""),
                authors=author_list if isinstance(author_list, list) else [author_list] if author_list else [],
                abstract="",  # DBLP 不提供摘要
                year=year,
                venue=info.get("venue", ""),
                doi=doi,
                arxiv_id=arxiv_id,
                source="dblp",
                url=info.get("url", ""),
            ))

        return results

    async def fetch_details(self, paper_id: str) -> PaperSourceResult | None:
        """DBLP 不支持按 ID 获取详情（使用 URL 中的 key）"""
        return None
