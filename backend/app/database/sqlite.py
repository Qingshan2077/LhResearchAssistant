"""SQLAlchemy ORM Models — 完整数据模型"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean,
    DateTime, JSON, ForeignKey,
)
from sqlalchemy.orm import relationship

from app.database import Base
from app.services.crypto import decrypt_secret, encrypt_secret


def _uuid():
    return str(uuid.uuid4())


def _utcnow():
    return datetime.now(timezone.utc)


# ── 项目 ──────────────────────────────────────────
class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    papers = relationship("Paper", back_populates="project", cascade="all, delete-orphan")
    writing_projects = relationship("WritingProject", back_populates="project", cascade="all, delete-orphan")


# ── 论文 ──────────────────────────────────────────
class Paper(Base):
    __tablename__ = "papers"

    id = Column(String(36), primary_key=True, default=_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=True)

    # 元数据
    title = Column(String(1024), nullable=False)
    authors = Column(JSON, default=list)
    abstract = Column(Text, default="")
    year = Column(Integer, nullable=True)
    venue = Column(String(512), default="")
    paper_type = Column(String(32), default="")    # conference / journal / preprint / workshop
    doi = Column(String(255), default="")
    arxiv_id = Column(String(64), default="")
    source = Column(String(32), default="")        # arxiv / semantic_scholar / dblp / manual / crossref
    citation_count = Column(Integer, default=0)
    keywords = Column(JSON, default=list)
    url = Column(String(1024), default="")
    pdf_url = Column(String(1024), default="")

    # 本地数据
    pdf_path = Column(String(1024), default="")       # 本地缓存路径
    pdf_download_error = Column(Text, default="")     # PDF download failure reason
    extracted_data = Column(JSON, default=dict)        # LLM 结构化提取结果
    citation_verified = Column(JSON, default=list)     # S2 citation verification results
    citation_data = Column(Text, default="")           # Cached citation graph JSON
    citation_cached_at = Column(DateTime, nullable=True)
    tags = Column(JSON, default=list)                  # 用户标签
    notes = Column(Text, default="")                   # encrypted user notes

    @property
    def decrypted_notes(self) -> str:
        """Return notes while remaining compatible with legacy plaintext rows."""
        return decrypt_secret(self.notes or "")

    def set_encrypted_notes(self, plaintext: str) -> None:
        self.notes = encrypt_secret(plaintext)

    read_status = Column(String(16), default="unread") # unread / reading / read
    rating = Column(Integer, default=0)                # 用户评分 1-5

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # 关系
    project = relationship("Project", back_populates="papers")
    relations_out = relationship(
        "PaperRelation",
        foreign_keys="PaperRelation.source_paper_id",
        back_populates="source_paper",
        cascade="all, delete-orphan",
    )
    relations_in = relationship(
        "PaperRelation",
        foreign_keys="PaperRelation.target_paper_id",
        back_populates="target_paper",
        cascade="all, delete-orphan",
    )
    mindmap_nodes = relationship("MindMapNode", back_populates="paper", cascade="all, delete-orphan")


# ── 论文关系 ──────────────────────────────────────
class PaperRelation(Base):
    """论文间关系: cites / compared_to / extends / conflicts_with / implements / evaluates"""

    __tablename__ = "paper_relations"

    id = Column(String(36), primary_key=True, default=_uuid)
    source_paper_id = Column(String(36), ForeignKey("papers.id"), nullable=False)
    target_paper_id = Column(String(36), ForeignKey("papers.id"), nullable=False)
    relation_type = Column(String(32), nullable=False)
    description = Column(Text, default="")
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=_utcnow)

    source_paper = relationship("Paper", foreign_keys=[source_paper_id], back_populates="relations_out")
    target_paper = relationship("Paper", foreign_keys=[target_paper_id], back_populates="relations_in")


# ── 思维图节点 ────────────────────────────────────
class MindMapNode(Base):
    """论文思维图节点。node_type: problem / background / method / sub_method / experiment / 
       dataset / result / conclusion / limitation / future"""

    __tablename__ = "mindmap_nodes"

    id = Column(String(36), primary_key=True, default=_uuid)
    paper_id = Column(String(36), ForeignKey("papers.id"), nullable=False)
    parent_id = Column(String(36), ForeignKey("mindmap_nodes.id"), nullable=True)
    label = Column(String(255), nullable=False)
    node_type = Column(String(32), default="other")
    content = Column(Text, default="")
    position_x = Column(Float, default=0.0)
    position_y = Column(Float, default=0.0)
    created_at = Column(DateTime, default=_utcnow)

    paper = relationship("Paper", back_populates="mindmap_nodes")
    children = relationship(
        "MindMapNode",
        back_populates="parent",
        cascade="all, delete-orphan",
        remote_side=[parent_id],
    )
    parent = relationship("MindMapNode", remote_side=[id], back_populates="children")


# ── LLM Provider 配置 ────────────────────────────
class LLMProvider(Base):
    """LLM 提供商配置"""

    __tablename__ = "llm_providers"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(64), nullable=False)             # deepseek / openai / claude / ollama / custom
    display_name = Column(String(128), default="")
    api_key = Column(String(1024), default="")
    base_url = Column(String(512), default="")
    default_model = Column(String(128), default="")
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
    max_tokens = Column(Integer, default=8192)
    temperature = Column(Float, default=0.7)
    last_test_at = Column(DateTime, nullable=True)
    last_test_success = Column(Boolean, nullable=True)
    last_test_latency = Column(Integer, default=0)


class AppSetting(Base):
    """Persistent application-level key-value setting."""

    __tablename__ = "app_settings"

    key = Column(String(64), primary_key=True)
    value = Column(Text, default="")
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class LLMUsage(Base):
    __tablename__ = "llm_usage"

    id = Column(String(36), primary_key=True, default=_uuid)
    timestamp = Column(DateTime, default=_utcnow, index=True)
    provider_id = Column(String(36), nullable=True)
    provider_name = Column(String(64), default="")
    model = Column(String(128), default="")
    function_name = Column(String(64), default="")
    tokens_in = Column(Integer, default=0)
    tokens_out = Column(Integer, default=0)
    duration_ms = Column(Integer, default=0)
    status = Column(String(16), default="success")
    error_msg = Column(String(512), default="")


# ── 写作项目 ──────────────────────────────────────
class WritingProject(Base):
    __tablename__ = "writing_projects"

    id = Column(String(36), primary_key=True, default=_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    title = Column(String(512), nullable=False)
    target_venue = Column(String(256), default="")
    language = Column(String(8), default="en")       # en / zh
    template = Column(String(128), default="")
    external_editor_path = Column(String(1024), default="")
    outline = Column(JSON, default=list)
    latex_project_path = Column(String(1024), default="")
    created_at = Column(DateTime, default=_utcnow)

    project = relationship("Project", back_populates="writing_projects")


# ── 搜索历史 ──────────────────────────────────────
class SearchHistory(Base):
    __tablename__ = "search_histories"

    id = Column(String(36), primary_key=True, default=_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=True)
    query = Column(String(1024), nullable=False)
    filters = Column(JSON, default=dict)
    result_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)

# ── Idea 与 Socratic 历史 ─────────────────────────
class SocraticSession(Base):
    __tablename__ = "socratic_sessions"

    id = Column(String(36), primary_key=True, default=_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=True, index=True)
    title = Column(String(255), default="")
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    intent = Column(String(32), default="exploratory")
    layer = Column(Integer, default=1)
    turn_count = Column(Integer, default=0)
    is_converged = Column(Boolean, default=False)
    summary_json = Column(JSON, nullable=True)
    convergence_json = Column(JSON, nullable=True)
    insights_list = Column(JSON, nullable=True)
    layer_turns_json = Column(JSON, nullable=True)
    rq_history_json = Column(JSON, nullable=True)
    active_turn_index = Column(Integer, nullable=True)


class SocraticMessage(Base):
    __tablename__ = "socratic_messages"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(String(36), ForeignKey("socratic_sessions.id"), nullable=False, index=True)
    role = Column(String(16), nullable=False)
    content = Column(Text, nullable=False)
    turn_index = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=_utcnow)


class SocraticInsight(Base):
    __tablename__ = "socratic_insights"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(String(36), ForeignKey("socratic_sessions.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    turn_index = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=_utcnow)


class IdeaHistory(Base):
    __tablename__ = "idea_history"

    id = Column(String(36), primary_key=True, default=_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=True, index=True)
    title = Column(String(255), default="")
    created_at = Column(DateTime, default=_utcnow)
    mode = Column(String(32), nullable=False)
    paper_ids = Column(JSON, default=list)
    custom_prompt = Column(Text, default="")
    domain_a = Column(String(128), default="")
    domain_b = Column(String(128), default="")
    generated_content = Column(Text, default="")
    evaluations = Column(JSON, default=list)
