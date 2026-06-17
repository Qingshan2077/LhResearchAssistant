import { useEffect, useState } from "react";
import { useKnowledgeStore } from "../stores/knowledgeStore";
import { useNavigate } from "react-router-dom";
import { Network, Search as SearchIcon, Loader2, BookOpen } from "lucide-react";

export default function KnowledgeBasePage() {
  const navigate = useNavigate();
  const { graphData, fetchGraph, query, queryResult, querying } = useKnowledgeStore();
  const [searchInput, setSearchInput] = useState("");

  useEffect(() => {
    fetchGraph("default");
  }, [fetchGraph]);

  const handleQuery = () => {
    if (searchInput.trim()) {
      query("default", searchInput.trim());
    }
  };

  return (
    <div className="flex flex-col gap-6 h-full">
      {/* 标题 */}
      <div>
        <h1 className="text-2xl font-bold">知识库</h1>
        <p className="text-muted-foreground text-sm mt-1">
          论文知识图谱 + 语义搜索
        </p>
      </div>

      {/* 搜索栏 */}
      <div className="flex gap-3">
        <input
          type="text"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleQuery()}
          placeholder="搜索知识库内容…"
          className="flex-1 px-4 py-2.5 rounded-lg border border-input bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <button
          onClick={handleQuery}
          disabled={querying || !searchInput.trim()}
          className="px-6 py-2.5 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors font-medium"
        >
          {querying ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <SearchIcon size={16} />
          )}
        </button>
      </div>

      <div className="flex gap-6 flex-1 min-h-0">
        {/* 知识图谱 */}
        <div className="flex-1 border border-border rounded-lg overflow-hidden bg-card flex flex-col">
          <div className="px-4 py-2.5 border-b border-border bg-muted/30 flex items-center justify-between">
            <span className="text-sm font-medium flex items-center gap-2">
              <Network size={16} />
              知识图谱
            </span>
            <span className="text-xs text-muted-foreground">
              {graphData?.nodes.length || 0} 节点 / {graphData?.edges.length || 0} 关系
            </span>
          </div>
          <div className="flex-1 flex items-center justify-center p-4">
            {graphData && graphData.nodes.length > 0 ? (
              <div className="w-full h-full flex flex-wrap gap-2 overflow-auto p-2">
                {/* 简单的标签云式展示（Phase 2 替换为 Cytoscape.js） */}
                {graphData.nodes
                  .filter((n) => n.type === "paper")
                  .slice(0, 50)
                  .map((node) => (
                    <button
                      key={node.id}
                      onClick={() => {
                        const pid = node.id.replace("paper:", "");
                        navigate(`/papers/${pid}`);
                      }}
                      className="px-3 py-1.5 rounded-full text-xs border border-border hover:border-primary hover:bg-primary/5 transition-colors"
                    >
                      {node.label.length > 30
                        ? node.label.slice(0, 30) + "…"
                        : node.label}
                    </button>
                  ))}
                {/* 概念节点 */}
                {graphData.nodes
                  .filter((n) => n.type === "concept")
                  .slice(0, 20)
                  .map((node) => (
                    <span
                      key={node.id}
                      className="px-2 py-1 rounded-full text-xs bg-primary/10 text-primary"
                    >
                      #{node.label}
                    </span>
                  ))}
              </div>
            ) : (
              <div className="text-center text-muted-foreground">
                <Network size={48} className="mx-auto mb-4 opacity-30" />
                <p className="text-sm">知识库为空</p>
                <p className="text-xs mt-1">导入论文后自动构建知识图谱</p>
              </div>
            )}
          </div>
        </div>

        {/* 搜索结果 */}
        <div className="w-[400px] border border-border rounded-lg overflow-hidden flex flex-col shrink-0">
          <div className="px-4 py-2.5 border-b border-border bg-muted/30 text-sm font-medium">
            搜索结果
          </div>
          <div className="flex-1 overflow-auto p-4">
            {queryResult ? (
              <div className="text-sm leading-relaxed whitespace-pre-wrap">
                {queryResult}
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                <div className="text-center">
                  <BookOpen size={32} className="mx-auto mb-2 opacity-30" />
                  搜索知识库内容
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
