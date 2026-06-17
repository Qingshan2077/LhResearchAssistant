<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Qingshan2077/LhResearchAssistant/main/assets/logo-dark.png">
  <img alt="LhResearchAssistant" src="https://raw.githubusercontent.com/Qingshan2077/LhResearchAssistant/main/assets/logo-light.png">
</picture>

# LhResearchAssistant 🎓

> 全流程科研桌面助手 — 从文献检索到论文发表，AI 辅助，Human-in-the-loop

**English** | [中文](#中文介绍)

LhResearchAssistant is a desktop application for CS researchers that covers the entire research workflow: paper retrieval → reading & analysis → idea generation → LaTeX writing → journal selection & review. Powered by LLM (DeepSeek / OpenAI / Claude / Ollama), local knowledge base, Usage Dashboard, full i18n (EN/ZH), and vector search.

---

## 中文介绍

面向**计算机领域研究者**的桌面科研助手。不是全自动科研系统（拒绝 AI Scientist 路线），而是 **Human-in-the-loop** 的智能辅助工具 —— AI 处理 grunt work，研究者做核心决策。

### 核心功能

```
┌─────────────────────────────────────────────────────────────────┐
│                    LhResearchAssistant                           │
├──────────┬──────────┬──────────┬──────────┬─────────────────────┤
│ 文献检索  │ 论文解读  │ Idea生成 │ 论文写作  │ 选刊 + 审稿        │
│          │          │          │          │                     │
│ arXiv    │ PDF内嵌  │ Gap分析  │ LaTeX模板 │ CCF选刊推荐         │
│ S2       │ AI结构化 │ 跨领域迁移│ 引导式写作│ 格式检查            │
│ DBLP     │ 思维图   │ 趋势预测  │ BibTeX管理│ 模拟审稿            │
│ 综述生成  │ 知识图谱  │ 可行性评估│ 中英文润色│ Cover Letter       │
│          │ Chroma   │          │          │ Rebuttal           │
└──────────┴──────────┴──────────┴──────────┴─────────────────────┘
```

#### ① 文献检索与综述

- **多源并行检索**：arXiv + Semantic Scholar + DBLP + CrossRef，去重合并
- **关键词扩展**：LLM 自动生成同义词和相关概念
- **结构化综述**：选中论文 → SSE 流式生成带引用的综述（方法对比 / 时间线 / 问题导向）

#### ② 论文解读 + 思维图 + 知识库

- **PDF 内嵌阅读器**：iframe 渲染，支持下载
- **AI 结构化提取**：问题 → 方法 → 实验 → 结论，JSON 结构存储
- **交互式思维图**：React Flow 拖拽画布，双击编辑，右键添加/删除，保存持久化
- **知识图谱**：Cytoscape.js 力导向图，论文节点 + 概念节点，关系边着色
- **Chroma 向量知识库**：论文段落自动索引，语义搜索 + LLM 回答

#### ③ Idea 生成与可行性判断

- **三个模式**：Gap 分析 / 跨领域迁移 / 趋势预测
- **SSE 流式输出**：边生成边展示
- **可行性评估**：新颖性 / 可实现性 / 成本 / 风险 四维度评分
- **引用锚定**：每个 idea 关联到具体论文

#### ④ LaTeX 写作

- **模板系统**：NeurIPS 2024 / ACL / IEEE Transactions / 中文 CTeX
- **引导式写作 Agent**：基于大纲 + 知识库论文，LLM 逐节生成，附带 [paper_id] 引用锚点
- **BibTeX 管理**：从论文库生成 `.bib` 条目、导出、DOI 验证（CrossRef）
- **中英文学术润色**：学术 / 简洁 / 流畅 三种风格，原文 vs 润色对比

#### ⑤ 选刊与审稿

- **CCF 选刊推荐**：40+ CS 会议/期刊，LLM 匹配 + 规则兜底
- **格式检查**：页数、匿名、摘要字数、必要章节、引用样式 — 按模板规则检查
- **模拟审稿**：4 角色审稿人（方法/实验/理论/写作）+ meta-review + 决策
- **Cover Letter / Rebuttal** 生成
- **Sprint Contract**：Paper-blind Pre-commitment（投稿前自检清单）
- **Writing Quality Check**：AI 写作质量评估（清晰度/简洁性/逻辑性）
- **7-mode AI Failure Checklist**：7 大失败模式检测
- **S2 Citation Verification**：引用真实性验证

#### ⑥ 设置与管理

- **LLM Provider 管理**：DeepSeek / OpenAI / Claude / Ollama / Custom，活跃切换 + 内联编辑
- **用量统计看板**：调用次数 / Token 用量 / 按 Provider & 功能聚合
- **数据管理**：库统计 + 清空向量缓存
- **系统信息**：版本/路径/占用

#### 🌐 中英文切换

- **完整 i18n**：所有页面支持中/英文一键切换，存储在 localStorage

### 技术栈

| 层 | 技术 |
|----|------|
| 桌面壳 | **[Tauri v2](https://v2.tauri.app/)** — 10MB 包体，原生性能 |
| 前端 | **React 18 + TypeScript + Vite 6 + Tailwind CSS 4** |
| 可视化 | **React Flow** (思维图) + **Cytoscape.js** (知识图谱) + **Recharts** |
| 状态管理 | **Zustand** |
| 后端 | **Python FastAPI + uvicorn** |
| Agent 框架 | **LangGraph** |
| LLM | **DeepSeek** (主力) / OpenAI / Claude / Ollama，用户可配置 |
| 向量数据库 | **ChromaDB** |
| 数据库 | **SQLite + SQLAlchemy 2.0** |
| PDF 解析 | **PyMuPDF** (快速) + **marker-pdf** (高精度) |
| 数据源 | arXiv / Semantic Scholar / DBLP / CrossRef |
| 包管理 | **uv** (后端) / npm (前端) |

### 架构概览

```
┌────────────────────────────────────────────────────────────┐
│                    Tauri 桌面窗口                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              React 前端 (Vite + Tailwind)              │  │
│  │   SearchPage │ ReaderPage │ KnowledgePage │          │  │
│  │   IdeaPage │ WritePage │ ReviewPage │ SettingsPage  │  │
│  └──────────────────────┬───────────────────────────────┘  │
│                         │ HTTP / WebSocket                  │
│  ┌──────────────────────┴───────────────────────────────┐  │
│  │         Rust Bridge (< 50 lines)                     │  │
│  │   启动/停止 Python 后端 + 文件对话框 + 系统通知        │  │
│  └──────────────────────┬───────────────────────────────┘  │
└─────────────────────────┼──────────────────────────────────┘
                          │ localhost:8787
┌─────────────────────────┴──────────────────────────────────┐
│              Python FastAPI 后端                             │
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐ │
│  │  检索     │ │  解读    │ │  写作     │ │  审稿           │ │
│  │  Agent   │ │  Agent   │ │  Agent   │ │  Agent          │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────┘ │
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐ │
│  │ SQLite   │ │ Chroma   │ │NetworkX  │ │  File Store     │ │
│  │ (用户数据)│ │(语义向量) │ │(论文图谱) │ │(PDF/tex/缓存)   │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### 快速开始

#### 环境要求

- Python >= 3.11
- Node.js >= 20
- uv (Python 包管理器): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Rust (编译 Tauri 时需要): `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`

#### 后端

```bash
cd backend
uv sync
cp .env.example .env            # 编辑填入 DeepSeek API Key
uv run uvicorn app.main:app --port 8787 --reload
```

验证：`curl http://localhost:8787/api/v1/health`

#### 前端（浏览器开发模式）

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 `http://localhost:1420`

#### 桌面应用

```bash
cd frontend
cargo install tauri-cli --version "^2"
cargo tauri dev      # 开发模式
cargo tauri build    # 打包安装包
```

### API 文档

启动后端后访问 `http://localhost:8787/docs` (Swagger UI)

### 项目结构

```
LhResearchAssistant/
├── backend/                  # Python FastAPI 后端
│   ├── app/
│   │   ├── main.py           # FastAPI 入口
│   │   ├── config.py         # 配置
│   │   ├── database/         # SQLite + Chroma + NetworkX
│   │   ├── agents/           # Agent (检索/解读/Idea/写作/审稿)
│   │   ├── services/         # 服务 (数据源/PDF/BibTeX/选刊/格式)
│   │   ├── llm/              # LLM Provider 抽象层
│   │   ├── routers/          # API 路由 (9 个模块)
│   │   └── models/           # Pydantic schemas
│   ├── templates/            # LaTeX 模板
│   └── data/                 # 运行时数据 (gitignored)
├── frontend/                 # Tauri + React 前端
│   ├── src/
│   │   ├── routes/           # 7 个页面组件
│   │   ├── components/       # 通用组件 (Sidebar/ChatPanel)
│   │   ├── stores/           # Zustand 状态管理
│   │   └── lib/              # API 客户端 + 类型定义
│   └── src-tauri/            # Tauri Rust (≈65 行)
├── docs/                     # 开发文档 (gitignored)
└── SETUP.md                  # 详细安装指南
```

### TODO / Roadmap

- [x] Phase 1: 文献检索 + PDF 阅读 + 基础知识库
- [x] Phase 2: 知识图谱增强 + ChatPanel + Idea 生成 + Chroma 向量库
- [x] Phase 3: 写作 Agent + BibTeX + 润色 + 选刊 + 格式检查 + 模拟审稿
- [x] Step 1-3 (ARS 集成): Sprint Contract / Writing Quality / Rebuttal / S2验证 / 苏格拉底导师 / Generator-Evaluator / 动态人设
- [x] **Settings 页面**: Provider 管理 + 用量看板 + 数据管理 + 系统信息
- [x] **中英文切换**: 全页面 i18n
- [ ] **团队协作**：多用户 + WebSocket 实时同步
- [ ] **知识图谱概念级合并**：同义概念融合、多跳推理
- [ ] **图表自动提取**：PDF 图表识别与 caption 提取
- [ ] **插件系统**：自定义数据源 / Agent / 模板

---

<p align="center">
  <b>LhResearchAssistant</b> — Built with ❤️ for the CS research community<br>
  If you find this project helpful, please ⭐ star it on GitHub!
</p>
