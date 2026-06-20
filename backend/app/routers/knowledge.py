"""知识库路由 — 语义搜索 + 知识图谱 + 思维图"""

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from loguru import logger

from app.database import get_db
from app.database.chroma_client import collection
from app.database.sqlite import Paper, MindMapNode, PaperRelation
from app.llm import ChatMessage
from app.llm.router import get_active_provider
from app.models import KnowledgeQuery, GraphData, MindMapData, MindMapUpdate

router = APIRouter()


def _normalize_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _list_values(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _paper_concepts(paper: Paper) -> list[str]:
    """Return stored keywords plus useful concepts from structured extraction."""
    extracted = paper.extracted_data if isinstance(paper.extracted_data, dict) else {}
    method = extracted.get("method") if isinstance(extracted.get("method"), dict) else {}
    experiments = (
        extracted.get("experiments")
        if isinstance(extracted.get("experiments"), dict)
        else {}
    )

    candidates: list[object] = _list_values(paper.keywords)
    candidates.extend(_list_values(extracted.get("keywords")))
    candidates.extend(
        component.get("name")
        for component in _list_values(method.get("components"))
        if isinstance(component, dict)
    )
    for field in ("datasets", "baselines", "metrics"):
        candidates.extend(_list_values(experiments.get(field)))

    concepts: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        concept = _normalize_text(candidate)
        key = concept.casefold()
        if concept and key not in seen:
            seen.add(key)
            concepts.append(concept)
    return concepts[:30]


def _local_citation_target(citation: dict, papers: list[Paper]) -> Paper | None:
    """Match a verified citation result to a paper already in this graph."""
    match = citation.get("match") if isinstance(citation.get("match"), dict) else {}
    external_ids = match.get("externalIds") if isinstance(match.get("externalIds"), dict) else {}
    cited_title = _normalize_text(match.get("title") or citation.get("citation")).casefold()
    cited_doi = _normalize_text(external_ids.get("DOI")).casefold()
    cited_arxiv = _normalize_text(external_ids.get("ArXiv")).casefold()
    cited_s2_id = _normalize_text(match.get("paperId") or citation.get("paperId"))

    for paper in papers:
        extracted = paper.extracted_data if isinstance(paper.extracted_data, dict) else {}
        local_s2_id = _normalize_text(
            extracted.get("s2_paper_id")
            or extracted.get("paperId")
            or extracted.get("semantic_scholar_id")
        )
        if cited_s2_id and local_s2_id == cited_s2_id:
            return paper
        if cited_doi and _normalize_text(paper.doi).casefold() == cited_doi:
            return paper
        if cited_arxiv and _normalize_text(paper.arxiv_id).casefold() == cited_arxiv:
            return paper
        if cited_title and _normalize_text(paper.title).casefold() == cited_title:
            return paper
    return None


@router.post("/knowledge/query")
async def knowledge_query(req: KnowledgeQuery, db: Session = Depends(get_db)):
    """知识库语义搜索：优先使用 Chroma，失败时回退到 SQLite LIKE。"""
    chunks: list[str] = []
    metadatas: list[dict] = []
    papers: list[Paper] = []

    try:
        results = collection.query(query_texts=[req.query], n_results=req.top_k)
        chunks = results.get("documents", [[]])[0] or []
        metadatas = results.get("metadatas", [[]])[0] or []
        paper_ids = []
        for metadata in metadatas:
            paper_id = metadata.get("paper_id")
            if paper_id and paper_id not in paper_ids:
                paper_ids.append(paper_id)
        if paper_ids:
            papers = (
                db.query(Paper)
                .filter(Paper.project_id == req.project_id, Paper.id.in_(paper_ids))
                .all()
            )
    except Exception as exc:
        logger.warning("knowledge.py operation failed: {}", exc)
        papers = []

    if not papers:
        papers = (
            db.query(Paper)
            .filter(
                Paper.project_id == req.project_id,
                (Paper.title.contains(req.query)) | (Paper.abstract.contains(req.query)),
            )
            .limit(req.top_k)
            .all()
        )
        chunks = [f"Title: {p.title}\nAbstract: {p.abstract[:800]}" for p in papers]
        metadatas = [{"paper_id": p.id, "chunk_index": 0} for p in papers]

    if not papers:
        return {"answer": "No relevant papers found in the knowledge base.", "sources": []}

    sources = [{"paper_id": p.id, "title": p.title, "relevance": 1.0} for p in papers]
    context = "\n\n".join([
        f"[Chunk {i + 1}] paper_id={m.get('paper_id')}\n{chunk}"
        for i, (chunk, m) in enumerate(zip(chunks, metadatas))
    ])

    answer = f"Found {len(papers)} relevant papers in your knowledge base."
    if req.include_graph_context:
        try:
            provider, config = get_active_provider(db)
            answer = await provider.chat([
                ChatMessage(role="system", content="Answer using only the retrieved paper context. Cite source paper titles when possible."),
                ChatMessage(role="user", content=f"Question: {req.query}\n\nRetrieved context:\n{context}"),
            ], config)
        except Exception as exc:
            logger.warning("knowledge.py operation failed: {}", exc)
            pass

    return {
        "answer": answer,
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
        for kw in _paper_concepts(paper):
            concept_key = re.sub(r"[^\w-]+", "_", kw.casefold()).strip("_")
            kw_id = f"concept:{concept_key}"
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
    edge_keys = {(edge["source"], edge["target"], edge["type"]) for edge in edges}
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
            edge_keys.add((
                f"paper:{rel.source_paper_id}",
                f"paper:{rel.target_paper_id}",
                rel.relation_type,
            ))

        # Verified citations contain enough metadata to infer local paper edges
        # even when no explicit PaperRelation row exists.
        for paper in papers:
            for citation in (paper.citation_verified or []):
                if not isinstance(citation, dict) or citation.get("status") != "verified":
                    continue
                target = _local_citation_target(citation, papers)
                if not target or target.id == paper.id:
                    continue
                edge_key = (f"paper:{paper.id}", f"paper:{target.id}", "cites")
                if edge_key in edge_keys:
                    continue
                match = citation.get("match") if isinstance(citation.get("match"), dict) else {}
                edges.append({
                    "source": edge_key[0],
                    "target": edge_key[1],
                    "type": "cites",
                    "label": "cites",
                    "data": {
                        "description": f"Verified citation of {target.title}",
                        "confidence": match.get("score", 1.0),
                        "inferred": True,
                    },
                })
                edge_keys.add(edge_key)

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
        "id": "auto-root",
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
