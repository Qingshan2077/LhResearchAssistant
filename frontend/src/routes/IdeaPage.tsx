import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  BarChart3,
  BrainCircuit,
  Check,
  FlaskConical,
  GitCompare,
  History,
  Lightbulb,
  Loader2,
  Plus,
  Save,
  Search,
  Sparkles,
  Trash2,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import clsx from "clsx";
import { api, apiUrl, type IdeaHistoryDetail, type IdeaHistoryItem, type Paper } from "../lib/api";
import { t } from "../i18n";
import { useSettingsStore } from "../stores/settingsStore";
import { useSocraticIdeaBridgeStore } from "../stores/socraticIdeaBridgeStore";

type IdeaMode = "gap_analysis" | "cross_domain" | "trend_based";
type GenerationPhase = "generating" | "evaluating" | "done";

type Evaluation = {
  idea_title: string;
  novelty: number;
  feasibility: number;
  cost: number;
  reasoning: string;
  risk?: string;
  report?: string;
};

const MODES: Array<{ id: IdeaMode; label: string; icon: LucideIcon }> = [
  { id: "gap_analysis", label: "Gap 分析", icon: Lightbulb },
  { id: "cross_domain", label: "跨领域迁移", icon: GitCompare },
  { id: "trend_based", label: "趋势预测", icon: BarChart3 },
];

