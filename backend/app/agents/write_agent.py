"""Write Agent — 写作辅助（Phase 3 实现）"""


async def generate_section(outline: str, context: str, language: str = "en") -> str:
    """生成论文章节（Phase 3 完整实现）"""
    return f"[Writing module — Phase 3. Outline: {outline[:50]}...]"


async def polish_text(text: str, style: str = "academic") -> str:
    """润色文本"""
    return text


async def generate_citation_bibtex(papers: list) -> str:
    """生成 BibTeX 引用"""
    return ""
