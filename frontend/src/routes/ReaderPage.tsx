import { useParams, useNavigate } from "react-router-dom";
import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { api, apiUrl, type CitationGraphData, type CitationGraphNode, type Paper } from "../lib/api";
import { useKnowledgeStore } from "../stores/knowledgeStore";
import {
  ArrowLeft,
  AlertTriangle,
  Bot,
  Brain,
  BookOpen,
  CheckCircle2,
  Download,
  FileText,
  GitBranch,
  Loader2,
  MessageSquare,
  Plus,
  Save,
  ShieldCheck,
  Trash2,
  XCircle,
} from "lucide-react";
import ReactFlow, {
  Background,
  Controls,
  type Edge,
  type Node,
  useEdgesState,
  useNodesState,
} from "reactflow";
import "reactflow/dist/style.css";
import { t, type Language } from "../i18n";
import { useSettingsStore } from "../stores/settingsStore";
import { ChatPanel } from "../components/ChatPanel";

type Tab = "structure" | "mindmap" | "notes" | "citations" | "citation_graph" | "chat";

type CitationStatus = {
  total: number;
  verified: number;
  not_found: number;
  ambiguous: number;
  citations: Array<Record<string, unknown>>;
};

export default function ReaderPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [paper, setPaper] = useState<Paper | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("structure");
  const [parsing, setParsing] = useState(false);
  const [notes, setNotes] = useState("");
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [verifyingCitations, setVerifyingCitations] = useState(false);
  const [verificationProgress, setVerificationProgress] = useState("");
  const [citationStatus, setCitationStatus] = useState<CitationStatus | null>(null);
  const [citationGraph, setCitationGraph] = useState<CitationGraphData | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphError, setGraphError] = useState("");

  const mindmapData = useKnowledgeStore((s) => s.mindmapData);
  const fetchMindMap = useKnowledgeStore((s) => s.fetchMindMap);
  const saveMindMap = useKnowledgeStore((s) => s.saveMindMap);

  const language = useSettingsStore((s) => s.language);

  const fetchCitationGraph = async () => {
    if (!id) return;
    setGraphLoading(true);
    setGraphError("");
    try {
      const data = await api.get(`papers/${id}/citation-graph`).json<CitationGraphData>();
      if (data.error) {
        setCitationGraph(null);
        setGraphError(data.error);
      } else {
        setCitationGraph(data);
      }
    } catch (e) {
      setCitationGraph(null);
      setGraphError(`Failed to load citation graph: ${e}`);
    } finally {
      setGraphLoading(false);
    }
  };

  useEffect(() => {
    if (!id) return;
    setCitationGraph(null);
    setGraphError("");
    api
      .get(`papers/${id}`)
      .json<Paper>()
      .then((p) => {
        setPaper(p);
        setNotes(p.notes || "");
        if (p.pdf_path) {
          setPdfUrl(`${apiUrl(`papers/${id}/pdf`)}?t=${Date.now()}`);
        }
        setCitationStatus({
          total: p.citation_verified?.length || 0,
          verified: p.citation_verified?.filter((item) => item.status === "verified").length || 0,
          not_found: p.citation_verified?.filter((item) => item.status === "not_found").length || 0,
          ambiguous: p.citation_verified?.filter((item) => item.status === "ambiguous").length || 0,
          citations: p.citation_verified || [],
        });
        // 加载思维图
        fetchMindMap(id);
      });
    api
      .get(`papers/${id}/verification-status`)
      .json<CitationStatus>()
      .then(setCitationStatus)
      .catch(() => undefined);
  }, [id, fetchMindMap]);

  useEffect(() => {
    if (activeTab === "citation_graph" && !citationGraph && !graphLoading && !graphError) {
      fetchCitationGraph();
    }
  }, [activeTab, citationGraph, graphLoading, graphError]);

  const handleParse = async () => {
    if (!id) return;
    setParsing(true);
    try {
      const response = await fetch(apiUrl(`papers/${id}/parse`), {
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

  const handleDownloadPdf = async () => {
    if (!id) return;
    setDownloadingPdf(true);
    try {
      const result = await api
        .post(`papers/${id}/download-pdf`)
        .json<{ status: string; pdf_path?: string; error?: string }>();
      if (result.status === "downloaded" || result.status === "exists") {
        const next = await api.get(`papers/${id}`).json<Paper>();
        setPaper(next);
        setPdfUrl(`${apiUrl(`papers/${id}/pdf`)}?t=${Date.now()}`);
      } else {
        setPaper((prev) => prev ? { ...prev, pdf_download_error: result.error || "PDF download failed." } : prev);
      }
    } finally {
      setDownloadingPdf(false);
    }
  };

  const handleVerifyCitations = async () => {
    if (!id) return;
    setVerifyingCitations(true);
    setActiveTab("citations");
    setVerificationProgress("准备提取引用…");
    try {
      const response = await fetch(apiUrl(`papers/${id}/verify-citations`), { method: "POST" });
      await readSse(response, (data) => {
        if (data.type === "start") {
          setVerificationProgress(`发现 ${data.total || 0} 条候选引用`);
        }
        if (data.type === "citation_status") {
          setVerificationProgress(`${data.current || 0}/${data.total || 0}: ${String(data.citation || "")}`);
          setCitationStatus((prev) => {
            const citations = [...(prev?.citations || [])];
            citations.push(data);
            return summarizeCitations(citations);
          });
        }
        if (data.type === "summary") {
          setCitationStatus(data as CitationStatus);
        }
      });
    } finally {
      setVerifyingCitations(false);
      setVerificationProgress("");
    }
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
        <button
          onClick={handleVerifyCitations}
          disabled={verifyingCitations}
          className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm hover:bg-muted disabled:opacity-50"
        >
          {verifyingCitations ? <Loader2 size={15} className="animate-spin" /> : <ShieldCheck size={15} />}
          验证引用
        </button>
      </div>

      <div className="flex gap-4 flex-1 min-h-0">
        {/* PDF 阅读器 */}
        <div className="flex-1 border border-border rounded-lg overflow-hidden bg-card flex flex-col">
          <div className="px-4 py-2 border-b border-border bg-muted/30 flex items-center justify-between text-sm">
            <span className="text-muted-foreground">PDF 阅读器</span>
            {paper.pdf_path ? (
              <span className="inline-flex items-center gap-1 text-xs text-green-500">
                <Download size={14} /> 后台已缓存
              </span>
            ) : paper.pdf_url ? (
              <button
                onClick={handleDownloadPdf}
                disabled={downloadingPdf}
                className="text-primary hover:underline flex items-center gap-1 disabled:opacity-50"
              >
                {downloadingPdf ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                后台下载 PDF
              </button>
            ) : (
              <span className="text-xs text-muted-foreground">No PDF URL</span>
            )}
          </div>
          <div className="flex-1 flex items-center justify-center bg-muted/20">
            {paper.pdf_path ? (
              <iframe
                key={pdfUrl || paper.pdf_path}
                title={paper.title}
                src={pdfUrl || apiUrl(`papers/${id}/pdf`)}
                className="h-full w-full border-0 bg-background"
              />
            ) : (
              <div className="text-center p-8 text-muted-foreground">
                <FileText size={48} className="mx-auto mb-4 opacity-50" />
                <p className="text-sm">{t(language, "pdfCannotDisplay")}</p>
                <p className="text-xs mt-1">
                  {paper.pdf_download_error || (paper.pdf_url ? t(language, "pdfNotDownloaded") : t(language, "pdfNoOpenAccess"))}
                </p>
                {paper.pdf_url && (
                  <button
                    onClick={handleDownloadPdf}
                    disabled={downloadingPdf}
                    className="mt-4 inline-flex items-center gap-2 rounded-md border border-border px-3 py-2 text-xs text-foreground hover:bg-muted disabled:opacity-50"
                  >
                    {downloadingPdf ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                    {t(language, "downloadAndOpenPdf")}
                  </button>
                )}
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
              { key: "citations", label: "引用", icon: ShieldCheck },
              { key: "chat", label: "对话", icon: Bot },
              { key: "citation_graph", label: "引用图", icon: GitBranch },
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
                  <MindMapView
                    paperId={id!}
                    nodes={mindmapData[id!].nodes}
                    onSave={(nextNodes) => saveMindMap(id!, nextNodes)}
                  />
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

            {activeTab === "citations" && (
              <CitationVerificationPanel
                status={citationStatus}
                progress={verificationProgress}
                verifying={verifyingCitations}
                onVerify={handleVerifyCitations}
                language={language}
              />
            )}

            {activeTab === "citation_graph" && (
              <CitationGraphPanel
                data={citationGraph}
                loading={graphLoading}
                error={graphError}
                onRefresh={fetchCitationGraph}
                onOpenNode={(node) => {
                  if (node.local_id) {
                    navigate(`/papers/${node.local_id}`);
                    return;
                  }
                  if (node.url) {
                    window.open(node.url, "_blank", "noreferrer");
                  }
                }}
              />
            )}

            {activeTab === "chat" && (
              <div className="flex h-full min-h-[420px]">
                <ChatPanel
                  paperContext={{
                    title: paper.title,
                    abstract: paper.abstract,
                    extractedData: paper.extracted_data,
                  }}
                  defaultOpen
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

async function readSse(response: Response, onData: (data: Record<string, unknown>) => void) {
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
      if (!line.startsWith("data: ")) continue;
      try {
        onData(JSON.parse(line.slice(6)));
      } catch {
        // Ignore malformed SSE rows.
      }
    }
  }
}

function summarizeCitations(citations: Array<Record<string, unknown>>): CitationStatus {
  return {
    total: citations.length,
    verified: citations.filter((item) => item.status === "verified").length,
    not_found: citations.filter((item) => item.status === "not_found").length,
    ambiguous: citations.filter((item) => item.status === "ambiguous").length,
    citations,
  };
}

function CitationGraphPanel({
  data,
  loading,
  error,
  onRefresh,
  onOpenNode,
}: {
  data: CitationGraphData | null;
  loading: boolean;
  error: string;
  onRefresh: () => void;
  onOpenNode: (node: CitationGraphNode) => void;
}) {
  const { flowNodes, flowEdges } = useMemo(() => toCitationFlowElements(data), [data]);

  if (loading) {
    return (
      <div className="flex h-full min-h-[420px] items-center justify-center text-sm text-muted-foreground">
        <Loader2 size={18} className="mr-2 animate-spin" />
        Loading citation graph...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex h-full min-h-[420px] flex-col items-center justify-center rounded-lg border border-dashed border-border p-4 text-center">
        <GitBranch size={28} className="mb-3 text-muted-foreground" />
        <div className="text-sm font-medium text-foreground">Citation graph unavailable</div>
        <div className="mt-1 text-xs text-muted-foreground">{error || "No citation graph data."}</div>
        <button
          onClick={onRefresh}
          className="mt-3 rounded-md border border-border px-3 py-1.5 text-xs hover:bg-muted"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-[420px] flex-col gap-3">
      <div className="grid grid-cols-3 gap-2 text-xs">
        <CitationMetric label="Seed" value={1} />
        <CitationMetric label="References" value={data.references.length} />
        <CitationMetric label="Citations" value={data.citations.length} />
      </div>
      <div className="relative min-h-[360px] flex-1 overflow-hidden rounded-lg border border-border bg-background">
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          onNodeClick={(_, node) => onOpenNode(node.data.sourceNode as CitationGraphNode)}
          fitView
          panOnDrag
          nodesDraggable
        >
          <Background gap={18} color="hsl(215 20.2% 65.1% / 0.22)" />
          <Controls />
        </ReactFlow>
      </div>
    </div>
  );
}

function toCitationFlowElements(data: CitationGraphData | null): { flowNodes: Node[]; flowEdges: Edge[] } {
  if (!data) return { flowNodes: [], flowEdges: [] };

  const nodes = data.graph.nodes;
  const references = nodes.filter((node) => node.group === "reference");
  const citations = nodes.filter((node) => node.group === "citation");
  const seed = nodes.find((node) => node.is_seed) || data.paper;
  const flowNodes: Node[] = [];

  flowNodes.push(toCitationFlowNode(seed, { x: 360, y: 210 }));
  references.forEach((node, index) => {
    flowNodes.push(toCitationFlowNode(node, { x: 20, y: laneY(index, references.length) }));
  });
  citations.forEach((node, index) => {
    flowNodes.push(toCitationFlowNode(node, { x: 700, y: laneY(index, citations.length) }));
  });

  const flowEdges = data.graph.edges.map<Edge>((edge, index) => ({
    id: `${edge.source}->${edge.target}:${index}`,
    source: edge.source,
    target: edge.target,
    type: "smoothstep",
    animated: true,
    style: { stroke: "hsl(215 20.2% 65.1%)" },
  }));

  return { flowNodes, flowEdges };
}

function laneY(index: number, total: number) {
  const spacing = 118;
  const offset = Math.max(0, (total - 1) * spacing) / 2;
  return 210 + index * spacing - offset;
}

function toCitationFlowNode(node: CitationGraphNode, position: { x: number; y: number }): Node {
  return {
    id: node.id,
    position,
    data: {
      sourceNode: node,
      label: renderCitationFlowLabel(node),
    },
    style: citationNodeStyle(node.group),
  };
}

function citationNodeStyle(group: CitationGraphNode["group"]): CSSProperties {
  const tones: Record<CitationGraphNode["group"], CSSProperties> = {
    seed: { borderColor: "#f59e0b", background: "rgba(245, 158, 11, 0.16)" },
    reference: { borderColor: "#38bdf8", background: "rgba(14, 165, 233, 0.12)" },
    citation: { borderColor: "#34d399", background: "rgba(16, 185, 129, 0.12)" },
  };
  return {
    width: 220,
    borderRadius: 8,
    border: "1px solid var(--color-border)",
    color: "var(--color-foreground)",
    fontSize: 12,
    padding: 10,
    cursor: "pointer",
    ...tones[group],
  };
}

function renderCitationFlowLabel(node: CitationGraphNode) {
  return (
    <div title={node.title} className="max-w-[200px]">
      <div className="line-clamp-2 text-xs font-semibold">{node.title || node.label}</div>
      <div className="mt-1 flex flex-wrap gap-1 text-[10px] text-muted-foreground">
        {node.year && <span>{node.year}</span>}
        <span>{node.citation_count || 0} cites</span>
        {node.local_id && <span className="text-cyan-500">local</span>}
      </div>
    </div>
  );
}

function CitationVerificationPanel({
  status,
  progress,
  verifying,
  onVerify,
  language,
}: {
  status: CitationStatus | null;
  progress: string;
  verifying: boolean;
  onVerify: () => void;
  language: Language;
}) {
  const citations = status?.citations || [];
  return (
    <div className="flex h-full flex-col gap-3 text-sm">
      <div className="grid grid-cols-4 gap-2 text-xs">
        <CitationMetric label="Total" value={status?.total || 0} />
        <CitationMetric label="Verified" value={status?.verified || 0} />
        <CitationMetric label="Ambiguous" value={status?.ambiguous || 0} />
        <CitationMetric label="Missing" value={status?.not_found || 0} />
      </div>
      <button
        onClick={onVerify}
        disabled={verifying}
        className="inline-flex items-center justify-center gap-2 rounded-md bg-primary px-3 py-2 text-xs text-primary-foreground disabled:opacity-50"
      >
        {verifying ? <Loader2 size={13} className="animate-spin" /> : <ShieldCheck size={13} />}
        {verifying ? t(language, "verifying") : t(language, "reVerifyCitations")}
      </button>
      {progress && <div className="rounded-md bg-muted/40 p-2 text-xs text-muted-foreground">{progress}</div>}
      <div className="min-h-0 flex-1 overflow-auto">
        {citations.length === 0 ? (
          <div className="flex h-40 items-center justify-center rounded-lg border border-dashed border-border text-center text-xs text-muted-foreground">
            {t(language, "noCitationVerification")}
          </div>
        ) : (
          citations.map((item, index) => <CitationRow key={`${String(item.citation)}-${index}`} item={item} />)
        )}
      </div>
    </div>
  );
}

function CitationMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md bg-muted/40 p-2">
      <div className="text-muted-foreground">{label}</div>
      <div className="text-base font-semibold">{value}</div>
    </div>
  );
}

function CitationRow({ item }: { item: Record<string, unknown> }) {
  const status = String(item.status || "not_found");
  const Icon = status === "verified" ? CheckCircle2 : status === "ambiguous" ? AlertTriangle : XCircle;
  const tone = status === "verified" ? "text-green-500" : status === "ambiguous" ? "text-amber-500" : "text-destructive";
  const match = item.match as Record<string, unknown> | null;
  return (
    <div className="mb-2 rounded-md border border-border p-2 text-xs">
      <div className={`mb-1 flex items-center gap-1 font-medium ${tone}`}>
        <Icon size={13} />
        {status}
      </div>
      <div className="line-clamp-2">{String(item.citation || "")}</div>
      {match !== null && Boolean(match.title) && (
        <div className="mt-1 line-clamp-2 text-muted-foreground">
          Match: {String(match.title)} {match.year ? `(${String(match.year)})` : ""}
        </div>
      )}
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
  paper_id: string;
  label: string;
  node_type: string;
  content: string;
  position: { x: number; y: number };
  parent_id: string | null;
};

type MindMapContextMenu = {
  nodeId: string;
  x: number;
  y: number;
} | null;

type MindMapEditState = {
  nodeId: string;
  label: string;
  content: string;
} | null;

function MindMapView({
  paperId,
  nodes,
  onSave,
}: {
  paperId: string;
  nodes: MindMapNode[];
  onSave: (nodes: MindMapNode[]) => Promise<void>;
}) {
  const { flowNodes, flowEdges } = useMemo(() => toFlowElements(nodes), [nodes]);
  const [reactFlowNodes, setReactFlowNodes, onNodesChange] = useNodesState(flowNodes);
  const [reactFlowEdges, setReactFlowEdges, onEdgesChange] = useEdgesState(flowEdges);
  const [contextMenu, setContextMenu] = useState<MindMapContextMenu>(null);
  const [editing, setEditing] = useState<MindMapEditState>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setReactFlowNodes(flowNodes);
    setReactFlowEdges(flowEdges);
  }, [flowNodes, flowEdges, setReactFlowEdges, setReactFlowNodes]);

  if (nodes.length === 0) {
    return <div className="text-muted-foreground text-sm">Empty mind map</div>;
  }

  const updateNodeData = (nodeId: string, patch: Partial<MindMapNode>) => {
    setReactFlowNodes((current) =>
      current.map((node) => {
        if (node.id !== nodeId) return node;
        const nextData = {
          ...node.data,
          labelText: patch.label ?? node.data.labelText,
          content: patch.content ?? node.data.content,
          node_type: patch.node_type ?? node.data.node_type,
          parent_id: patch.parent_id ?? node.data.parent_id,
        };
        return {
          ...node,
          data: {
            ...nextData,
            label: renderFlowLabel(nextData.labelText, nextData.content),
          },
          style: {
            ...node.style,
            ...nodeTypeStyle(nextData.node_type),
          },
        };
      })
    );
  };

  const editNode = (nodeId: string) => {
    const node = reactFlowNodes.find((item) => item.id === nodeId);
    if (!node) return;
    setEditing({
      nodeId,
      label: String(node.data.labelText || ""),
      content: String(node.data.content || ""),
    });
  };

  const addChild = (nodeId: string) => {
    const parent = reactFlowNodes.find((item) => item.id === nodeId);
    if (!parent) return;

    const childId = `manual-${Date.now()}`;
    const child: Node = {
      id: childId,
      position: {
        x: parent.position.x + 220,
        y: parent.position.y + 80,
      },
      data: {
        labelText: "New Node",
        content: "",
        node_type: "other",
        parent_id: nodeId,
        label: renderFlowLabel("New Node", ""),
      },
      style: baseNodeStyle("other"),
    };

    setReactFlowNodes((current) => [...current, child]);
    setReactFlowEdges((current) => [
      ...current,
      {
        id: `${nodeId}->${childId}`,
        source: nodeId,
        target: childId,
        type: "smoothstep",
        style: { stroke: "hsl(215 20.2% 65.1%)" },
      },
    ]);
    setContextMenu(null);
  };

  const deleteNode = (nodeId: string) => {
    const removeIds = new Set([nodeId]);
    let changed = true;
    while (changed) {
      changed = false;
      for (const node of reactFlowNodes) {
        if (removeIds.has(String(node.data.parent_id)) && !removeIds.has(node.id)) {
          removeIds.add(node.id);
          changed = true;
        }
      }
    }

    setReactFlowNodes((current) => current.filter((node) => !removeIds.has(node.id)));
    setReactFlowEdges((current) =>
      current.filter((edge) => !removeIds.has(edge.source) && !removeIds.has(edge.target))
    );
    setContextMenu(null);
  };

  const changeType = (nodeId: string) => {
    const node = reactFlowNodes.find((item) => item.id === nodeId);
    if (!node) return;
    const nextType = window.prompt(
      "节点类型",
      String(node.data.node_type || "other")
    );
    if (!nextType) return;
    updateNodeData(nodeId, { node_type: nextType });
    setContextMenu(null);
  };

  const save = async () => {
    setSaving(true);
    try {
      await onSave(
        reactFlowNodes.map((node) => ({
          id: node.id,
          paper_id: paperId,
          parent_id: String(node.data.parent_id || "") || null,
          label: String(node.data.labelText || ""),
          node_type: String(node.data.node_type || "other"),
          content: String(node.data.content || ""),
          position: node.position,
        }))
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="relative h-full min-h-[420px] overflow-hidden rounded-lg border border-border bg-background">
      <div className="absolute right-2 top-2 z-10">
        <button
          onClick={save}
          disabled={saving}
          className="inline-flex items-center gap-1 rounded-md bg-primary px-2.5 py-1.5 text-xs text-primary-foreground shadow disabled:opacity-50"
        >
          <Save size={13} />
          {saving ? "保存中" : "保存"}
        </button>
      </div>
      <ReactFlow
        key={nodes.map((node) => node.id).join(":")}
        nodes={reactFlowNodes}
        edges={reactFlowEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeDoubleClick={(_, node) => editNode(node.id)}
        onNodeContextMenu={(event, node) => {
          event.preventDefault();
          setContextMenu({ nodeId: node.id, x: event.clientX, y: event.clientY });
        }}
        onPaneClick={() => setContextMenu(null)}
        fitView
        nodesDraggable
        panOnDrag
      >
        <Background gap={16} color="hsl(215 20.2% 65.1% / 0.22)" />
        <Controls />
      </ReactFlow>

      {contextMenu && (
        <div
          className="fixed z-50 overflow-hidden rounded-md border border-border bg-popover text-popover-foreground shadow-lg"
          style={{ left: contextMenu.x, top: contextMenu.y }}
        >
          <button
            onClick={() => addChild(contextMenu.nodeId)}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs hover:bg-muted"
          >
            <Plus size={13} />
            添加子节点
          </button>
          <button
            onClick={() => changeType(contextMenu.nodeId)}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs hover:bg-muted"
          >
            <BookOpen size={13} />
            修改类型
          </button>
          <button
            onClick={() => deleteNode(contextMenu.nodeId)}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-destructive hover:bg-muted"
          >
            <Trash2 size={13} />
            删除节点
          </button>
        </div>
      )}

      {editing && (
        <div className="absolute inset-x-3 bottom-3 z-20 rounded-lg border border-border bg-card p-3 shadow-xl">
          <div className="mb-2 text-xs font-medium">编辑节点</div>
          <input
            value={editing.label}
            onChange={(e) => setEditing((prev) => prev ? { ...prev, label: e.target.value } : prev)}
            className="mb-2 h-9 w-full rounded-md border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
            placeholder="节点标题"
          />
          <textarea
            value={editing.content}
            onChange={(e) => setEditing((prev) => prev ? { ...prev, content: e.target.value } : prev)}
            className="h-24 w-full resize-none rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            placeholder="节点内容"
          />
          <div className="mt-2 flex justify-end gap-2">
            <button
              onClick={() => setEditing(null)}
              className="rounded-md border border-border px-3 py-1.5 text-xs hover:bg-muted"
            >
              取消
            </button>
            <button
              onClick={() => {
                updateNodeData(editing.nodeId, {
                  label: editing.label,
                  content: editing.content,
                });
                setEditing(null);
              }}
              className="rounded-md bg-primary px-3 py-1.5 text-xs text-primary-foreground"
            >
              应用
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function toFlowElements(nodes: MindMapNode[]): { flowNodes: Node[]; flowEdges: Edge[] } {
  const flowNodes = nodes.map<Node>((node) => ({
    id: node.id,
    position: node.position,
    data: {
      labelText: node.label,
      content: node.content,
      node_type: node.node_type,
      parent_id: node.parent_id,
      label: renderFlowLabel(node.label, node.content),
    },
    style: baseNodeStyle(node.node_type),
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

function nodeTypeStyle(nodeType: string): CSSProperties {
  const typeStyles: Record<string, CSSProperties> = {
    root: { borderColor: "#60a5fa", background: "rgba(59, 130, 246, 0.14)" },
    problem: { borderColor: "#f87171", background: "rgba(239, 68, 68, 0.12)" },
    method: { borderColor: "#38bdf8", background: "rgba(14, 165, 233, 0.12)" },
    sub_method: { borderColor: "#22d3ee", background: "rgba(34, 211, 238, 0.12)" },
    experiment: { borderColor: "#34d399", background: "rgba(16, 185, 129, 0.12)" },
    conclusion: { borderColor: "#a78bfa", background: "rgba(139, 92, 246, 0.12)" },
  };

  return typeStyles[nodeType] || {};
}

function baseNodeStyle(nodeType: string): CSSProperties {
  return {
    width: 190,
    borderRadius: 8,
    border: "1px solid var(--color-border)",
    color: "var(--color-foreground)",
    fontSize: 12,
    padding: 8,
    ...nodeTypeStyle(nodeType),
  };
}

function renderFlowLabel(label: string, content: string) {
  return (
    <div title={content} className="max-w-[180px]">
      <div className="text-xs font-semibold">{label}</div>
      {content && (
        <div className="mt-1 line-clamp-2 text-[10px] text-muted-foreground">
          {content}
        </div>
      )}
    </div>
  );
}