export default function IdeaPage() {
  const navigate = useNavigate();
  const [papers, setPapers] = useState<Paper[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [mode, setMode] = useState<IdeaMode>("gap_analysis");
  const [domainA, setDomainA] = useState("");
  const [domainB, setDomainB] = useState("");
  const [customPrompt, setCustomPrompt] = useState("");
  const [socraticContextDraft, setSocraticContextDraft] = useState("");
  const [search, setSearch] = useState("");
  const [generating, setGenerating] = useState(false);
  const [phase, setPhase] = useState<GenerationPhase>("done");
  const [streamStatus, setStreamStatus] = useState("");
  const [content, setContent] = useState("");
  const [evaluations, setEvaluations] = useState<Record<string, Evaluation>>({});
  const [sidebarTab, setSidebarTab] = useState<"papers" | "history">("papers");
  const [historyList, setHistoryList] = useState<IdeaHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [savingHistory, setSavingHistory] = useState(false);
  const [historySaved, setHistorySaved] = useState(false);
  const [viewingHistoryId, setViewingHistoryId] = useState<string | null>(null);
  const language = useSettingsStore((s) => s.language);
  const {
    availableSessions,
    loading: socraticLoading,
    error: socraticError,
    selectedSessionId,
    selectedSessionSummary,
    useSocraticContext,
    fetchSocraticSessions,
    selectSession,
    clearSelection,
    setUseSocraticContext,
    buildContextPrompt,
  } = useSocraticIdeaBridgeStore();

  useEffect(() => {
    setSocraticContextDraft(
      useSocraticContext && selectedSessionSummary ? buildContextPrompt() : ""
    );
  }, [buildContextPrompt, selectedSessionSummary, useSocraticContext]);

  const effectiveCustomPrompt = useMemo(() => {
    const context = useSocraticContext ? socraticContextDraft.trim() : "";
    if (!context) return customPrompt;
    if (!customPrompt.trim()) return context;
    return `${customPrompt.trimEnd()}\n\n---\n\n${context}`;
  }, [customPrompt, socraticContextDraft, useSocraticContext]);

  useEffect(() => {
    api
      .get("papers", { searchParams: { project_id: "default", page_size: 500 } })
      .json<{ items: Paper[] }>()
      .then((resp) => setPapers(resp.items))
      .catch(() => setPapers([]));
    void refreshIdeaHistory();
    void fetchSocraticSessions();
  }, []);

  async function refreshIdeaHistory() {
    setHistoryLoading(true);
    try {
      const rows = await api
        .get("ideas/history", { searchParams: { project_id: "default" } })
        .json<IdeaHistoryItem[]>();
      setHistoryList(rows);
    } catch {
      setHistoryList([]);
    } finally {
      setHistoryLoading(false);
    }
  }

  const saveIdeaHistory = async () => {
    if (!content.trim() || historySaved || viewingHistoryId) return;
    setSavingHistory(true);
    try {
      await api.post("ideas/history/save", {
        json: {
          project_id: "default",
          mode,
          paper_ids: Array.from(selectedIds),
          custom_prompt: effectiveCustomPrompt,
          domain_a: domainA,
          domain_b: domainB,
          generated_content: content,
          evaluations: Object.values(evaluations),
        },
      });
      setHistorySaved(true);
      await refreshIdeaHistory();
    } finally {
      setSavingHistory(false);
    }
  };

  const openIdeaHistory = async (historyId: string) => {
    const detail = await api.get(`ideas/history/${historyId}`).json<IdeaHistoryDetail>();
    setUseSocraticContext(false);
    setViewingHistoryId(detail.id);
    setMode(detail.mode as IdeaMode);
    setSelectedIds(new Set(detail.paper_ids || []));
    setCustomPrompt(detail.custom_prompt || "");
    setDomainA(detail.domain_a || "");
    setDomainB(detail.domain_b || "");
    setContent(detail.generated_content || "");
    setEvaluations(
      (detail.evaluations || []).reduce<Record<string, Evaluation>>((result, value) => {
        const evaluation = value as Evaluation;
        if (evaluation.idea_title) result[evaluation.idea_title] = evaluation;
        return result;
      }, {})
    );
    setPhase("done");
    setStreamStatus("");
  };

  const deleteIdeaHistory = async (historyId: string) => {
    if (!window.confirm(t(language, "deleteIdeaHistoryConfirm"))) return;
    await api.delete(`ideas/history/${historyId}`);
    if (viewingHistoryId === historyId) startNewIdea();
    await refreshIdeaHistory();
  };

  const startNewIdea = () => {
    setUseSocraticContext(false);
    setViewingHistoryId(null);
    setMode("gap_analysis");
    setDomainA("");
    setDomainB("");
    setCustomPrompt("");
    setContent("");
    setEvaluations({});
    setSelectedIds(new Set());
    setHistorySaved(false);
    setSidebarTab("papers");
  };
  const filteredPapers = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    if (!keyword) return papers;
    return papers.filter((paper) =>
      [paper.title, paper.abstract, paper.venue, paper.authors?.join(" ")]
        .join(" ")
        .toLowerCase()
        .includes(keyword)
    );
  }, [papers, search]);

  const ideaCards = useMemo(() => parseIdeaCards(content), [content]);

  const togglePaper = (paperId: string) => {
    if (viewingHistoryId) return;
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(paperId)) next.delete(paperId);
      else next.add(paperId);
      return next;
    });
  };

  const generateIdeas = async () => {
    if (viewingHistoryId) return;
    setHistorySaved(false);
    setGenerating(true);
    setPhase("generating");
    setStreamStatus("");
    setContent("");
    setEvaluations({});

    try {
      const response = await fetch(apiUrl("ideas/generate"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: "default",
          paper_ids: Array.from(selectedIds),
          mode,
          custom_prompt: effectiveCustomPrompt,
          domain_a: domainA,
          domain_b: domainB,
        }),
      });

      if (!response.ok) throw new Error(`Generate failed: ${response.status}`);

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
            const data = JSON.parse(line.slice(6));
            if (data.type === "chunk") {
              setContent((prev) => prev + data.content);
            } else if (data.type === "status") {
              setStreamStatus(String(data.message || ""));
            } else if (data.type === "generation_done") {
              setPhase("evaluating");
            } else if (data.type === "evaluation" && data.evaluation) {
              const evaluation = data.evaluation as Evaluation;
              setEvaluations((prev) => ({
                ...prev,
                [evaluation.idea_title]: evaluation,
              }));
            } else if (data.type === "done") {
              setPhase("done");
            } else if (data.type === "error") {
              setContent((prev) => prev + `\n\n> ${data.message}`);
            }
          } catch {
            // Ignore malformed stream rows.
          }
        }
      }
    } catch (error) {
      setContent(`${t(language, "generateFailed")}: ${error}`);
      setPhase("done");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="flex min-h-full flex-col gap-5">
      <section className="rounded-lg border border-border bg-card p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-amber-500">
              <Sparkles size={14} />
              Research Ideation
            </div>
            <h1 className="mt-2 text-3xl font-semibold">{t(language, "ideaTitle")}</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {t(language, "ideaSubtitle")}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => navigate("/ideas/socratic")}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-border px-4 text-sm font-medium hover:bg-muted"
            >
              <BrainCircuit size={17} />
              {t(language, "guidedIdeaGen")}
            </button>
            <button
              onClick={generateIdeas}
              disabled={generating || Boolean(viewingHistoryId)}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-foreground px-4 text-sm font-medium text-background disabled:opacity-50"
            >
              {generating ? <Loader2 size={17} className="animate-spin" /> : <FlaskConical size={17} />}
              {t(language, generating ? "generatingIdeas" : "generateIdea")}
            </button>
          </div>
        </div>
      </section>

      <div className="grid items-start gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <aside className="flex min-w-0 flex-col gap-4">
          <div className="grid grid-cols-2 rounded-lg border border-border bg-card p-1">
            <button onClick={() => setSidebarTab("papers")} className={clsx("rounded-md px-3 py-2 text-xs", sidebarTab === "papers" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted")}>{t(language, "paperSelection")}</button>
            <button onClick={() => setSidebarTab("history")} className={clsx("rounded-md px-3 py-2 text-xs", sidebarTab === "history" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted")}>{t(language, "historyRecords")}</button>
          </div>
          {sidebarTab === "papers" ? (
            <>
          <section className="rounded-lg border border-border bg-card p-4">
            <div className="mb-3 text-sm font-medium">{t(language, "ideaMode")}</div>
            <div className="grid gap-2">
              {MODES.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => setMode(id)}
                  disabled={Boolean(viewingHistoryId)}
                  className={clsx(
                    "flex items-center gap-2 rounded-md border px-3 py-2 text-left text-sm transition",
                    mode === id
                      ? "border-amber-400 bg-amber-400/10 text-amber-600 dark:text-amber-300"
                      : "border-border hover:bg-muted"
                  )}
                >
                  <Icon size={16} />
                  {label}
                </button>
              ))}
            </div>

            {mode === "cross_domain" && (
              <div className="mt-3 grid gap-2">
                <input
                  value={domainA}
                  onChange={(e) => setDomainA(e.target.value)}
                  disabled={Boolean(viewingHistoryId)}
                  placeholder={t(language, "ideaDomainA")}
                  className="rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                />
                <input
                  value={domainB}
                  onChange={(e) => setDomainB(e.target.value)}
                  disabled={Boolean(viewingHistoryId)}
                  placeholder={t(language, "ideaDomainB")}
                  className="rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            )}

            <textarea
              value={customPrompt}
              onChange={(e) => setCustomPrompt(e.target.value)}
              disabled={Boolean(viewingHistoryId)}
              placeholder={t(language, "ideaPrefPlaceholder")}
              className="mt-3 h-24 w-full resize-none rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            />

            <div className="mt-3 rounded-md border border-violet-400/30 bg-violet-400/5 p-3">
              <label className="flex items-center gap-2 text-sm font-medium">
                <input
                  type="checkbox"
                  checked={useSocraticContext}
                  onChange={(event) => setUseSocraticContext(event.target.checked)}
                  disabled={Boolean(viewingHistoryId)}
                  className="h-4 w-4 rounded border-border accent-violet-500"
                />
                {t(language, "socraticBridgeTitle")}
              </label>
              <p className="mt-1 text-[11px] text-muted-foreground">
                {t(language, "socraticBridgeHelp")}
              </p>

              {useSocraticContext && (
                <div className="mt-3 space-y-2">
                  {!selectedSessionId && (
                    <select
                      value=""
                      onChange={(event) => void selectSession(event.target.value)}
                      disabled={socraticLoading || availableSessions.length === 0}
                      className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-xs outline-none"
                    >
                      <option value="" disabled>
                        {socraticLoading
                          ? t(language, "loadingHistory")
                          : availableSessions.length > 0
                            ? t(language, "selectSocraticSession")
                            : t(language, "noSocraticHistory")}
                      </option>
                      {availableSessions.map((session) => (
                        <option key={session.id} value={session.id}>
                          {session.title || `Socratic ${formatHistoryDate(session.created_at, language)}`} · {session.turn_count} {t(language, "socraticTurns")} / {session.message_count ?? 0} messages · {formatHistoryDate(session.created_at, language)}
                        </option>
                      ))}
                    </select>
                  )}

                  {selectedSessionId && socraticLoading && (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Loader2 size={13} className="animate-spin" />
                      {t(language, "loadingHistory")}
                    </div>
                  )}

                  {selectedSessionId && !socraticLoading && !selectedSessionSummary && (
                    <div className="rounded-md border border-amber-400/30 bg-amber-400/10 p-2 text-xs text-amber-700 dark:text-amber-300">
                      {t(language, "socraticNoSummary")}
                    </div>
                  )}

                  {selectedSessionSummary && (
                    <div className="space-y-2">
                      {selectedSessionSummary.research_question && (
                        <div className="rounded-md bg-background/70 p-2">
                          <div className="text-[11px] font-medium text-muted-foreground">{t(language, "socraticResearchQuestion")}</div>
                          <div className="mt-0.5 text-xs">{selectedSessionSummary.research_question}</div>
                        </div>
                      )}
                      {selectedSessionSummary.insights && selectedSessionSummary.insights.length > 0 && (
                        <div className="rounded-md bg-background/70 p-2">
                          <div className="text-[11px] font-medium text-muted-foreground">{t(language, "socraticInsights")}</div>
                          <ul className="mt-1 list-inside list-disc space-y-0.5 text-xs">
                            {selectedSessionSummary.insights.slice(0, 3).map((insight, index) => (
                              <li key={`${index}-${insight}`} className="truncate">{insight}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {selectedSessionSummary.methodology && (
                        <div className="rounded-md bg-background/70 p-2">
                          <div className="text-[11px] font-medium text-muted-foreground">{t(language, "socraticMethodology")}</div>
                          <div className="mt-0.5 line-clamp-3 text-xs">{selectedSessionSummary.methodology}</div>
                        </div>
                      )}
                      <label className="block">
                        <span className="text-[11px] font-medium text-muted-foreground">{t(language, "socraticContextPrompt")}</span>
                        <textarea
                          value={socraticContextDraft}
                          onChange={(event) => setSocraticContextDraft(event.target.value)}
                          rows={8}
                          className="mt-1 w-full resize-y rounded-md border border-input bg-background px-2 py-1.5 text-xs outline-none focus:ring-2 focus:ring-ring"
                        />
                      </label>
                    </div>
                  )}

                  {selectedSessionId && !socraticLoading && (
                    <button
                      type="button"
                      onClick={clearSelection}
                      className="text-xs text-violet-600 hover:text-violet-500 dark:text-violet-400"
                    >
                      {t(language, "changeSocraticSession")}
                    </button>
                  )}
                  {socraticError && <div className="text-xs text-destructive">{socraticError}</div>}
                </div>
              )}
            </div>
          </section>

          <section className="flex max-h-[680px] flex-col overflow-hidden rounded-lg border border-border bg-card">
            <div className="border-b border-border p-3">
              <div className="mb-2 flex items-center justify-between text-sm font-medium">
                {t(language, "selectContextPapers")}
                <span className="text-xs text-muted-foreground">{selectedIds.size} {t(language, "selectedCount")}</span>
              </div>
              <div className="relative">
                <Search
                  size={15}
                  className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground"
                />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder={t(language, "filterPapers")}
                  className="h-9 w-full rounded-md border border-input bg-background pl-8 pr-3 text-sm outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            </div>
            <div className="min-h-0 flex-1 overflow-auto p-2">
              {filteredPapers.map((paper) => {
                const selected = selectedIds.has(paper.id);
                return (
                  <button
                    key={paper.id}
                    onClick={() => togglePaper(paper.id)}
                    disabled={Boolean(viewingHistoryId)}
                    className={clsx(
                      "mb-2 flex w-full items-start gap-2 rounded-md border p-3 text-left transition",
                      selected ? "border-amber-400 bg-amber-400/10" : "border-border hover:bg-muted"
                    )}
                  >
                    <span
                      className={clsx(
                        "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border",
                        selected ? "border-amber-400 bg-amber-400 text-slate-950" : "border-border"
                      )}
                    >
                      {selected && <Check size={12} />}
                    </span>
                    <span className="min-w-0">
                      <span className="line-clamp-2 text-xs font-medium">{paper.title}</span>
                      <span className="mt-1 block text-[11px] text-muted-foreground">
                        {paper.year || "N/A"} · {paper.venue || "N/A"}
                      </span>
                    </span>
                  </button>
                );
              })}
              {filteredPapers.length === 0 && (
                <div className="py-8 text-center text-sm text-muted-foreground">
                  {t(language, "noPapersForIdea")}
                </div>
              )}
            </div>
          </section>
            </>
          ) : (
            <section className="flex max-h-[680px] flex-col overflow-hidden rounded-lg border border-border bg-card">
              <div className="flex items-center justify-between border-b border-border px-4 py-3">
                <div className="flex items-center gap-2 text-sm font-medium"><History size={15} />{t(language, "ideaHistory")}</div>
                <button onClick={startNewIdea} className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"><Plus size={13} />{t(language, "newIdea")}</button>
              </div>
              <div className="min-h-0 flex-1 overflow-auto p-2">
                {historyLoading && <div className="p-4 text-center text-xs text-muted-foreground">{t(language, "loadingHistory")}</div>}
                {!historyLoading && historyList.length === 0 && <div className="p-6 text-center text-xs text-muted-foreground">{t(language, "noHistoryRecords")}</div>}
                {historyList.map((item) => (
                  <div key={item.id} className={clsx("mb-2 flex items-start gap-2 rounded-md border p-3", viewingHistoryId === item.id ? "border-amber-400 bg-amber-400/10" : "border-border")}>
                    <button onClick={() => void openIdeaHistory(item.id)} className="min-w-0 flex-1 text-left">
                      <div className="truncate text-sm font-medium">{item.title}</div>
                      <div className="mt-1 text-[11px] text-muted-foreground">{item.mode} · {formatHistoryDate(item.created_at, language)}</div>
                    </button>
                    <button onClick={() => void deleteIdeaHistory(item.id)} className="rounded p-1 text-muted-foreground hover:text-destructive"><Trash2 size={14} /></button>
                  </div>
                ))}
              </div>
            </section>
          )}
        </aside>

        <section className="overflow-hidden rounded-lg border border-border bg-card">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <div className="text-sm font-medium">{t(language, "ideaGenResult")}{viewingHistoryId ? ` · ${t(language, "historyReadonly")}` : ""}</div>
            <div className="flex items-center gap-3">
              {content && !viewingHistoryId && (
                <button onClick={() => void saveIdeaHistory()} disabled={savingHistory || historySaved} className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1.5 text-xs hover:bg-muted disabled:opacity-50">
                  {savingHistory ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
                  {historySaved ? t(language, "savedToHistory") : t(language, "saveToHistory")}
                </button>
              )}
              {viewingHistoryId && <button onClick={startNewIdea} className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1.5 text-xs hover:bg-muted"><Plus size={13} />{t(language, "newIdea")}</button>}
              <div className="text-xs text-muted-foreground">
                {phase === "evaluating" ? t(language, "evaluating") : `${ideaCards.length || 0} ${t(language, "ideas")}`}
              </div>
            </div>
          </div>
          <div className="p-4">
            {streamStatus && (
              <div className="mb-3 rounded-md bg-muted/40 p-2 text-xs text-muted-foreground">
                {streamStatus}
              </div>
            )}
            {!content && !generating && (
              <div className="flex h-full items-center justify-center text-center text-sm text-muted-foreground">
                {t(language, "generateIdeaHint")}
              </div>
            )}

            {ideaCards.length > 0 ? (
              <div className="grid gap-4">
                {ideaCards.map((idea) => {
                  const evaluation = findEvaluation(evaluations, idea.title);
                  return (
                    <article key={idea.title} className="rounded-lg border border-border bg-background p-4">
                      <h3 className="text-base font-semibold">{idea.title}</h3>
                      <div
                        className="mt-3 text-sm leading-6 text-muted-foreground"
                        dangerouslySetInnerHTML={{ __html: renderMarkdown(idea.body) }}
                      />
                      {evaluation ? (
                        <EvaluationView evaluation={evaluation} />
                      ) : phase === "evaluating" ? (
                        <div className="mt-4 inline-flex items-center gap-2 rounded-md bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
                          <Loader2 size={13} className="animate-spin" />
                          {t(language, "waitingEvaluation")}
                        </div>
                      ) : null}
                    </article>
                  );
                })}
              </div>
            ) : (
              content && (
                <div
                  className="text-sm leading-6"
                  dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
                />
              )
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

function EvaluationView({ evaluation }: { evaluation: Evaluation }) {
  return (
    <div className="mt-4 rounded-md border border-border bg-muted/30 p-3 text-sm">
      <div className="grid grid-cols-3 gap-2 text-xs">
        <Score label="Novelty" value={evaluation.novelty} />
        <Score label="Feasible" value={evaluation.feasibility} />
        <Score label="Cost" value={evaluation.cost} />
      </div>
      <div
        className="mt-3 text-xs leading-5 text-muted-foreground"
        dangerouslySetInnerHTML={{ __html: renderMarkdown(evaluation.reasoning || evaluation.report || "") }}
      />
    </div>
  );
}

function Score({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded bg-background px-2 py-1">
      <div className="text-muted-foreground">{label}</div>
      <div className="font-semibold">{value}</div>
    </div>
  );
}

function parseIdeaCards(markdown: string) {
  const sections = markdown
    .split(/\n(?=##\s+)/g)
    .map((section) => section.trim())
    .filter(Boolean);

  return sections.map((section, index) => {
    const match = section.match(/^##\s*(.+)$/m);
    const title = match?.[1]?.trim() || `Idea ${index + 1}`;
    const body = section.replace(/^##\s*.+$/m, "").trim();
    return { title, body };
  });
}

function findEvaluation(evaluations: Record<string, Evaluation>, title: string) {
  if (evaluations[title]) return evaluations[title];
  const normalizedTitle = normalizeTitle(title);
  return Object.values(evaluations).find((item) => normalizeTitle(item.idea_title) === normalizedTitle);
}

function normalizeTitle(title: string) {
  return title
    .replace(/^idea\s*\d+\s*[:：-]\s*/i, "")
    .trim()
    .toLowerCase();
}

function renderMarkdown(text: string): string {
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  return escaped
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/^# (.+)$/gm, "<h1>$1</h1>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/^- (.+)$/gm, "<li>$1</li>")
    .replace(/(<li>.*<\/li>\n?)+/g, "<ul>$&</ul>")
    .replace(/`(.+?)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br/>");
}

function formatHistoryDate(value: string, language: "en" | "zh") {
  if (!value) return "-";
  return new Date(value).toLocaleString(language === "zh" ? "zh-CN" : "en", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
