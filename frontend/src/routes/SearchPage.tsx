import { useCallback, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  BookOpenCheck,
  Check,
  Database,
  ExternalLink,
  FileText,
  Layers,
  Loader2,
  MessageSquare,
  Search,
  Sparkles,
  Table2,
} from "lucide-react";
import clsx from "clsx";
import { t } from "../i18n";
import { api, type ComparisonTable, type Paper } from "../lib/api";
import { usePaperStore } from "../stores/paperStore";
import { useSettingsStore } from "../stores/settingsStore";

const SOURCE_OPTIONS = [
  { id: "arxiv", label: "arXiv" },
  { id: "semantic_scholar", label: "Semantic Scholar" },
  { id: "dblp", label: "DBLP" },
];

export default function SearchPage() {
  const language = useSettingsStore((s) => s.language);
  const { papers, loading, error, search, searchQuery, totalCount, sourceBreakdown, sourceErrors } =
    usePaperStore();
  const [query, setQuery] = useState("");
  const [sources, setSources] = useState<string[]>(SOURCE_OPTIONS.map((s) => s.id));
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [generatingReview, setGeneratingReview] = useState(false);
  const [reviewContent, setReviewContent] = useState("");
  const [askQuestion, setAskQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [askAnswer, setAskAnswer] = useState("");
  const [askStatus, setAskStatus] = useState("");
  const [comparing, setComparing] = useState(false);
  const [comparisonTable, setComparisonTable] = useState<ComparisonTable | null>(null);
  const reviewRef = useRef<HTMLDivElement>(null);

  const selectedPapers = useMemo(
    () => papers.filter((paper) => selectedIds.has(paper.id)),
    [papers, selectedIds]
  );
  const hasSearched = Boolean(searchQuery);

  const handleSearch = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      const activeSources = sources.length ? sources : SOURCE_OPTIONS.map((source) => source.id);
      const trimmed = query.trim();
      if (!trimmed) return;

      setSelectedIds(new Set());
      setReviewContent("");
      setAskAnswer("");
      setAskStatus("");
      setComparisonTable(null);
      await search(trimmed, activeSources);
    },
    [query, search, sources]
  );

  const toggleSource = (source: string) => {
    setSources((prev) =>
      prev.includes(source) ? prev.filter((item) => item !== source) : [...prev, source]
    );
  };

  const toggleSelect = (id: string) => {
    setComparisonTable(null);
    setAskStatus("");
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const resolveSelectedLocalPaperIds = async (projectId = "default") => {
    if (selectedPapers.length === 0) return [];

    try {
      await api.post("papers/batch", {
        json: selectedPapers.map((paper) => toPaperCreate(paper, projectId)),
      });
    } catch {
      // Existing papers are resolved by fetching the local library below.
    }

    const resp = await api
      .get("papers", { searchParams: { project_id: projectId, page_size: 500 } })
      .json<{ items: Paper[] }>();

    return resp.items
      .filter((paper) => selectedPapers.some((selected) => samePaper(paper, selected)))
      .map((paper) => paper.id);
  };

  const askPapers = async () => {
    if (selectedIds.size === 0 || !askQuestion.trim()) return;
    setAsking(true);
    setAskAnswer("");
    setAskStatus(t(language, "preparingSelectedPapers"));

    try {
      const paperIds = await resolveSelectedLocalPaperIds();
      if (paperIds.length === 0) {
        setAskStatus(t(language, "noSelectedResolved"));
        return;
      }

      const response = await fetch("/api/v1/papers/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paper_ids: paperIds, question: askQuestion, top_k: 8 }),
      });

      if (!response.ok) throw new Error(`${response.status}`);

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
        for (const rawLine of lines) {
          const line = rawLine.trimEnd();
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === "chunk") setAskAnswer((prev) => prev + data.content);
            if (data.type === "status") setAskStatus(String(data.message || ""));
            if (data.type === "error") setAskStatus(String(data.message || t(language, "askFailed")));
            if (data.type === "done") setAskStatus("");
          } catch {
            // Ignore malformed SSE rows.
          }
        }
      }
    } catch (err) {
      setAskStatus(`${t(language, "askFailed")} ${err}`);
    } finally {
      setAsking(false);
    }
  };

  const generateComparison = async () => {
    if (selectedIds.size < 2) return;
    setComparing(true);
    setComparisonTable(null);
    try {
      const paperIds = await resolveSelectedLocalPaperIds();
      if (paperIds.length < 2) return;
      const resp = await api
        .post("papers/compare", {
          json: {
            paper_ids: paperIds,
            dimensions: ["method", "dataset", "metric", "code_available", "key_finding"],
          },
        })
        .json<ComparisonTable>();
      setComparisonTable(resp);
    } finally {
      setComparing(false);
    }
  };

  const handleGenerateReview = async () => {
    if (selectedIds.size === 0) return;
    setGeneratingReview(true);
    setReviewContent("");

    const projectId = "default";
    try {
      await api.post("papers/batch", {
        json: selectedPapers.map((paper) => toPaperCreate(paper, projectId)),
      });
    } catch {
      // Papers may already exist locally. Continue and resolve imported IDs below.
    }

    try {
      const resp = await api
        .get("papers", { searchParams: { project_id: projectId, page_size: 500 } })
        .json<{ items: Paper[] }>();

      const importedIds = resp.items
        .filter((paper) => selectedPapers.some((selected) => selected.title === paper.title))
        .map((paper) => paper.id);

      const response = await fetch("/api/v1/search/generate-review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: projectId,
          paper_ids: importedIds,
          focus: "method_comparison",
          language,
        }),
      });

      if (!response.ok) throw new Error(`${response.status}`);

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
            if (data.type === "chunk") setReviewContent((prev) => prev + data.content);
            if (data.type === "done") setGeneratingReview(false);
            if (data.type === "error") {
              setReviewContent((prev) => `${prev}\n\n[${data.message}]`);
              setGeneratingReview(false);
            }
          } catch {
            // Ignore malformed SSE rows.
          }
        }
      }
    } catch (err) {
      setReviewContent(`${t(language, "reviewFailed")}: ${err}`);
    } finally {
      setGeneratingReview(false);
    }
  };

  const handleImport = async () => {
    if (selectedIds.size === 0) return;
    try {
      await api.post("papers/batch", {
        json: selectedPapers.map((paper) => toPaperCreate(paper, "default")),
      });
      setSelectedIds(new Set());
    } catch (err) {
      console.error("Import failed", err);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-5">
      <section className="relative overflow-hidden rounded-lg border border-border bg-card p-5 shadow-sm">
        <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-cyan-400 via-violet-500 to-amber-300" />
        <div className="flex flex-col gap-5">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.2em] text-cyan-500">
                <Layers size={14} />
                {t(language, "researchRadar")}
              </div>
              <h1 className="mt-2 text-3xl font-semibold text-foreground">{t(language, "searchTitle")}</h1>
              <p className="mt-1 text-sm text-muted-foreground">{t(language, "searchSubtitle")}</p>
            </div>

            <div className="grid grid-cols-3 overflow-hidden rounded-lg border border-border bg-background/70 text-center text-xs">
              <Metric label={t(language, "metricResults")} value={String(totalCount || papers.length)} />
              <Metric label={t(language, "selected")} value={String(selectedIds.size)} />
              <Metric label={t(language, "sources")} value={String(Object.keys(sourceBreakdown).length || sources.length)} />
            </div>
          </div>

          <form onSubmit={handleSearch} className="flex flex-col gap-3">
            <div className="flex flex-col gap-3 md:flex-row">
              <div className="relative min-w-0 flex-1">
                <Search size={18} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={t(language, "searchPlaceholder")}
                  className="h-12 w-full rounded-lg border border-input bg-background pl-10 pr-4 text-sm text-foreground outline-none transition focus:border-cyan-400 focus:ring-2 focus:ring-cyan-400/25"
                />
              </div>
              <button
                type="submit"
                disabled={loading || !query.trim()}
                className="inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-foreground px-5 text-sm font-medium text-background transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? <Loader2 size={18} className="animate-spin" /> : <Search size={18} />}
                {loading ? t(language, "searching") : t(language, "searchButton")}
              </button>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {SOURCE_OPTIONS.map((source) => {
                const active = sources.includes(source.id);
                const sourceError = sourceErrors[source.id];
                return (
                  <button
                    key={source.id}
                    type="button"
                    onClick={() => toggleSource(source.id)}
                    title={sourceError || source.label}
                    className={clsx(
                      "inline-flex h-8 items-center gap-2 rounded-md border px-3 text-xs font-medium transition",
                      sourceError
                        ? "border-destructive/60 bg-destructive/10 text-destructive"
                        : active
                          ? "border-cyan-400/60 bg-cyan-400/10 text-cyan-600 dark:text-cyan-300"
                          : "border-border bg-background text-muted-foreground hover:text-foreground"
                    )}
                  >
                    {sourceError ? <AlertCircle size={14} /> : active ? <Check size={14} /> : <Database size={14} />}
                    {source.label}
                    {sourceBreakdown[source.id] !== undefined && (
                      <span className="rounded bg-background/80 px-1.5 py-0.5">
                        {sourceBreakdown[source.id]}
                        {sourceError ? " !" : ""}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </form>
        </div>
      </section>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {papers.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card px-4 py-3">
          <div className="text-sm text-muted-foreground">
            {totalCount} {t(language, "selectedSummary")} {selectedIds.size}
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={handleImport}
              disabled={selectedIds.size === 0}
              className="inline-flex h-9 items-center gap-2 rounded-md border border-border bg-background px-3 text-sm font-medium transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Database size={16} />
              {t(language, "importSelected")}
            </button>
            <button
              onClick={handleGenerateReview}
              disabled={selectedIds.size === 0 || generatingReview}
              className="inline-flex h-9 items-center gap-2 rounded-md bg-violet-600 px-3 text-sm font-medium text-white transition hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {generatingReview ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
              {generatingReview ? t(language, "generating") : t(language, "generateReview")}
            </button>
          </div>
        </div>
      )}

      {selectedIds.size > 0 && (
        <section className="overflow-hidden rounded-lg border border-cyan-400/30 bg-card shadow-[0_18px_60px_rgba(14,165,233,0.10)]">
          <div className="border-b border-border bg-gradient-to-r from-cyan-500/10 via-violet-500/10 to-amber-400/10 px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-foreground">{t(language, "selectedWorkspaceTitle")}</div>
                <div className="mt-0.5 text-xs text-muted-foreground">{t(language, "selectedWorkspaceSubtitle")}</div>
              </div>
              <div className="rounded-md border border-border bg-background/70 px-2.5 py-1 text-xs text-muted-foreground">
                {selectedIds.size} {t(language, "selectedCount")}
              </div>
            </div>
          </div>

          <div className="grid gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_auto]">
            <div className="min-w-0">
              <div className="flex flex-col gap-2 md:flex-row">
                <input
                  value={askQuestion}
                  onChange={(e) => setAskQuestion(e.target.value)}
                  placeholder={t(language, "askPlaceholder")}
                  className="h-10 min-w-0 flex-1 rounded-md border border-input bg-background px-3 text-sm outline-none transition focus:border-cyan-400 focus:ring-2 focus:ring-cyan-400/25"
                />
                <button
                  onClick={askPapers}
                  disabled={asking || !askQuestion.trim()}
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-cyan-600 px-4 text-sm font-medium text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {asking ? <Loader2 size={16} className="animate-spin" /> : <MessageSquare size={16} />}
                  {t(language, "ask")}
                </button>
              </div>

              {askStatus && <div className="mt-2 text-xs text-cyan-600 dark:text-cyan-300">{askStatus}</div>}
              {askAnswer && (
                <div className="mt-3 max-h-56 overflow-auto rounded-md border border-border bg-background/70 p-3 text-sm leading-6 text-muted-foreground">
                  <div className="prose prose-sm max-w-none dark:prose-invert" dangerouslySetInnerHTML={{ __html: renderMarkdown(askAnswer) }} />
                </div>
              )}
            </div>

            <div className="flex flex-col gap-2 md:flex-row lg:flex-col">
              <button
                onClick={generateComparison}
                disabled={selectedIds.size < 2 || comparing}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-border bg-background px-4 text-sm font-medium transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
              >
                {comparing ? <Loader2 size={16} className="animate-spin" /> : <Table2 size={16} />}
                {t(language, "compare")}
              </button>
              <div className="text-xs text-muted-foreground">{t(language, "compareRequires")}</div>
            </div>
          </div>

          {comparisonTable && (
            <div className="border-t border-border p-4">
              <PaperComparisonTable data={comparisonTable} language={language} />
            </div>
          )}
        </section>
      )}

      <div className="grid min-h-0 flex-1 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(420px,0.48fr)]">
        <section className="min-h-0 overflow-hidden rounded-lg border border-border bg-card">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <div className="flex items-center gap-2 text-sm font-medium">
              <BookOpenCheck size={17} className="text-cyan-500" />
              {t(language, "searchResultsTitle")}
            </div>
            {hasSearched && <span className="line-clamp-1 text-xs text-muted-foreground">"{searchQuery}"</span>}
          </div>

          <div className="h-full overflow-auto p-3">
            {papers.length === 0 && !loading && (
              <EmptyState
                title={hasSearched ? t(language, "noPapersFound") : t(language, "startSearchTitle")}
                body={hasSearched ? t(language, "noPapersFoundHelp") : t(language, "startSearchHelp")}
              />
            )}

            {loading && (
              <div className="grid gap-3">
                {Array.from({ length: 6 }).map((_, index) => (
                  <div key={index} className="h-28 animate-pulse rounded-lg bg-muted" />
                ))}
              </div>
            )}

            <div className="grid gap-3">
              {papers.map((paper) => {
                const selected = selectedIds.has(paper.id);
                return (
                  <article
                    key={paper.id}
                    onClick={() => toggleSelect(paper.id)}
                    className={clsx(
                      "group cursor-pointer rounded-lg border bg-background p-4 transition",
                      selected
                        ? "border-cyan-400 shadow-[0_0_0_1px_rgba(34,211,238,0.35)]"
                        : "border-border hover:border-cyan-400/50 hover:bg-muted/35"
                    )}
                  >
                    <div className="flex items-start gap-4">
                      <div className={clsx("mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border transition", selected ? "border-cyan-400 bg-cyan-400 text-slate-950" : "border-border text-transparent group-hover:border-cyan-400")}>
                        <Check size={14} />
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded bg-secondary px-2 py-0.5 text-xs text-secondary-foreground">{paper.source || t(language, "unknown")}</span>
                          {paper.year && <span className="text-xs text-muted-foreground">{paper.year}</span>}
                          {paper.citation_count > 0 && (
                            <span className="text-xs text-amber-500">{t(language, "citations")} {paper.citation_count}</span>
                          )}
                          {!paper.is_new && <span className="text-xs text-cyan-500">{t(language, "imported")}</span>}
                        </div>

                        <h3 className="mt-2 line-clamp-2 text-sm font-semibold leading-6 text-foreground">{paper.title}</h3>
                        <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">
                          {paper.authors?.slice(0, 6).join(", ")}
                          {paper.authors && paper.authors.length > 6 ? " et al." : ""}
                        </p>

                        {paper.abstract && <p className="mt-3 line-clamp-2 text-xs leading-5 text-muted-foreground">{paper.abstract}</p>}

                        <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                          <span className="inline-flex items-center gap-1">
                            <FileText size={13} />
                            {paper.venue || "N/A"}
                          </span>
                          {paper.url && (
                            <a
                              href={paper.url}
                              target="_blank"
                              rel="noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="inline-flex items-center gap-1 text-cyan-600 hover:underline dark:text-cyan-300"
                            >
                              <ExternalLink size={13} />
                              {t(language, "originalPaper")}
                            </a>
                          )}
                        </div>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        </section>

        <section className="min-h-0 overflow-hidden rounded-lg border border-border bg-card">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Sparkles size={17} className="text-violet-500" />
              {t(language, "literatureReview")}
            </div>
            {generatingReview && (
              <span className="inline-flex items-center gap-1 text-xs text-violet-500">
                <Loader2 size={13} className="animate-spin" />
                {t(language, "generating")}
              </span>
            )}
          </div>
          <div ref={reviewRef} className="h-full overflow-auto p-4 text-sm leading-6 text-muted-foreground">
            {reviewContent ? (
              <div className="prose prose-sm max-w-none dark:prose-invert" dangerouslySetInnerHTML={{ __html: renderMarkdown(reviewContent) }} />
            ) : (
              <EmptyState title={t(language, "selectPapersReviewTitle")} body={t(language, "selectPapersReviewBody")} />
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-20 border-r border-border px-4 py-2 last:border-r-0">
      <div className="text-lg font-semibold text-foreground">{value}</div>
      <div className="text-[11px] text-muted-foreground">{label}</div>
    </div>
  );
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="flex min-h-56 flex-col items-center justify-center rounded-lg border border-dashed border-border bg-background/60 px-6 text-center">
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-secondary text-secondary-foreground">
        <Search size={18} />
      </div>
      <div className="text-sm font-medium text-foreground">{title}</div>
      <div className="mt-1 text-xs text-muted-foreground">{body}</div>
    </div>
  );
}

function PaperComparisonTable({ data, language }: { data: ComparisonTable; language: "en" | "zh" }) {
  const dimensions = data.table.length > 0 ? Object.keys(data.table[0].values || {}) : [];

  return (
    <div className="min-w-0">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="text-sm font-semibold text-foreground">{t(language, "comparisonMatrix")}</div>
        <div className="text-xs text-muted-foreground">{data.table.length} {t(language, "paperCount")}</div>
      </div>
      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full min-w-[780px] border-collapse text-xs">
          <thead>
            <tr className="bg-muted/60 text-muted-foreground">
              <th className="border-b border-r border-border px-3 py-2 text-left font-medium">{t(language, "tableTitle")}</th>
              <th className="border-b border-r border-border px-3 py-2 text-left font-medium">{t(language, "tableYear")}</th>
              <th className="border-b border-r border-border px-3 py-2 text-left font-medium">{t(language, "tableVenue")}</th>
              {dimensions.map((dimension) => (
                <th key={dimension} className="border-b border-r border-border px-3 py-2 text-left font-medium">
                  {dimension.replace(/_/g, " ")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.table.map((row) => (
              <tr key={row.id} className="align-top hover:bg-muted/30">
                <td className="max-w-[260px] border-r border-border px-3 py-2 font-medium text-foreground">{row.title}</td>
                <td className="border-r border-border px-3 py-2 text-muted-foreground">{row.year || "-"}</td>
                <td className="border-r border-border px-3 py-2 text-muted-foreground">{row.venue || "-"}</td>
                {dimensions.map((dimension) => (
                  <td key={dimension} className="max-w-[240px] border-r border-border px-3 py-2 text-muted-foreground">
                    {row.values?.[dimension] || "-"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.notes && <div className="mt-3 text-xs italic text-muted-foreground">{data.notes}</div>}
    </div>
  );
}

function samePaper(left: Paper, right: Paper) {
  const leftDoi = normalizePaperKey(left.doi);
  const rightDoi = normalizePaperKey(right.doi);
  if (leftDoi && rightDoi && leftDoi === rightDoi) return true;

  const leftArxiv = normalizePaperKey(left.arxiv_id);
  const rightArxiv = normalizePaperKey(right.arxiv_id);
  if (leftArxiv && rightArxiv && leftArxiv === rightArxiv) return true;

  return normalizePaperKey(left.title) === normalizePaperKey(right.title);
}

function normalizePaperKey(value: string | null | undefined) {
  return (value || "").trim().toLowerCase().replace(/\s+/g, " ");
}

function toPaperCreate(paper: Paper, projectId: string) {
  return {
    project_id: projectId,
    title: paper.title,
    authors: paper.authors,
    abstract: paper.abstract,
    year: paper.year,
    venue: paper.venue,
    paper_type: paper.paper_type,
    doi: paper.doi,
    arxiv_id: paper.arxiv_id,
    source: paper.source,
    citation_count: paper.citation_count,
    keywords: paper.keywords,
    url: paper.url,
    pdf_url: paper.pdf_url,
  };
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
    .replace(/^&gt; (.+)$/gm, "<blockquote>$1</blockquote>")
    .replace(/```(\w*)\n([\s\S]*?)```/g, "<pre><code>$2</code></pre>")
    .replace(/`(.+?)`/g, "<code>$1</code>")
    .replace(/\n\n/g, "</p><p>")
    .replace(/\n/g, "<br/>");
}
