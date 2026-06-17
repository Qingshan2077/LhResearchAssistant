import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, BrainCircuit, CheckCircle2, Lightbulb, Loader2, Send, Square, Target } from "lucide-react";
import clsx from "clsx";
import { useNavigate } from "react-router-dom";
import { t } from "../i18n";
import { useSettingsStore } from "../stores/settingsStore";
import { useSocraticStore } from "../stores/socraticStore";

const LAYERS = [
  "Problem Framing",
  "Methodology",
  "Evidence",
  "Critical Check",
  "Significance",
];

const SIGNALS = [
  ["s1", "Thesis Clarity"],
  ["s2", "Counterargument"],
  ["s3", "Method Rationale"],
  ["s4", "Scope Stability"],
  ["s5", "Self Calibration"],
] as const;

export default function IdeaSocraticPage() {
  const navigate = useNavigate();
  const language = useSettingsStore((s) => s.language);
  const {
    sessionId,
    messages,
    currentLayer,
    layerName,
    insights,
    convergence,
    turnCount,
    isActive,
    connecting,
    error,
    summary,
    createSession,
    sendMessage,
    getSummary,
    closeSession,
  } = useSocraticStore();
  const [draft, setDraft] = useState("");
  const [initial, setInitial] = useState("");
  const [summaryLoading, setSummaryLoading] = useState(false);

  useEffect(() => {
    return () => closeSession();
  }, [closeSession]);

  const activeSignals = useMemo(
    () => Object.values(convergence || {}).filter(Boolean).length,
    [convergence]
  );

  const start = async () => {
    await createSession("default", initial);
    setInitial("");
  };

  const submit = async () => {
    if (!draft.trim()) return;
    const text = draft;
    setDraft("");
    await sendMessage(text);
  };

  const loadSummary = async () => {
    setSummaryLoading(true);
    try {
      await getSummary();
    } finally {
      setSummaryLoading(false);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-5">
      <section className="rounded-lg border border-border bg-card p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex min-w-0 items-center gap-3">
            <button onClick={() => navigate("/ideas")} className="rounded-md p-2 hover:bg-muted">
              <ArrowLeft size={18} />
            </button>
            <div>
              <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-amber-500">
                <BrainCircuit size={14} />
                Socratic Mentor
              </div>
              <h1 className="mt-1 text-2xl font-semibold">引导式 Idea 生成</h1>
            </div>
          </div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>{sessionId ? (isActive ? "探索中" : "已结束") : "未开始"}</span>
            <span>·</span>
            <span>{turnCount} turns</span>
            <span>·</span>
            <span>{activeSignals}/5 signals</span>
          </div>
        </div>

        <div className="mt-5 grid gap-2 md:grid-cols-5">
          {LAYERS.map((label, index) => {
            const layer = index + 1;
            return (
              <div
                key={label}
                className={clsx(
                  "rounded-md border p-3 text-xs",
                  currentLayer === layer
                    ? "border-amber-400 bg-amber-400/10 text-amber-700 dark:text-amber-300"
                    : currentLayer > layer
                      ? "border-emerald-400 bg-emerald-400/10 text-emerald-700 dark:text-emerald-300"
                      : "border-border bg-background text-muted-foreground"
                )}
              >
                <div className="font-semibold">{layer}/5</div>
                <div className="mt-1 truncate">{label}</div>
              </div>
            );
          })}
        </div>
      </section>

      {!sessionId ? (
        <section className="rounded-lg border border-border bg-card p-5">
          <div className="mb-3 text-sm font-medium">{t(language, "socraticPrompt")}</div>
          <textarea
            value={initial}
            onChange={(event) => setInitial(event.target.value)}
            placeholder={t(language, "socraticPlaceholder")}
            className="h-36 w-full resize-none rounded-md border border-input bg-background p-3 text-sm leading-6 outline-none focus:ring-2 focus:ring-ring"
          />
          <button
            onClick={start}
            disabled={connecting}
            className="mt-3 inline-flex h-10 items-center gap-2 rounded-md bg-primary px-4 text-sm text-primary-foreground disabled:opacity-50"
          >
            {connecting ? <Loader2 size={16} className="animate-spin" /> : <Lightbulb size={16} />}
            开始引导
          </button>
        </section>
      ) : (
        <div className="grid min-h-0 flex-1 gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <section className="flex min-h-0 flex-col rounded-lg border border-border bg-card">
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <div className="text-sm font-medium">
                Layer {currentLayer}: {layerName}
              </div>
              <button
                onClick={loadSummary}
                disabled={summaryLoading}
                className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-xs hover:bg-muted disabled:opacity-50"
              >
                {summaryLoading ? <Loader2 size={13} className="animate-spin" /> : <Target size={13} />}
                生成 Summary
              </button>
            </div>

            <div className="min-h-0 flex-1 overflow-auto p-4">
              <div className="grid gap-3">
                {messages.map((message, index) => (
                  <div
                    key={index}
                    className={clsx(
                      "max-w-[86%] rounded-lg border p-3 text-sm leading-6",
                      message.role === "user"
                        ? "ml-auto border-amber-400 bg-amber-400/10"
                        : "mr-auto border-border bg-background"
                    )}
                  >
                    {message.content}
                  </div>
                ))}
              </div>
              {error && <div className="mt-3 rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}
            </div>

            <div className="border-t border-border p-3">
              <div className="flex gap-2">
                <textarea
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) submit();
                  }}
                  placeholder={t(language, "socraticAnswerPlaceholder")}
                  className="h-20 min-w-0 flex-1 resize-none rounded-md border border-input bg-background p-3 text-sm outline-none focus:ring-2 focus:ring-ring"
                />
                <button
                  onClick={submit}
                  disabled={!draft.trim() || !isActive}
                  className="inline-flex w-12 items-center justify-center rounded-md bg-primary text-primary-foreground disabled:opacity-50"
                >
                  <Send size={17} />
                </button>
              </div>
            </div>
          </section>

          <aside className="flex min-h-0 flex-col gap-4 overflow-hidden">
            <section className="rounded-lg border border-border bg-card p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
                <CheckCircle2 size={16} className="text-emerald-500" />
                Convergence
              </div>
              <div className="grid gap-2">
                {SIGNALS.map(([key, label]) => (
                  <div key={key} className="flex items-center justify-between rounded-md bg-muted/40 px-3 py-2 text-xs">
                    <span>{label}</span>
                    <span className={convergence?.[key] ? "text-emerald-500" : "text-muted-foreground"}>
                      {convergence?.[key] ? "active" : "pending"}
                    </span>
                  </div>
                ))}
              </div>
            </section>

            <section className="min-h-0 flex-1 overflow-auto rounded-lg border border-border bg-card p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
                <Lightbulb size={16} className="text-amber-500" />
                INSIGHT
              </div>
              {insights.length === 0 ? (
                <div className="rounded-md border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
                  {t(language, "noInsight")}
                </div>
              ) : (
                <div className="grid gap-2">
                  {insights.map((item, index) => (
                    <div key={index} className="rounded-md bg-amber-400/10 p-2 text-xs leading-5">
                      {item}
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="max-h-[42%] overflow-auto rounded-lg border border-border bg-card p-4">
              <div className="mb-3 flex items-center justify-between">
                <div className="text-sm font-semibold">Research Plan</div>
                <button onClick={closeSession} className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
                  <Square size={12} />
                  结束
                </button>
              </div>
              {summary ? (
                <div className="grid gap-2 text-xs leading-5">
                  <SummaryItem label="RQ" value={summary.research_question} />
                  <SummaryItem label="Method" value={summary.methodology} />
                  <SummaryItem label="Evidence" value={summary.evidence_plan} />
                  <SummaryItem label="Significance" value={summary.significance} />
                </div>
              ) : (
                <div className="text-xs text-muted-foreground">{t(language, "socraticSummaryHint")}</div>
              )}
            </section>
          </aside>
        </div>
      )}
    </div>
  );
}

function SummaryItem({ label, value }: { label: string; value: unknown }) {
  if (!value) return null;
  return (
    <div className="rounded-md bg-muted/40 p-2">
      <div className="mb-1 text-muted-foreground">{label}</div>
      <div>{String(value)}</div>
    </div>
  );
}
