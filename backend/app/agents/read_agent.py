"""Read Agent — 论文解读 + 结构化提取"""

from typing import AsyncGenerator
from pathlib import Path
from sqlalchemy.orm import Session

from loguru import logger

from app.database.sqlite import Paper, MindMapNode
from app.services.pdf_parser import PDFParser
from app.database.chroma_client import index_paper_chunks
from app.llm.router import get_active_provider
from app.llm import ChatMessage


EXTRACT_PROMPT = """You are an expert research paper analyzer. Extract the following structured information from this paper's text. 
Return your response as a valid JSON object with exactly these fields:

{
  "problem": "The core problem this paper addresses",
  "background": "Relevant background and context",
  "method": {
    "overview": "Overall description of the method",
    "components": [
      {"name": "Component name", "description": "What it does", "key_insight": "Key insight"}
    ]
  },
  "experiments": {
    "datasets": ["dataset1", "dataset2"],
    "baselines": ["baseline1", "baseline2"],
    "metrics": ["metric1", "metric2"],
    "key_results": "Summary of main results",
    "ablation": "Ablation study findings"
  },
  "contributions": ["Contribution 1", "Contribution 2"],
  "limitations": ["Limitation 1"],
  "conclusion": "Conclusion of the paper"
}

Only output the JSON object, nothing else.
"""


async def parse_paper_structure(paper: Paper, db: Session) -> AsyncGenerator[dict, None]:
    """解析论文 PDF，用 LLM 提取结构化信息"""
    yield {"type": "progress", "phase": "extracting_text", "paper_id": paper.id}

    # Step 1: 提取文本
    pdf_path = paper.pdf_path
    if not pdf_path or not Path(pdf_path).exists():
        yield {"type": "error", "message": "PDF file not found"}
        return

    try:
        full_text = PDFParser.extract_text_fast(pdf_path)
    except Exception as e:
        logger.warning("read_agent.py operation failed: {}", e)
        yield {"type": "error", "message": f"PDF extraction failed: {str(e)}"}
        return

    # 截断长文本（LLM 上下文限制）
    text = full_text
    max_chars = 60000  # ~15K tokens
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[...truncated...]"

    yield {"type": "progress", "phase": "analyzing_structure", "paper_id": paper.id}

    # Step 2: LLM 结构化提取
    provider, config = get_active_provider(db)
    messages = [
        ChatMessage(role="system", content=EXTRACT_PROMPT),
        ChatMessage(role="user", content=f"Paper title: {paper.title}\n\nPaper text:\n{text}"),
    ]

    try:
        result = await provider.chat(messages, config)
    except Exception as e:
        logger.warning("read_agent.py operation failed: {}", e)
        yield {"type": "error", "message": f"LLM analysis failed: {str(e)}"}
        return

    # Step 3: 解析 JSON
    import json
    import re

    # 尝试从 markdown 代码块中提取 JSON
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", result, re.DOTALL)
    if json_match:
        result = json_match.group(1)

    try:
        extracted = json.loads(result)
    except json.JSONDecodeError:
        # 尝试修复常见格式问题
        try:
            # 去掉首尾非 JSON 字符
            clean = result.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[-2] if "```" in clean else clean
            extracted = json.loads(clean)
        except json.JSONDecodeError:
            yield {"type": "error", "message": "Failed to parse LLM output as JSON"}
            return

    # Step 4: 保存到数据库
    paper.extracted_data = extracted
    db.commit()

    yield {"type": "result", "extracted_data": extracted}

    # Step 5: 向量化写入 Chroma
    try:
        chunk_count = index_paper_chunks(paper.id, full_text)
        yield {"type": "progress", "phase": "chroma_indexed", "chunks": chunk_count}
    except Exception as e:
        logger.warning("read_agent.py operation failed: {}", e)
        yield {"type": "warning", "phase": "chroma_index_failed", "message": str(e)}

    # Step 6: 生成思维图节点
    try:
        _generate_mindmap_nodes(paper, extracted, db)
        yield {"type": "progress", "phase": "mindmap_generated", "paper_id": paper.id}
    except Exception as exc:
        logger.warning("read_agent.py operation failed: {}", exc)
        pass  # 思维图生成失败不阻塞流程

    yield {"type": "done", "paper_id": paper.id}


def _generate_mindmap_nodes(paper: Paper, extracted: dict, db: Session):
    """从结构化数据生成思维图节点"""
    # 删除旧节点
    db.query(MindMapNode).filter(MindMapNode.paper_id == paper.id).delete()

    nodes = []
    y_offset = 0

    # 根节点
    root = MindMapNode(
        paper_id=paper.id,
        parent_id=None,
        label=paper.title[:80],
        node_type="root",
        content="",
        position_x=400,
        position_y=y_offset,
    )
    db.add(root)
    db.flush()
    nodes.append(root)

    # Problem
    if extracted.get("problem"):
        prob = MindMapNode(
            paper_id=paper.id,
            parent_id=root.id,
            label="Problem",
            node_type="problem",
            content=extracted["problem"][:300],
            position_x=0,
            position_y=80,
        )
        db.add(prob)
        nodes.append(prob)

    # Method
    method = extracted.get("method", {})
    if method:
        meth = MindMapNode(
            paper_id=paper.id,
            parent_id=root.id,
            label=f"Method: {method.get('overview', '')[:50]}",
            node_type="method",
            content=method.get("overview", "")[:300],
            position_x=200,
            position_y=80,
        )
        db.add(meth)
        db.flush()
        nodes.append(meth)

        for comp in method.get("components", []):
            comp_node = MindMapNode(
                paper_id=paper.id,
                parent_id=meth.id,
                label=comp.get("name", "Component"),
                node_type="sub_method",
                content=comp.get("description", "")[:200],
                position_x=300,
                position_y=80 + len(nodes) * 40,
            )
            db.add(comp_node)
            nodes.append(comp_node)

    # Experiments
    exp = extracted.get("experiments", {})
    if exp:
        exp_node = MindMapNode(
            paper_id=paper.id,
            parent_id=root.id,
            label=f"Experiments ({len(exp.get('datasets', []))} datasets)",
            node_type="experiment",
            content=exp.get("key_results", "")[:200],
            position_x=400,
            position_y=80,
        )
        db.add(exp_node)
        nodes.append(exp_node)

    # Contributions
    for i, contrib in enumerate(extracted.get("contributions", [])):
        c_node = MindMapNode(
            paper_id=paper.id,
            parent_id=root.id,
            label=f"Contribution {i+1}",
            node_type="conclusion",
            content=contrib[:200],
            position_x=600,
            position_y=80 + i * 60,
        )
        db.add(c_node)
        nodes.append(c_node)

    db.commit()
