"""Semantic Scholar API 数据源"""

from app.services.proxy import get_async_client

from app.services.paper_sources import PaperSource, PaperSourceResult


class SemanticScholarSource(PaperSource):
    source_name = "semantic_scholar"

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    async def search(
        self,
        query: str,
        max_results: int = 50,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[PaperSourceResult]:
        params = {
            "query": query,
            "limit": min(max_results, 100),
            "fields": "title,authors,year,abstract,citationCount,externalIds,venue,publicationTypes,url,openAccessPdf",
        }
        if year_from or year_to:
            # Semantic Scholar 使用 year 范围语法
            years = f"{year_from or ''}-{year_to or ''}"
            if years != "-":
                params["year"] = years

        async with get_async_client() as client:
            resp = await client.get(f"{self.BASE_URL}/paper/search", params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for item in data.get("data", []):
            ext_ids = item.get("externalIds") or {}
            oa_pdf = item.get("openAccessPdf") or {}

            results.append(PaperSourceResult(
                title=item.get("title", ""),
                authors=[a.get("name", "") for a in (item.get("authors") or [])],
                abstract=item.get("abstract") or "",
                year=item.get("year"),
                venue=item.get("venue", ""),
                doi=ext_ids.get("DOI", ""),
                arxiv_id=ext_ids.get("ArXiv", ""),
                source="semantic_scholar",
                citation_count=item.get("citationCount", 0),
                url=item.get("url", ""),
                pdf_url=oa_pdf.get("url", ""),
            ))

        return results

    async def fetch_details(self, paper_id: str) -> PaperSourceResult | None:
        """按 S2 paper_id 获取详情"""
        async with get_async_client() as client:
            resp = await client.get(
                f"{self.BASE_URL}/paper/{paper_id}",
                params={
                    "fields": "title,authors,year,abstract,citationCount,externalIds,venue,url,openAccessPdf",
                },
                timeout=30,
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            item = resp.json()

        ext_ids = item.get("externalIds") or {}
        oa_pdf = item.get("openAccessPdf") or {}
        return PaperSourceResult(
            title=item.get("title", ""),
            authors=[a.get("name", "") for a in (item.get("authors") or [])],
            abstract=item.get("abstract") or "",
            year=item.get("year"),
            venue=item.get("venue", ""),
            doi=ext_ids.get("DOI", ""),
            arxiv_id=ext_ids.get("ArXiv", ""),
            source="semantic_scholar",
            citation_count=item.get("citationCount", 0),
            url=item.get("url", ""),
            pdf_url=oa_pdf.get("url", ""),
        )
