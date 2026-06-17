"""Paper Agent — 综述生成 Agent"""

from typing import AsyncGenerator
from sqlalchemy.orm import Session

from app.database.sqlite import Paper
from app.llm.router import get_active_provider
from app.llm import ChatMessage


def _build_review_prompt(
    papers: list[Paper],
    focus: str = "method_comparison",
    language: str = "en",
) -> str:
    """构建综述生成 prompt"""

    lang_instruction = (
        "Write the review in Chinese (中文)." if language == "zh"
        else "Write the review in English."
    )

    focus_instruction = {
        "method_comparison": (
            "Focus on comparing methodologies: analyze the key techniques, "
            "their similarities, differences, advantages, and limitations. "
            "Group papers by approach."
        ),
        "timeline": (
            "Focus on the chronological development of this field: "
            "how methods evolved over time, key breakthroughs, and paradigm shifts."
        ),
        "problem_centric": (
            "Focus on the problem space: what problems are addressed, "
            "what gaps remain, and how different works tackle the same challenges."
        ),
        "custom": "Focus on the aspects described in the custom instruction.",
    }.get(focus, "")

    paper_entries = []
    for i, p in enumerate(papers, 1):
        paper_entries.append(
            f"[{i}] {p.title}\n"
            f"    Authors: {', '.join(p.authors or [])}\n"
            f"    Year: {p.year or 'N/A'}, Venue: {p.venue or 'N/A'}\n"
            f"    Abstract: {p.abstract or 'N/A'}\n"
        )

    return f"""You are an expert in computer science research. Your task is to write a comprehensive literature review based on the provided papers.

{lang_instruction}

{focus_instruction}

Structure the review with:
1. **Introduction** — background and motivation of this research area
2. **Categorization** — group related papers and compare them
3. **Key Findings** — main results and contributions across papers
4. **Gaps and Challenges** — open problems and limitations
5. **Conclusion** — summary and future directions

Cite papers using [N] where N is the paper number in the list below.
Be specific about contributions, methods, and experimental results.
Aim for 1500-3000 words.

Papers:
{chr(10).join(paper_entries)}

Generate the review now.
"""


async def generate_review(
    papers: list[Paper],
    focus: str = "method_comparison",
    language: str = "en",
    db: Session | None = None,
) -> AsyncGenerator[dict, None]:
    """生成文献综述（SSE 流式）"""
    # 获取活跃 LLM
    if db:
        provider, config = get_active_provider(db)
    else:
        from app.llm.deepseek import DeepSeekProvider
        from app.llm import LLMConfig
        from app.config import settings
        provider = DeepSeekProvider()
        config = LLMConfig(
            api_key=settings.default_deepseek_api_key,
            base_url=settings.default_deepseek_base_url,
            model=settings.default_deepseek_model,
        )

    prompt = _build_review_prompt(papers, focus, language)
    messages = [
        ChatMessage(role="system", content=prompt),
        ChatMessage(role="user", content=f"Generate the literature review for {len(papers)} papers on the given topic."),
    ]

    # 发送进度信息
    yield {"type": "progress", "current": 0, "total": len(papers), "phase": "reading_papers"}

    # 发送论文引用信息
    for p in papers:
        yield {"type": "citation", "paper_id": p.id, "title": p.title}

    yield {"type": "progress", "current": len(papers), "total": len(papers), "phase": "generating_review"}

    # 流式生成综述
    try:
        async for chunk in provider.chat_stream(messages, config):
            yield {"type": "chunk", "content": chunk}
    except Exception as e:
        yield {"type": "error", "message": str(e)}
        return

    yield {"type": "done", "paper_count": len(papers)}


async def expand_query(query: str, db: Session | None = None) -> str:
    """扩展搜索关键词 — 生成同义词和相关概念"""
    if db:
        provider, config = get_active_provider(db)
    else:
        from app.llm.deepseek import DeepSeekProvider
        from app.llm import LLMConfig
        from app.config import settings
        provider = DeepSeekProvider()
        config = LLMConfig(
            api_key=settings.default_deepseek_api_key,
            base_url=settings.default_deepseek_base_url,
            model=settings.default_deepseek_model,
        )

    messages = [
        ChatMessage(role="system", content=(
            "You are a research search query optimizer. Given a user's research query, "
            "produce an expanded search query string that includes synonyms, related concepts, "
            "and alternative terminology. Return ONLY the expanded query text, no explanations."
        )),
        ChatMessage(role="user", content=f"Original query: {query}"),
    ]

    try:
        return await provider.chat(messages, config)
    except Exception:
        return query
