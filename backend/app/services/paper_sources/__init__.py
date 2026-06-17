"""统一论文数据源接口"""

from dataclasses import dataclass, field
from abc import ABC, abstractmethod


@dataclass
class PaperSourceResult:
    title: str
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    year: int | None = None
    venue: str = ""
    paper_type: str = ""
    doi: str = ""
    arxiv_id: str = ""
    source: str = ""
    citation_count: int = 0
    keywords: list[str] = field(default_factory=list)
    url: str = ""
    pdf_url: str = ""


class PaperSource(ABC):
    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 50,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[PaperSourceResult]:
        ...

    @abstractmethod
    async def fetch_details(self, paper_id: str) -> PaperSourceResult | None:
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        ...
