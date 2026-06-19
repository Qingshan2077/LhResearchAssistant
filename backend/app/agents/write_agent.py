"""Write Agent — guided academic writing."""

from typing import AsyncGenerator

from sqlalchemy.orm import Session

from loguru import logger

from app.database.chroma_client import collection
from app.database.sqlite import Paper
from app.llm import ChatMessage, LLMConfig, LLMProvider


def _paper_context(papers: list[Paper]) -> str:
    entries = []
    for paper in papers:
        entries.append(
            "\n".join([
                f"Paper ID: {paper.id}",
                f"Title: {paper.title}",
                f"Authors: {', '.join(paper.authors or [])}",
                f"Year: {paper.year or 'N/A'}",
                f"Venue: {paper.venue or 'N/A'}",
                f"Abstract: {(paper.abstract or '')[:1000]}",
            ])
        )
    return "\n\n".join(entries)


def _retrieve_chunks(section_name: str, paper_ids: list[str], top_k: int = 8) -> list[str]:
    try:
        results = collection.query(query_texts=[section_name], n_results=max(top_k * 3, top_k))
        docs = results.get("documents", [[]])[0] or []
        metas = results.get("metadatas", [[]])[0] or []
    except Exception as exc:
        logger.warning("write_agent.py operation failed: {}", exc)
        return []

    chunks = []
    paper_filter = set(paper_ids)
    for doc, meta in zip(docs, metas):
        if paper_filter and meta.get("paper_id") not in paper_filter:
            continue
        chunks.append(f"[{meta.get('paper_id')}]\n{doc}")
        if len(chunks) >= top_k:
            break
    return chunks


def _outline_text(outline: list[dict]) -> str:
    lines = []
    for item in outline:
        title = item.get("title") or item.get("section") or "Untitled"
        goal = item.get("goal") or item.get("description") or ""
        lines.append(f"- {title}: {goal}")
        for sub in item.get("subsections", []) or []:
            if isinstance(sub, dict):
                lines.append(f"  - {sub.get('title', 'Subsection')}: {sub.get('goal', '')}")
            else:
                lines.append(f"  - {sub}")
    return "\n".join(lines)


async def generate_section(
    outline: list[dict],
    section_name: str,
    context_papers: list[str],
    language: str,
    db: Session,
    provider: LLMProvider | None,
    config: LLMConfig | None,
    style: str = "academic",
) -> AsyncGenerator[dict, None]:
    """Generate a section with paper-id anchored claims."""
    papers = db.query(Paper).filter(Paper.id.in_(context_papers)).all() if context_papers else []
    chunks = _retrieve_chunks(section_name, context_papers)

    yield {
        "type": "status",
        "message": f"Loaded {len(papers)} papers and {len(chunks)} retrieved chunks",
    }

    if not provider or not config:
        fallback = (
            f"\\section{{{section_name}}}\n\n"
            f"This section should synthesize the selected literature and cite claims using paper ID anchors "
            f"such as [{papers[0].id if papers else 'paper_id'}]."
        )
        yield {"type": "chunk", "content": fallback}
        yield {"type": "done"}
        return

    language_rule = "Write in Chinese." if language == "zh" else "Write in English."
    prompt = f"""You are helping draft an academic paper section.

Section to write: {section_name}
Style: {style}
Language: {language_rule}

Full outline:
{_outline_text(outline)}

Requirements:
- Produce polished LaTeX-ready prose.
- Every literature claim must include paper ID anchors like [paper_id].
- Do not invent citations outside the provided papers/chunks.
- Prefer precise technical claims over generic wording.

Selected paper metadata:
{_paper_context(papers)}

Retrieved chunks:
{chr(10).join(chunks) if chunks else 'No Chroma chunks available. Use paper abstracts only.'}
"""

    try:
        async for token in provider.chat_stream([
            ChatMessage(role="system", content="You write rigorous academic paper sections."),
            ChatMessage(role="user", content=prompt),
        ], config):
            yield {"type": "chunk", "content": token}
    except Exception as exc:
        logger.warning("write_agent.py operation failed: {}", exc)
        yield {"type": "error", "message": str(exc)}

    yield {"type": "done"}


async def generate_outline(
    title: str,
    papers: list[Paper],
    language: str,
    provider: LLMProvider | None,
    config: LLMConfig | None,
) -> list[dict]:
    if not provider or not config:
        return _fallback_outline(language)

    prompt = f"""Generate a concise academic paper outline for this paper title:
{title}

Use these related papers as context:
{_paper_context(papers)}

Return JSON only: a list of objects with keys title, goal, subsections.
Language: {"Chinese" if language == "zh" else "English"}.
"""
    try:
        import json
        import re

        raw = await provider.chat([
            ChatMessage(role="system", content="You generate structured academic paper outlines."),
            ChatMessage(role="user", content=prompt),
        ], config)
        match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", raw, re.DOTALL)
        if match:
            raw = match.group(1)
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
    except Exception as exc:
        logger.warning("write_agent.py operation failed: {}", exc)
        pass
    return _fallback_outline(language)


async def polish_text(
    text: str,
    style: str,
    language: str,
    preserve_technical: bool,
    provider: LLMProvider | None,
    config: LLMConfig | None,
) -> str:
    if not provider or not config:
        return text

    prompt = f"""Polish the academic text below.

Style: {style}
Language: {"Chinese" if language == "zh" else "English"}
Preserve technical terms: {preserve_technical}

Return only the polished text.

Text:
{text}
"""
    try:
        return await provider.chat([
            ChatMessage(role="system", content="You polish academic writing without changing meaning."),
            ChatMessage(role="user", content=prompt),
        ], config)
    except Exception as exc:
        logger.warning("write_agent.py operation failed: {}", exc)
        return text


def _fallback_outline(language: str) -> list[dict]:
    if language == "zh":
        return [
            {"title": "引言", "goal": "研究动机、问题定义和贡献。", "subsections": []},
            {"title": "相关工作", "goal": "梳理核心文献并定位差异。", "subsections": []},
            {"title": "方法", "goal": "描述方法框架、模块和设计理由。", "subsections": []},
            {"title": "实验", "goal": "数据集、基线、指标和主要结果。", "subsections": []},
            {"title": "结论", "goal": "总结发现、局限和未来工作。", "subsections": []},
        ]
    return [
        {"title": "Introduction", "goal": "Motivation, problem statement, and contributions.", "subsections": []},
        {"title": "Related Work", "goal": "Position the paper against the literature.", "subsections": []},
        {"title": "Method", "goal": "Describe the proposed method and design choices.", "subsections": []},
        {"title": "Experiments", "goal": "Datasets, baselines, metrics, and results.", "subsections": []},
        {"title": "Conclusion", "goal": "Summarize findings, limitations, and future work.", "subsections": []},
    ]
