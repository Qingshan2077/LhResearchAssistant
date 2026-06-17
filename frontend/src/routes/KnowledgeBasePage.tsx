import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { BookOpen, Loader2, Network, Search as SearchIcon } from "lucide-react";
import cytoscape from "cytoscape";
import { ChatPanel } from "../components/ChatPanel";
import { t } from "../i18n";
import { useKnowledgeStore } from "../stores/knowledgeStore";
import { useSettingsStore } from "../stores/settingsStore";

export default function KnowledgeBasePage() {
  const navigate = useNavigate();
  const language = useSettingsStore((s) => s.language);
  const { graphData, fetchGraph, query, queryResult, querying } = useKnowledgeStore();
  const [searchInput, setSearchInput] = useState("");
  const graphRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    fetchGraph("default");
  }, [fetchGraph]);

  useEffect(() => {
    if (!graphRef.current || !graphData || graphData.nodes.length === 0) return;

    const isDark = document.documentElement.classList.contains("dark");
    const nodeTextColor = isDark ? "#e5e7eb" : "#1f2937";
    const nodeTextOutline = isDark ? "#020617" : "#ffffff";
    const edgeLabelBackground = isDark ? "#020617" : "#ffffff";

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
            "font-weight": 400,
            color: nodeTextColor,
            "text-outline-color": nodeTextOutline,
            "text-outline-width": 1.2,
            "text-wrap": "wrap",
            "text-max-width": 140,
          },
        },
        {
          selector: ".paper",
          style: {
            "background-color": "#3b82f6",
            width: "mapData(citation_count, 0, 5000, 30, 68)",
            height: "mapData(citation_count, 0, 5000, 30, 68)",
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
        { selector: "edge[type = 'cites']", style: { "line-color": "#3b82f6", "target-arrow-color": "#3b82f6" } },
        { selector: "edge[type = 'extends']", style: { "line-color": "#22c55e", "target-arrow-color": "#22c55e" } },
        { selector: "edge[type = 'conflicts'], edge[type = 'conflicts_with']", style: { "line-color": "#ef4444", "target-arrow-color": "#ef4444" } },
        { selector: "edge[type = 'compared_to']", style: { "line-color": "#a855f7", "target-arrow-color": "#a855f7" } },
        { selector: "node:selected", style: { "border-color": "#22d3ee", "border-width": 4 } },
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
    cy.on("mouseover", "edge", (event) => {
      const edge = event.target;
      edge.style("label", edge.data("label") || edge.data("type"));
      edge.style("font-size", 9);
      edge.style("font-weight", 400);
      edge.style("color", nodeTextColor);
      edge.style("text-background-color", edgeLabelBackground);
      edge.style("text-background-opacity", 0.9);
      edge.style("text-background-padding", 2);
    });
    cy.on("mouseout", "edge", (event) => {
      event.target.style("label", "");
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
    <div className="flex h-full flex-col gap-6">
      <section className="relative overflow-hidden rounded-lg border border-border bg-card p-5 shadow-sm">
        <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-cyan-400 via-violet-500 to-amber-300" />
        <h1 className="text-2xl font-bold">{t(language, "knowledgeTitle")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t(language, "knowledgeSubtitle")}</p>
      </section>

      <div className="flex gap-3">
        <input
          type="text"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleQuery()}
          placeholder={t(language, "searchKnowledgePlaceholder")}
          className="flex-1 rounded-lg border border-input bg-background px-4 py-2.5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <button
          onClick={handleQuery}
          disabled={querying || !searchInput.trim()}
          className="rounded-lg bg-primary px-6 py-2.5 font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
        >
          {querying ? <Loader2 size={16} className="animate-spin" /> : <SearchIcon size={16} />}
        </button>
      </div>

      <div className="flex min-h-0 flex-1 gap-6">
        <div className="flex flex-1 flex-col overflow-hidden rounded-lg border border-border bg-card">
          <div className="flex items-center justify-between border-b border-border bg-muted/30 px-4 py-2.5">
            <span className="flex items-center gap-2 text-sm font-medium">
              <Network size={16} />
              {t(language, "knowledgeGraph")}
            </span>
            <span className="text-xs text-muted-foreground">
              {graphData?.nodes.length || 0} {t(language, "nodes")} / {graphData?.edges.length || 0} {t(language, "relations")}
            </span>
          </div>
          <div className="flex flex-1 items-center justify-center p-4">
            {graphData && graphData.nodes.length > 0 ? (
              <div ref={graphRef} className="h-full min-h-[360px] w-full" />
            ) : (
              <div className="text-center text-muted-foreground">
                <Network size={48} className="mx-auto mb-4 opacity-30" />
                <p className="text-sm">{t(language, "emptyKnowledge")}</p>
                <p className="mt-1 text-xs">{t(language, "emptyKnowledgeHelp")}</p>
              </div>
            )}
          </div>
        </div>

        <div className="flex w-[400px] shrink-0 flex-col gap-4">
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-border">
            <div className="border-b border-border bg-muted/30 px-4 py-2.5 text-sm font-medium">
              {t(language, "searchResults")}
            </div>
            <div className="flex-1 overflow-auto p-4">
              {queryResult ? (
                <div className="whitespace-pre-wrap text-sm leading-relaxed">{queryResult}</div>
              ) : (
                <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                  <div className="text-center">
                    <BookOpen size={32} className="mx-auto mb-2 opacity-30" />
                    {t(language, "searchKnowledgePrompt")}
                  </div>
                </div>
              )}
            </div>
          </div>
          <div className="min-h-[320px] flex-1">
            <ChatPanel defaultOpen />
          </div>
        </div>
      </div>
    </div>
  );
}
