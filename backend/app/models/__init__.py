"""Pydantic schemas — 请求/响应模型"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ── Paper ──────────────────────────────────────────
class PaperBase(BaseModel):
    title: str
    authors: list[str] = []
    abstract: str = ""
    year: Optional[int] = None
    venue: str = ""
    paper_type: str = ""
    doi: str = ""
    arxiv_id: str = ""
    source: str = ""
    citation_count: int = 0
    keywords: list[str] = []
    url: str = ""
    pdf_url: str = ""


class PaperCreate(PaperBase):
    project_id: Optional[str] = None


class PaperUpdate(BaseModel):
    tags: Optional[list[str]] = None
    notes: Optional[str] = None
    read_status: Optional[str] = None
    rating: Optional[int] = None


class PaperResponse(PaperBase):
    id: str = ""
    project_id: Optional[str] = None
    pdf_path: str = ""
    extracted_data: dict = {}
    tags: list[str] = []
    notes: str = ""
    read_status: str = "unread"
    rating: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_new: bool = False  # 检索结果专用，标记是否已在本地库

    model_config = {"from_attributes": True}


class PaperListResponse(BaseModel):
    items: list[PaperResponse]
    total: int
    page: int
    page_size: int


# ── 搜索 ──────────────────────────────────────────
class SearchRequest(BaseModel):
    project_id: Optional[str] = None
    query: str
    sources: list[str] = ["arxiv", "semantic_scholar", "dblp"]
    max_results_per_source: int = 50
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    venue_filter: list[str] = []
    sort_by: str = "relevance"  # relevance / citations / date


class SearchResponse(BaseModel):
    papers: list[PaperResponse]
    total_count: int
    source_breakdown: dict[str, int]


class ImportRequest(BaseModel):
    project_id: str
    paper_ids: list[str] = Field(default_factory=list)
    papers: list[PaperCreate] = Field(default_factory=list)


class ImportResponse(BaseModel):
    imported: int
    skipped: int
    papers: list[PaperResponse]


class ReviewRequest(BaseModel):
    project_id: str
    paper_ids: list[str]
    focus: str = "method_comparison"  # method_comparison / timeline / problem_centric / custom
    custom_prompt: str = ""
    language: str = "en"


# ── Knowledge ────────────────────────────────────
class KnowledgeQuery(BaseModel):
    project_id: str
    query: str
    top_k: int = 5
    include_graph_context: bool = True


class GraphData(BaseModel):
    nodes: list[dict]
    edges: list[dict]


class MindMapData(BaseModel):
    nodes: list[dict]


class MindMapUpdate(BaseModel):
    nodes: list[dict]


# ── LLM Provider ─────────────────────────────────
class ProviderCreate(BaseModel):
    name: str
    display_name: str = ""
    api_key: str = ""
    base_url: str = ""
    default_model: str = ""
    is_active: bool = True
    priority: int = 0
    max_tokens: int = 8192
    temperature: float = 0.7


class ProviderResponse(ProviderCreate):
    id: str

    model_config = {"from_attributes": True}


# ── Settings ─────────────────────────────────────
class ThemeUpdate(BaseModel):
    theme: str  # dark / light
