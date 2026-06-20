"""CrossRef API 数据源 — DOI 解析和引用验证"""

from app.services.proxy import get_async_client

from app.services.paper_sources import PaperSource, PaperSourceResult


class CrossrefSource(PaperSource):
    source_name = "crossref"

    BASE_URL = "https://api.crossref.org/works"

    async def search(
        self,
        query: str,
        max_results: int = 50,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[PaperSourceResult]:
        params = {
            "query": query,
            "rows": min(max_results, 100),
        }
        if year_from:
            params["filter"] = f"from-pub-date:{year_from}"
        if year_to:
            existing = params.get("filter", "")
            sep = "," if existing else ""
            params["filter"] = f"{existing}{sep}until-pub-date:{year_to}"

        async with get_async_client() as client:
            resp = await client.get(self.BASE_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for item in data.get("message", {}).get("items", []):
            # 提取年份
            date_parts = (item.get("published-print") or item.get("published-online") or {}).get("date-parts", [[]])
            year = date_parts[0][0] if date_parts and date_parts[0] else None

            results.append(PaperSourceResult(
                title=item.get("title", [""])[0] if item.get("title") else "",
                authors=[
                    f"{a.get('given', '')} {a.get('family', '')}".strip()
                    for a in (item.get("author") or [])
                ],
                abstract=item.get("abstract", "") or "",
                year=year,
                venue=item.get("container-title", [""])[0] if item.get("container-title") else "",
                doi=item.get("DOI", ""),
                source="crossref",
                citation_count=item.get("is-referenced-by-count", 0),
                url=f"https://doi.org/{item.get('DOI', '')}" if item.get("DOI") else "",
            ))

        return results

    async def fetch_details(self, paper_id: str) -> PaperSourceResult | None:
        """按 DOI 获取详情"""
        async with get_async_client() as client:
            resp = await client.get(f"{self.BASE_URL}/{paper_id}", timeout=30)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            item = resp.json().get("message", {})

        date_parts = (item.get("published-print") or item.get("published-online") or {}).get("date-parts", [[]])
        year = date_parts[0][0] if date_parts and date_parts[0] else None

        return PaperSourceResult(
            title=item.get("title", [""])[0] if item.get("title") else "",
            authors=[
                f"{a.get('given', '')} {a.get('family', '')}".strip()
                for a in (item.get("author") or [])
            ],
            abstract=item.get("abstract", "") or "",
            year=year,
            venue=item.get("container-title", [""])[0] if item.get("container-title") else "",
            doi=item.get("DOI", ""),
            source="crossref",
            citation_count=item.get("is-referenced-by-count", 0),
        )

    async def verify_doi(self, doi: str) -> bool:
        """验证 DOI 是否存在"""
        async with get_async_client() as client:
            resp = await client.head(f"{self.BASE_URL}/{doi}", timeout=15)
            return resp.status_code == 200
