"""Idea Agent — Idea 生成与可行性判断（Phase 2 实现）"""

from typing import AsyncGenerator


async def generate_ideas(
    context: str,
    mode: str = "gap_analysis",
) -> AsyncGenerator[dict, None]:
    """生成研究 Idea（Phase 2 完整实现）"""
    yield {"type": "status", "message": "Idea generation module — Phase 2"}


async def evaluate_feasibility(idea: str) -> dict:
    """评估 Idea 可行性（Phase 2 完整实现）"""
    return {
        "idea": idea,
        "status": "planned",
        "novelty": 0,
        "feasibility": 0,
        "cost": 0,
        "risk": "unknown",
    }
