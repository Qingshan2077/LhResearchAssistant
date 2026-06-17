import { useState, useCallback, useRef, useEffect } from "react";
import { usePaperStore } from "../stores/paperStore";
import { api, type Paper } from "../lib/api";

export default function SearchPage() {
  const { papers, loading, search, searchQuery, totalCount } = usePaperStore();
  const [query, setQuery] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [generatingReview, setGeneratingReview] = useState(false);
  const [reviewContent, setReviewContent] = useState("");
  const reviewRef = useRef<HTMLDivElement>(null);

  const handleSearch = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (query.trim()) search(query.trim());
    },
    [query, search]
  );

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleGenerateReview = async () => {
    if (selectedIds.size === 0) return;
    setGeneratingReview(true);
    setReviewContent("");

    const selectedPapers = papers.filter((p) => selectedIds.has(p.id));
    const projectId = "default";

    // 先导入到本地
    try {
      await api.post("papers/batch", {
        json: selectedPapers.map((p) => ({
          project_id: projectId,
          title: p.title,
          authors: p.authors,
          abstract: p.abstract,
          year: p.year,
          venue: p.venue,
          doi: p.doi,
          arxiv_id: p.arxiv_id,
          source: p.source,
          citation_count: p.citation_count,
          keywords: p.keywords,
          url: p.url,
          pdf_url: p.pdf_url,
        })),
      });
    } catch {
      // 可能已导入，继续
    }

    // 从后端获取导入后的 paper IDs
    const resp = await api
      .get("papers", { searchParams: { project_id: projectId, page_size: 500 } })
      .json<{ items: Paper[] }>();

    const importedIds = resp.items
      .filter((p) => selectedPapers.some((sp) => sp.title === p.title))
      .map((p) => p.id);

    // SSE 流式接收综述
    const token = localStorage.getItem("auth_token") || "";
    const eventSource = new EventSource(
      `/api/v1/search/generate-review`,
      {
        withCredentials: true,
      }
    );

    // 使用 POST + SSE 的方式
    try {
      const response = await fetch("/api/v1/search/generate-review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: projectId,
          paper_ids: importedIds,
          focus: "method_comparison",
          language: "en",
        }),
      });

      const reader = response.body?.getReader();
      if (!reader) return;

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === "chunk") {
                setReviewContent((prev) => prev + data.content);
              } else if (data.type === "done") {
                setGeneratingReview(false);
              } else if (data.type === "error") {
                setReviewContent((prev) => prev + `\n\n[Error: ${data.message}]`);
                setGeneratingReview(false);
              }
            } catch {
              // 忽略解析失败的行
            }
          }
        }
      }
    } catch (e) {
      setReviewContent(`Failed to generate review: ${e}`);
    }
    setGeneratingReview(false);
  };

  const handleImport = async () => {
    if (selectedIds.size === 0) return;
    const selectedPapers = papers.filter((p) => selectedIds.has(p.id));
    try {
      await api.post("papers/batch", {
        json: selectedPapers.map((p) => ({
          project_id: "default",
          title: p.title,
          authors: p.authors,
          abstract: p.abstract,
          year: p.year,
          venue: p.venue,
          doi: p.doi,
          arxiv_id: p.arxiv_id,
          source: p.source,
          citation_count: p.citation_count,
          keywords: p.keywords,
          url: p.url,
          pdf_url: p.pdf_url,
        })),
      });
      setSelectedIds(new Set());
    } catch (e) {
      console.error("Import failed", e);
    }
  };

  return (
    <div className="flex flex-col gap-6 h-full">
      {/* 标题 */}
      <div>
        <h1 className="text-2xl font-bold">文献检索</h1>
        <p className="text-muted-foreground text-sm mt-1">
          搜索 arXiv、Semantic Scholar、DBLP 等数据库
        </p>
      </div>

      {/* 搜索栏 */}
      <form onSubmit={handleSearch} className="flex gap-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="输入研究方向关键词…"
          className="flex-1 px-4 py-2.5 rounded-lg border border-input bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="px-6 py-2.5 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors font-medium"
        >
          {loading ? "搜索中…" : "搜索"}
        </button>
      </form>

      {/* 操作栏 */}
      {papers.length > 0 && (
        <div className="flex items-center gap-3 text-sm">
          <span className="text-muted-foreground">
            共 {totalCount} 篇论文，已选 {selectedIds.size} 篇
          </span>
          {selectedIds.size > 0 && (
            <>
              <button
                onClick={handleImport}
                className="px-3 py-1.5 rounded-md bg-secondary text-secondary-foreground hover:bg-secondary/80 transition-colors"
              >
                导入选中
              </button>
              <button
                onClick={handleGenerateReview}
                disabled={generatingReview}
                className="px-3 py-1.5 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
              >
                {generatingReview ? "生成中…" : "生成综述"}
              </button>
            </>
          )}
        </div>
      )}

      <div className="flex gap-6 flex-1 min-h-0">
        {/* 论文列表 */}
        <div className="flex-1 overflow-auto">
          {papers.length === 0 && !loading && (
            <div className="flex items-center justify-center h-48 text-muted-foreground">
              输入关键词开始搜索
            </div>
          )}

          {loading && (
            <div className="flex items-center justify-center h-48 text-muted-foreground">
              正在并行搜索 arXiv + Semantic Scholar + DBLP…
            </div>
          )}

          <div className="space-y-2">
            {papers.map((paper) => (
              <div
                key={paper.id}
                onClick={() => toggleSelect(paper.id)}
                className={`p-4 rounded-lg border cursor-pointer transition-colors ${
                  selectedIds.has(paper.id)
                    ? "border-primary bg-primary/5"
                    : "border-border hover:bg-muted/50"
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-sm leading-snug line-clamp-2">
                      {paper.title}
                    </h3>
                    <p className="text-xs text-muted-foreground mt-1 line-clamp-1">
                      {paper.authors?.slice(0, 5).join(", ")}
                      {paper.authors && paper.authors.length > 5 ? " et al." : ""}
                    </p>
                    <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                      <span>{paper.year || "N/A"}</span>
                      <span>{paper.venue || "N/A"}</span>
                      {paper.citation_count > 0 && (
                        <span>引用: {paper.citation_count}</span>
                      )}
                      <span className="px-1.5 py-0.5 rounded bg-secondary/50 text-xs">
                        {paper.source}
                      </span>
                      {!paper.is_new && (
                        <span className="text-primary text-xs">已导入</span>
                      )}
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={selectedIds.has(paper.id)}
                    onChange={() => toggleSelect(paper.id)}
                    className="mt-1 shrink-0"
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 综述面板 */}
        {(reviewContent || generatingReview) && (
          <div className="w-1/2 border border-border rounded-lg overflow-hidden flex flex-col">
            <div className="px-4 py-2.5 border-b border-border bg-muted/30 font-medium text-sm">
              文献综述
              {generatingReview && (
                <span className="ml-2 text-primary text-xs animate-pulse">生成中…</span>
              )}
            </div>
            <div
              ref={reviewRef}
              className="flex-1 overflow-auto p-4 prose prose-sm dark:prose-invert max-w-none"
            >
              {reviewContent ? (
                <div dangerouslySetInnerHTML={{ __html: renderMarkdown(reviewContent) }} />
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                  等待生成…
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/** 简单的 Markdown 渲染（基础版，Phase 2 可换 marked/markdown-it） */
function renderMarkdown(text: string): string {
  return text
    // 标题
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/^# (.+)$/gm, "<h1>$1</h1>")
    // 粗体
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    // 列表
    .replace(/^- (.+)$/gm, "<li>$1</li>")
    .replace(/(<li>.*<\/li>\n?)+/g, "<ul>$&</ul>")
    // 引用
    .replace(/^> (.+)$/gm, "<blockquote>$1</blockquote>")
    // 段落
    .replace(/\n\n/g, "</p><p>")
    // 代码块
    .replace(/```(\w*)\n([\s\S]*?)```/g, "<pre><code>$2</code></pre>")
    // 行内代码
    .replace(/`(.+?)`/g, "<code>$1</code>")
    // 换行
    .replace(/\n/g, "<br/>")
    .replace(/<br\/><\/p>/g, "</p>")
    .replace(/<p>/g, "<p>")
    .replace(/^(?!<[hplu])/gm, "");
}
