import { useEffect, useRef, useState } from "react";
import { useKnowledgeStore } from "../stores/knowledgeStore";
import { useNavigate } from "react-router-dom";
import { Network, Search as SearchIcon, Loader2, BookOpen } from "lucide-react";
import cytoscape from "cytoscape";

export default function KnowledgeBasePage() {
  const navigate = useNavigate();
  const { graphData, fetchGraph, query, queryResult, querying } = useKnowledgeStore();
  const [searchInput, setSearchInput] = useState("");
  const graphRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    fetchGraph("default");
  }, [fetchGraph]);

  useEffect(() => {
    if (!graphRef.current || !graphData || graphData.nodes.length === 0) return;

    const cy = cytoscape({
      container: graphRef.current,
      elements: [
        ...graphData.nodes.map((node) => ({
          data: {
            id: node.id,
            label: node.label,
            type: node.type,
            group: node.group,
            ...node.data,
          },
          classes: node.type,
        })),
        ...graphData.edges.map((edge, index) => ({
          data: {
            id: `${edge.source}->${edge.target}:${index}`,
            source: edge.source,
            target: edge.target,
            type: edge.type,
            label: edge.label || "",
          },
        })),
      ],
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "font-size": 10,
            color: "hsl(210 40% 98%)",
            "text-outline-color": "hsl(222.2 84% 4.9%)",
            "text-outline-width": 2,
            "text-wrap": "wrap",
            "text-max-width": 140,
          },
        },
        {
          selector: ".paper",
          style: {
            "background-color": "#3b82f6",
            width: 34,
            height: 34,
            "border-color": "#93c5fd",
            "border-width": 2,
          },
        },
        {
          selector: ".concept",
          style: {
            "background-color": "#10b981",
            width: 22,
            height: 22,
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.2,
            "line-color": "#475569",
            "target-arrow-color": "#475569",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            opacity: 0.75,
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-color": "#22d3ee",
            "border-width": 4,
          },
        },
      ],
      layout: {
        name: "cose",
        padding: 36,
        animate: true,
        nodeRepulsion: 6000,
        idealEdgeLength: 120,
      },
    });

    cy.on("tap", ".paper", (event) => {
      const nodeId = event.target.id();
      if (nodeId.startsWith("paper:")) {
        navigate(`/papers/${nodeId.replace("paper:", "")}`);
      }
    });

    return () => {
      cy.destroy();
    };
  }, [graphData, navigate]);

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
              <div ref={graphRef} className="h-full w-full min-h-[360px]" />
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
