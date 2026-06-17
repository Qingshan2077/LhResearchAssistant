"""arXiv API 数据源 — 使用 arxiv 包"""

import arxiv

from app.services.paper_sources import PaperSource, PaperSourceResult


class ArxivSource(PaperSource):
    source_name = "arxiv"

    def __init__(self):
        self.client = arxiv.Client()

    async def search(
        self,
        query: str,
        max_results: int = 50,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[PaperSourceResult]:
        results = []
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance,
        )

        for result in self.client.results(search):
            year = result.published.year if result.published else None
            # 年份过滤
            if year_from and year and year < year_from:
                continue
            if year_to and year and year > year_to:
                continue

            results.append(PaperSourceResult(
                title=result.title,
                authors=[a.name for a in result.authors],
                abstract=result.summary,
                year=year,
                arxiv_id=result.entry_id.split("/")[-1] if result.entry_id else "",
                doi=result.doi or "",
                source="arxiv",
                pdf_url=result.pdf_url or "",
                url=result.entry_id or "",
            ))

        return results

    async def fetch_details(self, paper_id: str) -> PaperSourceResult | None:
        """按 arxiv_id 获取详情"""
        search = arxiv.Search(id_list=[paper_id])
        try:
            result = next(self.client.results(search))
        except StopIteration:
            return None

        return PaperSourceResult(
            title=result.title,
            authors=[a.name for a in result.authors],
            abstract=result.summary,
            year=result.published.year if result.published else None,
            arxiv_id=paper_id,
            doi=result.doi or "",
            source="arxiv",
            pdf_url=result.pdf_url or "",
            url=result.entry_id or "",
        )
