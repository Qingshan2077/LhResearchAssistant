import { useParams, useNavigate } from "react-router-dom";
import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { api, type Paper } from "../lib/api";
import { useKnowledgeStore } from "../stores/knowledgeStore";
import { ArrowLeft, Download, FileText, Brain, MessageSquare, BookOpen } from "lucide-react";
import ReactFlow, {
  Background,
  Controls,
  type Edge,
  type Node,
  useEdgesState,
  useNodesState,
} from "reactflow";
import "reactflow/dist/style.css";

type Tab = "structure" | "mindmap" | "notes" | "chat";

export default function ReaderPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [paper, setPaper] = useState<Paper | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("structure");
  const [parsing, setParsing] = useState(false);
  const [notes, setNotes] = useState("");
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);

  const mindmapData = useKnowledgeStore((s) => s.mindmapData);
  const fetchMindMap = useKnowledgeStore((s) => s.fetchMindMap);

  useEffect(() => {
    if (!id) return;
    api
      .get(`papers/${id}`)
      .json<Paper>()
      .then((p) => {
        setPaper(p);
        setNotes(p.notes || "");
        if (p.pdf_path) {
          setPdfUrl(`/api/v1/papers/${id}/pdf?t=${Date.now()}`);
        }
        // 加载思维图
        fetchMindMap(id);
      });
  }, [id, fetchMindMap]);

  const handleParse = async () => {
    if (!id) return;
    setParsing(true);
    try {
      const response = await fetch(`/api/v1/papers/${id}/parse`, {
        method: "POST",
      });
      const reader = response.body?.getReader();
      if (!reader) return;

      const decoder = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const text = decoder.decode(value, { stream: true });
        // 解析 SSE 事件
        for (const line of text.split("\n")) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === "result") {
                setPaper((prev) =>
                  prev ? { ...prev, extracted_data: data.extracted_data } : prev
                );
                fetchMindMap(id);
              } else if (data.type === "done") {
                setParsing(false);
              } else if (data.type === "error") {
                console.error("Parse error:", data.message);
                setParsing(false);
              }
            } catch {
              // ignore
            }
          }
        }
      }
    } catch (e) {
      console.error("Parse failed:", e);
    }
    setParsing(false);
  };

  const handleSaveNotes = async () => {
    if (!id) return;
    await api.patch(`papers/${id}`, { json: { notes } });
  };

  if (!paper) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        加载中…
      </div>
    );
  }

  const extracted = paper.extracted_data as Record<string, unknown> || {};
  const method = extracted.method as Record<string, unknown> || {};

  return (
    <div className="flex flex-col h-full">
      {/* 顶部导航 */}
      <div className="flex items-center gap-4 mb-4 pb-4 border-b border-border">
        <button
          onClick={() => navigate(-1)}
          className="p-2 rounded-lg hover:bg-muted transition-colors"
        >
          <ArrowLeft size={18} />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-semibold truncate">{paper.title}</h1>
          <p className="text-xs text-muted-foreground truncate">
            {paper.authors?.join(", ")} · {paper.year} · {paper.venue}
          </p>
        </div>

        {/* 操作按钮 */}
        {!paper.extracted_data || Object.keys(paper.extracted_data).length === 0 ? (
          <button
            onClick={handleParse}
            disabled={parsing}
            className="px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors text-sm"
          >
            {parsing ? "解析中…" : "AI 解析论文"}
          </button>
        ) : (
          <span className="text-xs text-green-500 flex items-center gap-1">
            <Brain size={14} /> 已解析
          </span>
        )}
      </div>

      <div className="flex gap-4 flex-1 min-h-0">
        {/* PDF 阅读器 */}
        <div className="flex-1 border border-border rounded-lg overflow-hidden bg-card flex flex-col">
          <div className="px-4 py-2 border-b border-border bg-muted/30 flex items-center justify-between text-sm">
            <span className="text-muted-foreground">PDF 阅读器</span>
            {paper.pdf_path && (
              <a
                href={pdfUrl || "#"}
                download
                className="text-primary hover:underline flex items-center gap-1"
              >
                <Download size={14} /> 下载
              </a>
            )}
          </div>
          <div className="flex-1 flex items-center justify-center bg-muted/20">
            {paper.pdf_path ? (
              <iframe
                title={paper.title}
                src={pdfUrl || `/api/v1/papers/${id}/pdf`}
                className="h-full w-full border-0 bg-background"
              />
            ) : (
              <div className="text-center p-8 text-muted-foreground">
                <FileText size={48} className="mx-auto mb-4 opacity-50" />
                <p className="text-sm">无 PDF 文件</p>
                <p className="text-xs mt-1">导入 PDF 后才能在线阅读</p>
              </div>
            )}
          </div>
        </div>

        {/* 右侧面板 */}
        <div className="w-[400px] border border-border rounded-lg overflow-hidden flex flex-col shrink-0">
          {/* Tab 切换 */}
          <div className="flex border-b border-border bg-muted/20">
            {([
              { key: "structure", label: "结构化", icon: Brain },
              { key: "mindmap", label: "思维图", icon: BookOpen },
              { key: "notes", label: "笔记", icon: MessageSquare },
            ] as const).map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={`flex-1 px-3 py-2.5 text-xs font-medium flex items-center justify-center gap-1.5 transition-colors ${
                  activeTab === key
                    ? "text-primary border-b-2 border-primary bg-primary/5"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <Icon size={14} />
                {label}
              </button>
            ))}
          </div>

          {/* Tab 内容 */}
          <div className="flex-1 overflow-auto p-4">
            {activeTab === "structure" && (
              <div className="space-y-4 text-sm">
                {extracted.problem ? (
                  <>
                    <Section title="Problem" content={extracted.problem as string} />
                    {extracted.background && (
                      <Section title="Background" content={extracted.background as string} />
                    )}
                    {method.overview && (
                      <Section title="Method Overview" content={method.overview as string} />
                    )}
                    {method.components && Array.isArray(method.components) && (
                      <div>
                        <h4 className="font-medium text-sm mb-2">Components</h4>
                        {(method.components as Array<Record<string, string>>).map(
                          (c: Record<string, string>, i: number) => (
                            <div key={i} className="ml-2 mb-2 p-2 rounded bg-muted/30">
                              <strong>{c.name}</strong>
                              <p className="text-xs text-muted-foreground mt-1">
                                {c.description}
                              </p>
                              {c.key_insight && (
                                <p className="text-xs text-primary mt-1">
                                  💡 {c.key_insight}
                                </p>
                              )}
                            </div>
                          )
                        )}
                      </div>
                    )}
                    {extracted.contributions && (
                      <div>
                        <h4 className="font-medium text-sm mb-1">Contributions</h4>
                        <ul className="list-disc list-inside text-xs text-muted-foreground space-y-1">
                          {(extracted.contributions as string[]).map(
                            (c: string, i: number) => (
                              <li key={i}>{c}</li>
                            )
                          )}
                        </ul>
                      </div>
                    )}
                    {extracted.limitations && (
                      <Section title="Limitations" content={(extracted.limitations as string[]).join("; ")} />
                    )}
                  </>
                ) : (
                  <div className="text-center text-muted-foreground py-8 text-sm">
                    尚未解析
                    <br />
                    <button
                      onClick={handleParse}
                      className="mt-2 text-primary hover:underline"
                    >
                      点击 AI 解析
                    </button>
                  </div>
                )}
              </div>
            )}

            {activeTab === "mindmap" && (
              <div className="h-full">
                {mindmapData[id!] ? (
                  <MindMapView nodes={mindmapData[id!].nodes} />
                ) : (
                  <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                    {parsing ? "生成中…" : "解析论文后生成思维图"}
                  </div>
                )}
              </div>
            )}

            {activeTab === "notes" && (
              <div className="flex flex-col h-full">
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="写笔记…"
                  className="flex-1 w-full resize-none bg-transparent text-sm focus:outline-none"
                />
                <button
                  onClick={handleSaveNotes}
                  className="mt-2 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs self-end"
                >
                  保存笔记
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Section({ title, content }: { title: string; content: string }) {
  return (
    <div>
      <h4 className="font-medium text-sm mb-1">{title}</h4>
      <p className="text-xs text-muted-foreground leading-relaxed">{content}</p>
    </div>
  );
}

type MindMapNode = {
  id: string;
  label: string;
  node_type: string;
  content: string;
  position: { x: number; y: number };
  parent_id: string | null;
};

function MindMapView({ nodes }: { nodes: MindMapNode[] }) {
  const { flowNodes, flowEdges } = useMemo(() => toFlowElements(nodes), [nodes]);
  const [reactFlowNodes, setReactFlowNodes, onNodesChange] = useNodesState(flowNodes);
  const [reactFlowEdges, setReactFlowEdges, onEdgesChange] = useEdgesState(flowEdges);

  useEffect(() => {
    setReactFlowNodes(flowNodes);
    setReactFlowEdges(flowEdges);
  }, [flowNodes, flowEdges, setReactFlowEdges, setReactFlowNodes]);

  if (nodes.length === 0) {
    return <div className="text-muted-foreground text-sm">Empty mind map</div>;
  }

  return (
    <div className="h-full min-h-[420px] overflow-hidden rounded-lg border border-border bg-background">
      <ReactFlow
        key={nodes.map((node) => node.id).join(":")}
        nodes={reactFlowNodes}
        edges={reactFlowEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        nodesDraggable
        panOnDrag
      >
        <Background gap={16} color="hsl(215 20.2% 65.1% / 0.22)" />
        <Controls />
      </ReactFlow>
    </div>
  );
}

function toFlowElements(nodes: MindMapNode[]): { flowNodes: Node[]; flowEdges: Edge[] } {
  const typeStyles: Record<string, CSSProperties> = {
    root: { borderColor: "#60a5fa", background: "rgba(59, 130, 246, 0.14)" },
    problem: { borderColor: "#f87171", background: "rgba(239, 68, 68, 0.12)" },
    method: { borderColor: "#38bdf8", background: "rgba(14, 165, 233, 0.12)" },
    sub_method: { borderColor: "#22d3ee", background: "rgba(34, 211, 238, 0.12)" },
    experiment: { borderColor: "#34d399", background: "rgba(16, 185, 129, 0.12)" },
    conclusion: { borderColor: "#a78bfa", background: "rgba(139, 92, 246, 0.12)" },
  };

  const flowNodes = nodes.map<Node>((node) => ({
    id: node.id,
    position: node.position,
    data: {
      label: (
        <div title={node.content} className="max-w-[180px]">
          <div className="text-xs font-semibold">{node.label}</div>
          {node.content && (
            <div className="mt-1 line-clamp-2 text-[10px] text-muted-foreground">
              {node.content}
            </div>
          )}
        </div>
      ),
    },
    style: {
      width: 190,
      borderRadius: 8,
      border: "1px solid var(--color-border)",
      color: "var(--color-foreground)",
      fontSize: 12,
      padding: 8,
      ...(typeStyles[node.node_type] || {}),
    },
  }));

  const flowEdges = nodes
    .filter((node) => node.parent_id)
    .map<Edge>((node) => ({
      id: `${node.parent_id}->${node.id}`,
      source: node.parent_id as string,
      target: node.id,
      type: "smoothstep",
      animated: node.node_type === "method",
      style: { stroke: "hsl(215 20.2% 65.1%)" },
    }));

  return { flowNodes, flowEdges };
}
