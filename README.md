<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Qingshan2077/LhResearchAssistant/main/assets/logo-dark.png">
  <img alt="LhResearchAssistant" src="https://raw.githubusercontent.com/Qingshan2077/LhResearchAssistant/main/assets/logo-light.png">
</picture>

# LhResearchAssistant 🎓

> 全流程科研桌面助手 — 从文献检索到论文发表，AI 辅助，Human-in-the-loop

**English** | [中文](#中文介绍)

LhResearchAssistant is an open-source desktop application purpose-built for CS researchers who want AI assistance without losing control of their workflow. Unlike cloud-based tools that treat researchers as passengers, LhResearchAssistant runs entirely on your own machine, gives you full visibility into every AI decision, and keeps your data where it belongs.

---

## Why LhResearchAssistant?

Most AI research tools today follow one of two paths: either they're cloud-only SaaS products that upload your data to third-party servers with opaque pricing, or they're research playgrounds that lack the depth to support a real publication workflow. LhResearchAssistant was built to bridge this gap.

The application covers the complete lifecycle of a CS research project — from the moment you type a search query to the day you submit your camera-ready paper. It searches across arXiv, Semantic Scholar, and DBLP in parallel, deduplicates results, and can automatically classify them into topic groups so you don't scroll through flat lists. It reads and structures PDFs, builds a local knowledge graph of papers and concepts, and indexes everything in a vector database for semantic retrieval.

When it's time to develop research ideas, two paths are available: a guided Socratic dialogue that walks you through 5 layers of questioning (from problem framing to significance), or a direct generator that analyzes gaps, cross-domain transfers, and publication trends in your selected papers. Both produce structured research plans with feasibility evaluations.

Writing support includes LaTeX templates (NeurIPS, ACL, IEEE, CTeX), a guided section-by-section writing agent, BibTeX management with DOI cross-validation, and bilingual polishing in Chinese and English. Before submission, the review module runs simulated peer reviews with 4 dynamic reviewer personas, a meta-review, format checks, and a preprint commitment checklist.

All LLM interactions use locally configured providers — DeepSeek, OpenAI, Claude, or Ollama — with real-time token tracking and cost estimation. For DeepSeek users especially, the system captures `prompt_cache_hit_tokens` from the API response and displays cache hit rates alongside estimated costs, so you know exactly what each search or generation costs down to the cent.

### Key Design Decisions

- **Local-first**: Everything runs on your machine. No data upload, no subscription fees beyond your LLM API costs.
- **Human-in-the-loop**: AI suggests; you decide. No auto-generated papers, no black-box decisions.
- **Token transparency**: Every API call is tracked with real token counts (not estimates), cache hit/miss breakdown, and cost.
- **Multi-provider**: Configure DeepSeek, OpenAI, Claude, and Ollama side by side, switch with one click.
- **i18n**: Full Chinese and English interfaces, switchable at any time.

---

## 中文介绍

### 这个工具解决什么问题？

做计算机科研的人都知道，文献调研、论文写作、投稿审稿这个流程里，有大量重复性、机械性的工作：

- 在 arXiv、S2、DBLP 之间来回切换搜论文，手动去重
- 读完几十篇论文后凭记忆整理 Related Work
- 面对空白的 LaTeX 文件不知道从哪里下笔
- 投出去之前心里没底，不知道审稿人会怎么骂

现有方案要么是全自动的 AI Scientist（不靠谱，研究者无法干预），要么是 SaaS 工具（数据要上传，费用不透明）。**LhResearchAssistant 走的是第三条路——本地运行、Human-in-the-loop、每一分钱都看得见。**

### 核心功能

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         LhResearchAssistant                                │
├──────────┬──────────┬─────────────┬───────────┬──────────────────────────┤
│ 文献检索  │ 论文解读  │ Idea 生成   │ 论文写作   │ 选刊 + 审稿             │
│          │          │             │           │                          │
│ arXiv    │ PDF内嵌  │ Gap 分析    │ LaTeX模板  │ CCF选刊推荐              │
│ S2       │ AI结构化 │ 跨领域迁移   │ 引导式写作 │ 格式检查                 │
│ DBLP     │ 思维图   │ 趋势预测    │ BibTeX管理 │ 模拟审稿 (4角色)         │
│ 综述生成  │ 知识图谱  │ 可行性评估  │ 中英文润色 │ Cover Letter             │
│ 自动分类  │ Chroma   │ 引导式Idea  │            │ Rebuttal                │
│ 结果筛选  │          │ Socratic导师│            │ Sprint Contract         │
│          │          │ 历史持久化  │            │ Writing Quality Check   │
│          │          │ 管线打通    │            │ AI Failure Checklist    │
└──────────┴──────────┴─────────────┴───────────┴──────────────────────────┘
```

#### ① 文献检索与综述

搜索结果不再是一个平铺列表。系统自动调用 LLM 将论文按主题分组（比如搜 AGV 调度时自动分出"路径规划"、"多机器人调度"、"强化学习"等），你只需点击标签就能只看某一类。

- **三源并行检索**：arXiv + Semantic Scholar + DBLP 同时搜索，自动去重合并
- **LLM 自动分类**：搜索完成后实时将结果分组，支持点击筛选
- **元数据过滤**：按来源（arXiv/S2/DBLP）、年份范围过滤，支持在结果中搜索关键词
- **结构化综述**：选中论文后流式生成综述，按方法对比 / 时间线 / 问题导向组织
- **引用验证**：S2 + CrossRef 交叉验证引用真实性

#### ② 论文解读 + 思维图 + 知识库

不只是读 PDF。系统自动提取论文的结构化信息（问题→方法→实验→结论），构建知识图谱，建立向量索引，让你可以对整个论文库提问。

- **PDF 内嵌阅读器**：iframe 渲染，支持下载
- **AI 结构化提取**：问题、方法、实验、结论，JSON 结构存储
- **交互式思维图**：React Flow 拖拽画布，双击编辑，保存持久化
- **知识图谱**：Cytoscape.js 力导向图，论文节点 + 概念节点，关系边着色
- **Chroma 向量知识库**：论文段落自动索引，语义搜索 + LLM 回答
- **ChatPanel**：对选中论文提问，LLM 结合向量库 + 全文回答

#### ③ Idea 生成与可行性判断

两个入口：一是**直接生成**，选论文、选模式（Gap 分析 / 跨领域迁移 / 趋势预测），直接出 3-5 个 Idea；二是**引导式 Socratic 导师**，AI 通过 5 层苏格拉底式提问，帮你在对话中把模糊想法打磨成清晰的研究问题。

两个入口之间的数据是打通的——你在 Socratic 里讨论产出的研究问题、洞见、方法论，可以直接注入到 Idea 生成的上下文中，不需要重复输入。

- **三个直接生成模式**：Gap 分析（找现有工作的漏洞）、跨领域迁移（A 领域方法搬到 B 领域）、趋势预测（按发表年份推断新兴方向）
- **Socratic 导师**：5 层对话（问题界定→方法论→证据设计→批判审视→意义贡献），AI 只提问不给答案
- **对话历史持久化**：自动保存所有 Socratic 会话，支持回看和管理
- **管线打通**：把 Socratic 产出注入到 Idea 生成的 custom_prompt 中
- **SSE 流式输出**：边生成边展示，不等待
- **可行性评估**：新颖性 / 可实现性 / 成本 / 风险 四维度评分 + LLM 推理

#### ④ LaTeX 写作

- **模板系统**：NeurIPS 2024 / ACL / IEEE Transactions / 中文 CTeX
- **引导式写作 Agent**：基于大纲 + 知识库论文，LLM 逐节生成，附带论文引用锚点
- **BibTeX 管理**：从论文库生成 `.bib` 条目、导出、DOI 验证（CrossRef）
- **中英文学术润色**：学术 / 简洁 / 流畅 三种风格，原文 vs 润色对比

#### ⑤ 选刊与审稿

投稿前的一套自检流程。先推荐合适的 CCF 会议/期刊，再检查格式是否符合模板要求，最后生成 4 个角色的模拟审稿意见。

- **CCF 选刊推荐**：40+ CS 会议/期刊，LLM 匹配 + 规则兜底
- **格式检查**：页数、匿名、摘要字数、必要章节、引用样式
- **模拟审稿**：4 角色审稿人（方法/实验/理论/写作），带动态人设 + meta-review + 决策
- **Cover Letter / Rebuttal** 生成
- **Sprint Contract**：投稿前自检清单（论文盲审预承诺）
- **Writing Quality Check**：AI 写作质量评估（清晰度/简洁性/逻辑性）
- **7-mode AI Failure Checklist**：7 大失败模式检测（实验设计、结论夸大等）
- **S2 Citation Verification**：引用真实性验证

#### ⑥ LLM 管理与用量追踪

支持 DeepSeek、OpenAI、Claude、Ollama 同时配置，一键切换激活。每个 Provider 可独立设置模型、API Key、Temperature、Max Tokens 和优先级。

用量看板实时显示每次调用的真实 token 消耗（从 API 响应中捕获，不是本地估算）和缓存命中率。对于 DeepSeek 模型，系统还会根据官方定价自动计算费用。

- **多 Provider 管理**：DeepSeek / OpenAI / Claude / Ollama / Custom，激活切换 + 内联编辑
- **缓存命中率监控**：自动捕获 DeepSeek 的 `prompt_cache_hit_tokens` 和 `prompt_cache_miss_tokens`
- **费用估算**：基于 DeepSeek 官方定价
  - V4-Flash：缓存命中 ¥0.02/M、缓存未命中 ¥1.00/M、输出 ¥2.00/M
  - V4-Pro：缓存命中 ¥0.025/M、缓存未命中 ¥3.00/M、输出 ¥6.00/M
- **用量统计看板**：调用次数 / 真实 Token / 缓存命中/未命中 / 按 Provider & 功能聚合 / 近 90 天趋势
- **数据管理**：库统计 + 清空向量缓存
- **系统信息**：版本/路径/磁盘占用

#### 🌐 中英文切换

所有页面支持中/英文一键切换，设置存储在 localStorage，刷新后保持。

---

### 技术栈

| 层 | 技术 |
|----|------|
| 桌面壳 | **[Tauri v2](https://v2.tauri.app/)** — 10MB 包体，原生性能 |
| 前端 | **React 18 + TypeScript + Vite 6 + Tailwind CSS 4** |
| 可视化 | **React Flow** (思维图) + **Cytoscape.js** (知识图谱) + **Recharts** |
| 状态管理 | **Zustand** |
| LLM | **DeepSeek** (主力) / OpenAI / Claude / Ollama，用户可配置 |
| 代理模式 | **ContextVar** 并发安全，自动捕获 API 真实 Token 和缓存数据 |
| 向量数据库 | **ChromaDB** |
| 数据库 | **SQLite + SQLAlchemy 2.0 + Alembic** |
| PDF 解析 | **PyMuPDF** (快速) + **marker-pdf** (高精度) |
| 数据源 | arXiv / Semantic Scholar / DBLP |
| 包管理 | **uv** (后端) / npm (前端) |

### 架构概览

```
┌────────────────────────────────────────────────────────────┐
│                    Tauri 桌面窗口                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              React 前端 (Vite + Tailwind)              │  │
│  │   SearchPage │ ReaderPage │ KnowledgePage │          │  │
│  │   IdeaPage │ SocraticPage │ WritePage │             │  │
│  │   ReviewPage │ SettingsPage │ LLMSettingsPage        │  │
│  └──────────────────────┬───────────────────────────────┘  │
│                         │ HTTP / WebSocket / SSE            │
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
│  │  + 分类   │ │  + 图谱   │ │  +BibTeX │ │  + 7 子模块     │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────┘ │
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐ │
│  │ SQLite   │ │ Chroma   │ │NetworkX  │ │  File Store     │ │
│  │ (用户数据)│ │(语义向量) │ │(论文图谱) │ │(PDF/tex/缓存)   │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  LLM Provider Layer (DeepSeek / OpenAI / Claude / ...)  │ │
│  │  Usage Tracking → 缓存命中监控 → 费用估算               │ │
│  └────────────────────────────────────────────────────────┘ │
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
uv run alembic upgrade head      # 创建数据库表
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
│   │   ├── agents/           # Agent (检索/解读/Idea/写作/审稿/Socratic)
│   │   ├── services/         # 服务 (数据源/PDF/BibTeX/选刊/格式/费用估算)
│   │   ├── llm/              # LLM Provider 抽象层
│   │   ├── routers/          # API 路由 (10 个模块)
│   │   └── models/           # Pydantic schemas
│   ├── templates/            # LaTeX 模板
│   └── data/                 # 运行时数据 (gitignored)
├── frontend/                 # Tauri + React 前端
│   ├── src/
│   │   ├── routes/           # 8 个页面组件
│   │   ├── components/       # 通用组件 (Sidebar/ChatPanel/UsageDashboard)
│   │   ├── stores/           # Zustand 状态管理
│   │   └── lib/              # API 客户端 + 类型定义
│   └── src-tauri/            # Tauri Rust (≈65 行)
└── SETUP.md                  # 详细安装指南
```

### TODO / Roadmap

- [x] Phase 1: 文献检索 + PDF 阅读 + 基础知识库
- [x] Phase 2: 知识图谱增强 + ChatPanel + Idea 生成 + Chroma 向量库
- [x] Phase 3: 写作 Agent + BibTeX + 润色 + 选刊 + 格式检查 + 模拟审稿
- [x] ARS 集成: Sprint Contract / Writing Quality / Rebuttal / S2验证 / Socratic 导师
- [x] **LLM 管理 + 用量看板**: Provider 管理 + Token 追踪 + 缓存命中率 + 费用估算
- [x] **检索结果分类**: LLM 自动分组 + 元数据过滤 + 搜索状态保持
- [x] **Socratic 持久化**: 对话历史保存/回看 + Socratic→Idea 管线打通
- [x] **Token 精确追踪**: ContextVar 并发安全的 API usage 捕获
- [ ] **团队协作**：多用户 + WebSocket 实时同步
- [ ] **知识图谱概念级合并**：同义概念融合、多跳推理
- [ ] **图表自动提取**：PDF 图表识别与 caption 提取
- [ ] **插件系统**：自定义数据源 / Agent / 模板

---

<p align="center">
  <b>LhResearchAssistant</b> — Built with ❤️ for the CS research community<br>
  If you find this project helpful, please ⭐ star it on GitHub!
</p>
