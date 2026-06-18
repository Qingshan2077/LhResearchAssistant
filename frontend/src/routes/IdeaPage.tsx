import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  BarChart3,
  BrainCircuit,
  Check,
  FlaskConical,
  GitCompare,
  Lightbulb,
  Loader2,
  Search,
  Sparkles,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import clsx from "clsx";
import { api, apiUrl, type Paper } from "../lib/api";
import { t } from "../i18n";
import { useSettingsStore } from "../stores/settingsStore";

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
  const [search, setSearch] = useState("");
  const [generating, setGenerating] = useState(false);
  const [phase, setPhase] = useState<GenerationPhase>("done");
  const [streamStatus, setStreamStatus] = useState("");
  const [content, setContent] = useState("");
  const [evaluations, setEvaluations] = useState<Record<string, Evaluation>>({});
  const language = useSettingsStore((s) => s.language);

  useEffect(() => {
    api
      .get("papers", { searchParams: { project_id: "default", page_size: 500 } })
      .json<{ items: Paper[] }>()
      .then((resp) => setPapers(resp.items))
      .catch(() => setPapers([]));
  }, []);

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
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(paperId)) next.delete(paperId);
      else next.add(paperId);
      return next;
    });
  };

  const generateIdeas = async () => {
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
          custom_prompt: customPrompt,
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
    <div className="flex h-full min-h-0 flex-col gap-5">
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
              disabled={generating}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-foreground px-4 text-sm font-medium text-background disabled:opacity-50"
            >
              {generating ? <Loader2 size={17} className="animate-spin" /> : <FlaskConical size={17} />}
              {t(language, generating ? "generatingIdeas" : "generateIdea")}
            </button>
          </div>
        </div>
      </section>

      <div className="grid min-h-0 flex-1 gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <aside className="flex min-h-0 flex-col gap-4 overflow-hidden">
          <section className="rounded-lg border border-border bg-card p-4">
            <div className="mb-3 text-sm font-medium">{t(language, "ideaMode")}</div>
            <div className="grid gap-2">
              {MODES.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => setMode(id)}
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
                  placeholder={t(language, "ideaDomainA")}
                  className="rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                />
                <input
                  value={domainB}
                  onChange={(e) => setDomainB(e.target.value)}
                  placeholder={t(language, "ideaDomainB")}
                  className="rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            )}

            <textarea
              value={customPrompt}
              onChange={(e) => setCustomPrompt(e.target.value)}
              placeholder={t(language, "ideaPrefPlaceholder")}
              className="mt-3 h-24 w-full resize-none rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
          </section>

          <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-border bg-card">
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
        </aside>

        <section className="min-h-0 overflow-hidden rounded-lg border border-border bg-card">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <div className="text-sm font-medium">{t(language, "ideaGenResult")}</div>
            <div className="text-xs text-muted-foreground">
              {phase === "evaluating" ? t(language, "evaluating") : `${ideaCards.length || 0} ${t(language, "ideas")}`}
            </div>
          </div>
          <div className="h-full overflow-auto p-4">
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
