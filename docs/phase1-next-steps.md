# LhResearchAssistant — Phase 1 剩余任务

> 给 ChatGPT 的开发任务清单
> 基于：https://github.com/Qingshan2077/LhResearchAssistant
> 当前 commit: 0c09b52

## 任务 1：搜索批量导入（最关键）

**问题**：`POST /api/v1/search/import` 端点直接报 400，无法使用。

**改为**：接收完整 paper 列表，批量写入数据库，并基于 arxiv_id/doi 去重。

修改文件：
- `backend/app/routers/search.py` 中的 `import_papers` 函数

```python
@router.post("/search/import", response_model=ImportResponse)
async def import_papers(req: ImportRequest, db: Session = Depends(get_db)):
    """
    req.paper_ids 是前端搜索结果中 paper 的临时 UUID。
    但实际上前端需要把完整 paper 数据传过来，所以改为：
      1. 前端传 papers: list[PaperCreate] 到 POST /papers/batch
      2. 或者直接把搜索结果传过来
    """
```

建议方案：**前端先调 `POST /api/v1/search` 拿到论文列表，然后调 `POST /api/v1/papers/batch` 批量导入**。这个接口已经有了，但前端 SearchPage 需要改一下 `handleImport` 和 `handleGenerateReview` 的调用逻辑。

## 任务 2：PDF 内嵌阅读器（PDF.js）

**当前**：ReaderPage 只显示"在浏览器中打开 PDF"，没有内嵌阅读器。

**改为**：真正在页面内嵌 PDF.js 渲染 PDF。方法：

1. 先加一个后端路由 `GET /api/v1/papers/{id}/pdf` 返回 PDF 文件流
2. 前端用 `<iframe>` 或 PDF.js 的 canvas 渲染

```python
# 在 backend/app/routers/papers.py 末尾添加
@router.get("/papers/{paper_id}/pdf")
async def get_paper_pdf(paper_id: str, db: Session = Depends(get_db)):
    """返回 PDF 文件"""
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper or not paper.pdf_path:
        raise HTTPException(status_code=404)
    from fastapi.responses import FileResponse
    return FileResponse(paper.pdf_path, media_type="application/pdf")
```

前端 `ReaderPage.tsx` 把 PDF 区域改成：

```tsx
{paper.pdf_path && (
  <iframe
    src={`/api/v1/papers/${id}/pdf`}
    className="w-full h-full"
  />
)}
```

这是最简单的方案。如果要更丰富的交互（高亮、搜索、缩放），需要集成 pdfjs-dist。

## 任务 3：知识图谱可视化

**当前**：`KnowledgeBasePage.tsx` 用标签云展示论文节点，没有真正的图。

**改为**：用 Cytoscape.js 渲染完整的力导向图。

```tsx
// 在 KnowledgeBasePage.tsx 中添加
import cytoscape from "cytoscape";

useEffect(() => {
  if (!graphData) return;
  const cy = cytoscape({
    container: document.getElementById("knowledge-graph"),
    elements: [
      ...graphData.nodes.map(n => ({
        data: { id: n.id, label: n.label },
        classes: n.type,
      })),
      ...graphData.edges.map(e => ({
        data: { source: e.source, target: e.target }
      }))
    ],
    style: [
      { selector: '.paper', style: { 'background-color': '#3b82f6', width: 30, height: 30 } },
      { selector: '.concept', style: { 'background-color': '#10b981', width: 20, height: 20 } },
      { selector: 'edge', style: { 'width': 1, 'line-color': '#334155' } },
    ],
    layout: { name: 'cose', padding: 20 },
  });
  return () => cy.destroy();
}, [graphData]);
```

## 任务 4：交互式思维图（React Flow）

**当前**：ReaderPage 的思维图是纯文本树状展示。

**改为**：用 React Flow 实现拖拽式思维图。

修改文件：`frontend/src/routes/ReaderPage.tsx` 中的 `MindMapView` 组件。

```tsx
import { ReactFlow, useNodesState, useEdgesState, Node, Edge } from "reactflow";
import "reactflow/dist/style.css";

// 将 mindmapData.nodes 转换为 React Flow 的 nodes + edges
```

已有数据格式：
```json
{
  "nodes": [
    {"id": "auto-root", "paper_id": "...", "parent_id": null, "label": "Title", "node_type": "root", "position": {"x": 400, "y": 0}},
    {"id": "auto-problem", "paper_id": "...", "parent_id": "auto-root", "label": "Problem", "node_type": "problem", ...}
  ]
}
```

## 任务 5：搜索去重改进

**问题**：搜索结果的 `existing_ids` 检测逻辑有误——只比较了 arxiv_id 和 doi 的 set，但如果某篇论文有 arxiv_id 而另一篇没有，会误判。

修改 `backend/app/routers/search.py` 中：

```python
# 改为从数据库查询所有已有论文的 arxiv_id 和 doi 集合
existing_arxiv = set()
existing_doi = set()
if req.project_id:
    papers_in_db = db.query(Paper).filter(Paper.project_id == req.project_id).all()
    for p in papers_in_db:
        if p.arxiv_id: existing_arxiv.add(p.arxiv_id)
        if p.doi: existing_doi.add(p.doi.lower())

# 检查 is_new
p["is_new"] = not (
    (source.arxiv_id and source.arxiv_id in existing_arxiv) or
    (source.doi and source.doi.lower() in existing_doi)
)
```

---

## 执行顺序

1. **先做任务 1**（搜索批量导入）—— 这是断裂点，搜完不能导入就没法用
2. **再做任务 2**（PDF 阅读器）—— 导入后要看论文
3. **再做任务 3+4**（图谱 + 思维图）—— 可视化
4. **最后任务 5**（去重优化）—— 小优化

## 验收标准

完成后应该能走通这个链路：
1. 打开页面 → 搜索 "transformer reinforcement learning"
2. 勾选论文 → 点"导入选中" → 论文出现在本地库
3. 上传 PDF → 点"AI 解析论文" → 看到结构化结果 + 思维图
4. 知识库页面看到力导向图
5. 输入搜索词能看到**已导入**标记
