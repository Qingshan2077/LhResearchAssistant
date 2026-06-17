"""Agent Phase Boundaries — 声明式约束注册表。

每个 agent 声明自己的能力范围，防止 scope leak。
Phase Boundary 是文档级别的约束，目前不强制执行，
但为后续运行时检查（PreToolUse hook）做好准备。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AgentPhase(str, Enum):
    """Agent 归属相位。"""
    IDEA = "idea"           # 想法生成 / Socratic 对话
    SEARCH = "search"       # 文献检索
    READING = "reading"     # 阅读、知识图谱、PDF 解析
    WRITING = "writing"     # 论文写作、大纲、润色
    REVIEW = "review"       # 同行评审、rebuttal
    CHECK = "check"         # 质量检查（写作质量、failure checklist）
    META = "meta"           # 编排/管理，无边界限制


class Bucket(str, Enum):
    """
    A = 单相位 agent，只能读写自己相位的内容
    B = 多相位 agent，在 allowed_reads 范围内可读
    C = 跨 skill gate，可读多个相位但写受限
    D = 元 agent，无边界限制
    """
    A = "A"
    B = "B"
    C = "C"
    D = "D"


@dataclass
class PhaseBoundary:
    """一个 agent 的相位边界声明。"""
    agent_name: str
    phase: AgentPhase
    bucket: Bucket = Bucket.A
    blocked_writes: list[str] = field(default_factory=list)
    allowed_reads: list[AgentPhase] = field(default_factory=list)
    description: str = ""


# ── 注册表 ──────────────────────────────────────────

AGENT_BOUNDARIES: dict[str, PhaseBoundary] = {
    "review_agent": PhaseBoundary(
        agent_name="review_agent",
        phase=AgentPhase.REVIEW,
        bucket=Bucket.A,
        description="模拟审稿管线（Sprint Contract + 4角色 + meta-review + rebuttal评分）",
    ),
    "idea_agent": PhaseBoundary(
        agent_name="idea_agent",
        phase=AgentPhase.IDEA,
        bucket=Bucket.A,
        description="Idea 生成（Generator-Evaluator 分离）",
    ),
    "socratic_agent": PhaseBoundary(
        agent_name="socratic_agent",
        phase=AgentPhase.IDEA,
        bucket=Bucket.B,
        allowed_reads=[AgentPhase.SEARCH, AgentPhase.WRITING],
        description="Socratic 5层对话引导，可读取已有论文和写作项目",
    ),
    "writing_agent": PhaseBoundary(
        agent_name="writing_agent",
        phase=AgentPhase.WRITING,
        bucket=Bucket.A,
        description="论文写作（大纲、分节、润色）",
    ),
    "paper_agent": PhaseBoundary(
        agent_name="paper_agent",
        phase=AgentPhase.META,
        bucket=Bucket.D,
        description="全流程 paper agent（跨相位编排）",
    ),
    "read_agent": PhaseBoundary(
        agent_name="read_agent",
        phase=AgentPhase.READING,
        bucket=Bucket.A,
        description="论文阅读理解、思维图、知识库",
    ),
    "failure_checklist_agent": PhaseBoundary(
        agent_name="failure_checklist_agent",
        phase=AgentPhase.CHECK,
        bucket=Bucket.C,
        allowed_reads=[AgentPhase.WRITING, AgentPhase.REVIEW],
        description="7-mode AI 失败模式检查",
    ),
}
