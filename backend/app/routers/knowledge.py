"""知识库路由 — 语义搜索 + 知识图谱 + 思维图"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.database import get_db
from app.database.sqlite import Paper, MindMapNode, PaperRelation
from app.models import KnowledgeQuery, GraphData, MindMapData, MindMapUpdate

router = APIRouter()


@router.post("/knowledge/query")
async def knowledge_query(req: KnowledgeQuery, db: Session = Depends(get_db)):
    """知识库语义搜索（SSE 流式返回 LLM 回答）"""
    # Phase 1 最小实现：基于 SQLite LIKE 搜索论文标题和摘要
    # Phase 2/7 将接入 Chroma 向量搜索
    search_term = f"%{req.query}%"
    papers = (
        db.query(Paper)
        .filter(
            Paper.project_id == req.project_id,
            (Paper.title.contains(req.query)) | (Paper.abstract.contains(req.query)),
        )
        .limit(req.top_k)
        .all()
    )

    if not papers:
        return {"answer": "No relevant papers found in the knowledge base.", "sources": []}

    sources = [{"paper_id": p.id, "title": p.title, "relevance": 1.0} for p in papers]

    # 简单拼接上下文返回
    context = "\n\n".join([
        f"Title: {p.title}\nAbstract: {p.abstract[:500]}" for p in papers
    ])

    return {
        "answer": f"Found {len(papers)} relevant papers in your knowledge base.",
        "sources": sources,
        "context": context,
    }


@router.get("/knowledge/graph")
def get_knowledge_graph(project_id: str | None = None, db: Session = Depends(get_db)):
    """获取知识图谱数据（Cytoscape.js 格式）"""
    query = db.query(Paper)
    if project_id:
        query = query.filter(Paper.project_id == project_id)

    papers = query.all()

    nodes = []
    edges = []
    concept_ids = set()

    for paper in papers:
        # 论文节点
        year_label = f" ({paper.year})" if paper.year else ""
        nodes.append({
            "id": f"paper:{paper.id}",
            "type": "paper",
            "label": f"{paper.title[:60]}{'...' if len(paper.title) > 60 else ''}{year_label}",
            "group": paper.venue or "unknown",
            "data": {
                "citation_count": paper.citation_count or 0,
                "year": paper.year,
                "read_status": paper.read_status,
            },
        })

        # 关键词节点
        for kw in (paper.keywords or []):
            kw_id = f"concept:{kw.lower().replace(' ', '_')}"
            if kw_id not in concept_ids:
                nodes.append({
                    "id": kw_id,
                    "type": "concept",
                    "label": kw,
                    "group": "concept",
                })
                concept_ids.add(kw_id)
            edges.append({
                "source": f"paper:{paper.id}",
                "target": kw_id,
                "type": "has_concept",
            })

    paper_ids = [paper.id for paper in papers]
    if paper_ids:
        relations = (
            db.query(PaperRelation)
            .filter(PaperRelation.source_paper_id.in_(paper_ids))
            .all()
        )
        visible_paper_ids = set(paper_ids)
        for rel in relations:
            if rel.target_paper_id not in visible_paper_ids:
                continue
            edges.append({
                "source": f"paper:{rel.source_paper_id}",
                "target": f"paper:{rel.target_paper_id}",
                "type": rel.relation_type,
                "label": rel.relation_type,
                "data": {
                    "description": rel.description,
                    "confidence": rel.confidence,
                },
            })

    return GraphData(nodes=nodes, edges=edges)


@router.get("/knowledge/mindmap/{paper_id}")
def get_mindmap(paper_id: str, db: Session = Depends(get_db)):
    """获取论文思维图数据"""
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    # 如果有已保存的节点，返回它们
    saved_nodes = (
        db.query(MindMapNode)
        .filter(MindMapNode.paper_id == paper_id)
        .all()
    )

    if saved_nodes:
        return MindMapData(nodes=[{
            "id": n.id,
            "paper_id": n.paper_id,
            "parent_id": n.parent_id,
            "label": n.label,
            "node_type": n.node_type,
            "content": n.content,
            "position": {"x": n.position_x, "y": n.position_y},
        } for n in saved_nodes])

    # 没有保存的节点，从 extracted_data 生成
    extracted = paper.extracted_data or {}
    if not extracted:
        return MindMapData(nodes=[])

    nodes = []
    y_offset = 0

    # 根节点：论文标题
    nodes.append({
        "id": f"auto-root",
        "paper_id": paper_id,
        "parent_id": None,
        "label": paper.title[:80],
        "node_type": "root",
        "content": "",
        "position": {"x": 400, "y": y_offset},
    })
    y_offset += 80

    # Problem
    if extracted.get("problem"):
        nodes.append({
            "id": "auto-problem",
            "paper_id": paper_id,
            "parent_id": "auto-root",
            "label": "Problem",
            "node_type": "problem",
            "content": extracted["problem"][:300],
            "position": {"x": 0, "y": y_offset},
        })
        y_offset += 80

    # Method
    method = extracted.get("method", {})
    if method:
        nodes.append({
            "id": "auto-method",
            "paper_id": paper_id,
            "parent_id": "auto-root",
            "label": f"Method: {method.get('overview', '')[:50]}",
            "node_type": "method",
            "content": method.get("overview", "")[:300],
            "position": {"x": 200, "y": y_offset},
        })
        y_offset += 80

        for comp in method.get("components", []):
            nodes.append({
                "id": f"auto-comp-{comp.get('name', 'unknown')}",
                "paper_id": paper_id,
                "parent_id": "auto-method",
                "label": comp.get("name", "Component"),
                "node_type": "sub_method",
                "content": comp.get("description", "")[:200],
                "position": {"x": 300, "y": y_offset},
            })
            y_offset += 60

    # Experiments
    exp = extracted.get("experiments", {})
    if exp:
        exp_label = f"Experiments ({len(exp.get('datasets', []))} datasets)"
        nodes.append({
            "id": "auto-exp",
            "paper_id": paper_id,
            "parent_id": "auto-root",
            "label": exp_label,
            "node_type": "experiment",
            "content": exp.get("key_results", "")[:200],
            "position": {"x": 400, "y": y_offset},
        })
        y_offset += 80

    # Contributions
    for i, contrib in enumerate(extracted.get("contributions", [])):
        nodes.append({
            "id": f"auto-contrib-{i}",
            "paper_id": paper_id,
            "parent_id": "auto-root",
            "label": f"Contribution {i+1}",
            "node_type": "conclusion",
            "content": contrib[:200],
            "position": {"x": 600, "y": y_offset + i * 60},
        })

    return MindMapData(nodes=nodes)


@router.patch("/knowledge/mindmap/{paper_id}")
def update_mindmap(paper_id: str, req: MindMapUpdate, db: Session = Depends(get_db)):
    """保存用户调整后的思维图"""
    # 删除旧节点
    db.query(MindMapNode).filter(MindMapNode.paper_id == paper_id).delete()

    # 插入新节点
    for n in req.nodes:
        node = MindMapNode(
            id=n.get("id"),
            paper_id=paper_id,
            parent_id=n.get("parent_id"),
            label=n.get("label", ""),
            node_type=n.get("node_type", "other"),
            content=n.get("content", ""),
            position_x=n.get("position", {}).get("x", 0),
            position_y=n.get("position", {}).get("y", 0),
        )
        db.add(node)

    db.commit()
    return {"saved": True}
