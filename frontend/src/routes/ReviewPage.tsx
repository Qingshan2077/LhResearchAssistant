import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BookMarked,
  CheckCircle2,
  ClipboardCheck,
  FileCheck2,
  Loader2,
  Mail,
  MessageSquareReply,
  SearchCheck,
  ShieldCheck,
  Sparkles,
  Star,
  XCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import clsx from "clsx";
import { api } from "../lib/api";

type WritingProject = {
  id: string;
  project_id: string;
  title: string;
  target_venue: string;
  language: string;
  template: string;
  latex_project_path: string;
  outline: Array<{ title: string; goal?: string }>;
  files: Array<{ path: string; type: "file" | "directory"; size: number }>;
  created_at: string;
};

type VenueResult = {
  name: string;
  full_name: string;
  field: string;
  ccf_rank: string;
  acceptance_rate: number;
  match_score: number;
  match_reason: string;
  avg_review_weeks: number;
  paper_type: string;
};

type FormatIssue = {
  severity: "error" | "warning" | "info";
  rule: string;
  message: string;
  line: number;
};

type FormatResult = {
  passed: boolean;
  issues: FormatIssue[];
  total_pages_estimate: number;
};

type ReviewCard = {
  reviewer: number;
  role: string;
  summary: string;
  strengths: string[];
  weaknesses: string[];
  questions: string[];
  overall_score: number;
  confidence: number;
};

type MetaReview = {
  decision: string;
  average_score: number;
  summary: string;
  action_items: string[];
};

type FailureMode = {
  mode: number;
  name: string;
  status: "clear" | "suspected" | "insufficient_evidence";
  reasoning: string;
  action_required: boolean;
};

type FailureChecklistResult = {
  modes: FailureMode[];
  blocking: boolean;
  summary: string;
};

type TabKey = "venue" | "format" | "simulate" | "letters" | "checklist";

const FORMAT_VENUES = [
  { value: "neurips_2024", label: "NeurIPS 2024" },
  { value: "acl", label: "ACL" },
  { value: "ieee_trans", label: "IEEE Transactions" },
  { value: "ctex_article", label: "CTeX Article" },
];

const TABS: Array<{ key: TabKey; label: string; icon: LucideIcon }> = [
  { key: "venue", label: "选刊推荐", icon: SearchCheck },
  { key: "format", label: "格式检查", icon: FileCheck2 },
  { key: "simulate", label: "模拟审稿", icon: ClipboardCheck },
  { key: "letters", label: "信件生成", icon: Mail },
  { key: "checklist", label: "失败检查", icon: AlertTriangle },
];

export default function ReviewPage() {
  const [projects, setProjects] = useState<WritingProject[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("venue");
  const [venue, setVenue] = useState("NeurIPS");
  const [formatVenue, setFormatVenue] = useState("neurips_2024");
  const [reviewerCount, setReviewerCount] = useState(3);

  const [venueForm, setVenueForm] = useState({
    title: "",
    abstract: "",
    keywords: "",
    method: "",
  });
  const [venueResults, setVenueResults] = useState<VenueResult[]>([]);
  const [recommending, setRecommending] = useState(false);

  const [formatResult, setFormatResult] = useState<FormatResult | null>(null);
  const [checkingFormat, setCheckingFormat] = useState(false);

  const [reviewers, setReviewers] = useState<ReviewCard[]>([]);
  const [metaReview, setMetaReview] = useState<MetaReview | null>(null);
  const [reviewLog, setReviewLog] = useState("");
  const [simulating, setSimulating] = useState(false);

  const [coverNotes, setCoverNotes] = useState("");
  const [coverLetter, setCoverLetter] = useState("");
  const [reviewText, setReviewText] = useState("");
  const [rebuttal, setRebuttal] = useState("");
  const [letterBusy, setLetterBusy] = useState<"cover" | "rebuttal" | null>(null);
  const [checklistText, setChecklistText] = useState("");
  const [checklistResult, setChecklistResult] = useState<FailureChecklistResult | null>(null);
  const [checklistBusy, setChecklistBusy] = useState(false);

  useEffect(() => {
    api
      .get("writing/projects", { searchParams: { project_id: "default" } })
      .json<{ items: WritingProject[] }>()
      .then((resp) => {
        setProjects(resp.items);
        if (resp.items[0]) setSelectedId(resp.items[0].id);
      })
      .catch(() => setProjects([]));
  }, []);

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedId) || projects[0] || null,
    [projects, selectedId]
  );

  useEffect(() => {
    if (!selectedProject) return;
    setVenue(selectedProject.target_venue || selectedProject.template || "NeurIPS");
    setFormatVenue(selectedProject.template || "neurips_2024");
    setVenueForm((prev) => ({
      ...prev,
      title: prev.title || selectedProject.title,
    }));
  }, [selectedProject?.id]);

  const recommendVenues = async () => {
    const title = venueForm.title.trim() || selectedProject?.title || "";
    if (!title) return;
    setRecommending(true);
    try {
      const resp = await api
        .post("review/recommend-venues", {
          json: {
            title,
            abstract: venueForm.abstract,
            keywords: venueForm.keywords
              .split(/[,，\n]/)
              .map((item) => item.trim())
              .filter(Boolean),
            method_description: venueForm.method,
          },
        })
        .json<{ venues: VenueResult[] }>();
      setVenueResults(resp.venues);
      if (resp.venues[0]) setVenue(resp.venues[0].name);
    } finally {
      setRecommending(false);
    }
  };

  const checkFormat = async () => {
    if (!selectedProject) return;
    setCheckingFormat(true);
    try {
      const resp = await api
        .post("review/check-format", {
          json: {
            writing_project_id: selectedProject.id,
            target_venue: formatVenue,
          },
        })
        .json<FormatResult>();
      setFormatResult(resp);
    } finally {
      setCheckingFormat(false);
    }
  };

  const simulateReview = async () => {
    if (!selectedProject) return;
    setSimulating(true);
    setReviewers([]);
    setMetaReview(null);
    setReviewLog("");
    try {
      const response = await fetch("/api/v1/review/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          writing_project_id: selectedProject.id,
          venue,
          reviewer_count: reviewerCount,
        }),
      });
      await readSse(response, (data) => {
        if (data.type === "status") {
          setReviewLog(String(data.message || ""));
        }
        if (data.type === "reviewer_start") {
          setReviewLog(`Reviewer ${String(data.reviewer || "")} (${String(data.role || "")}) is reading the manuscript...`);
        }
        if (data.type === "reviewer" && data.review) {
          setReviewers((prev) => [...prev, data.review as ReviewCard]);
        }
        if (data.type === "meta_review" && data.meta_review) {
          setMetaReview(data.meta_review as MetaReview);
        }
        if (data.type === "error") {
          setReviewLog(String(data.message || "Review simulation failed."));
        }
      });
    } finally {
      setSimulating(false);
    }
  };

  const generateCoverLetter = async () => {
    if (!selectedProject) return;
    setLetterBusy("cover");
    try {
      const resp = await api
        .post("review/generate-cover-letter", {
          json: {
            writing_project_id: selectedProject.id,
            venue,
            editor_name: "Editor",
            additional_notes: coverNotes,
          },
        })
        .json<{ content: string }>();
      setCoverLetter(resp.content);
    } finally {
      setLetterBusy(null);
    }
  };

  const generateRebuttal = async () => {
    if (!selectedProject || !reviewText.trim()) return;
    setLetterBusy("rebuttal");
    try {
      const resp = await api
        .post("review/generate-rebuttal", {
          json: {
            writing_project_id: selectedProject.id,
            review_text: reviewText,
            response_style: "detailed",
          },
        })
        .json<{ content: string }>();
      setRebuttal(resp.content);
    } finally {
      setLetterBusy(null);
    }
  };

  const runChecklist = async () => {
    if (!selectedProject && !checklistText.trim()) return;
    setChecklistBusy(true);
    try {
      const resp = await api
        .post("review/run-failure-checklist", {
          json: {
            writing_project_id: selectedProject?.id || "",
            text: checklistText,
          },
        })
        .json<FailureChecklistResult>();
      setChecklistResult(resp);
    } finally {
      setChecklistBusy(false);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-5">
      <section className="overflow-hidden rounded-lg border border-border bg-card">
        <div className="grid gap-0 xl:grid-cols-[minmax(0,1fr)_420px]">
          <div className="relative p-5">
            <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-cyan-400 via-emerald-400 to-amber-300" />
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-cyan-500">
              <ShieldCheck size={14} />
              Review Desk
            </div>
            <h1 className="mt-2 text-3xl font-semibold">审稿与选刊</h1>
            <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_180px_120px]">
              <select
                value={selectedProject?.id || ""}
                onChange={(event) => setSelectedId(event.target.value)}
                className="h-10 min-w-0 rounded-md border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              >
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.title}
                  </option>
                ))}
              </select>
              <input
                value={venue}
                onChange={(event) => setVenue(event.target.value)}
                placeholder="目标会议/期刊"
                className="h-10 rounded-md border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              />
              <select
                value={reviewerCount}
                onChange={(event) => setReviewerCount(Number(event.target.value))}
                className="h-10 rounded-md border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              >
                {[1, 2, 3, 4].map((count) => (
                  <option key={count} value={count}>
                    {count} 位审稿人
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-3 border-t border-border xl:border-l xl:border-t-0">
            <MetricTile label="项目" value={projects.length.toString()} icon={BookMarked} tone="cyan" />
            <MetricTile label="格式" value={formatResult ? (formatResult.passed ? "PASS" : "FIX") : "--"} icon={FileCheck2} tone="emerald" />
            <MetricTile label="评分" value={metaReview ? metaReview.average_score.toFixed(1) : "--"} icon={Star} tone="amber" />
          </div>
        </div>
      </section>

      <div className="flex flex-wrap gap-2">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={clsx(
              "inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm transition",
              activeTab === key
                ? "border-cyan-400 bg-cyan-400/10 text-cyan-600 dark:text-cyan-300"
                : "border-border bg-card text-muted-foreground hover:bg-muted"
            )}
          >
            <Icon size={16} />
            {label}
          </button>
        ))}
      </div>

      <div className="min-h-0 flex-1 overflow-hidden">
        {activeTab === "venue" && (
          <div className="grid h-full min-h-0 gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
            <section className="rounded-lg border border-border bg-card p-4">
              <SectionTitle icon={SearchCheck} title="投稿匹配" />
              <div className="mt-4 grid gap-3">
                <input
                  value={venueForm.title}
                  onChange={(event) => setVenueForm((prev) => ({ ...prev, title: event.target.value }))}
                  placeholder="论文标题"
                  className="h-10 rounded-md border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
                />
                <textarea
                  value={venueForm.abstract}
                  onChange={(event) => setVenueForm((prev) => ({ ...prev, abstract: event.target.value }))}
                  placeholder="摘要"
                  className="h-36 resize-none rounded-md border border-input bg-background p-3 text-sm leading-6 outline-none focus:ring-2 focus:ring-ring"
                />
                <input
                  value={venueForm.keywords}
                  onChange={(event) => setVenueForm((prev) => ({ ...prev, keywords: event.target.value }))}
                  placeholder="关键词，用逗号分隔"
                  className="h-10 rounded-md border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
                />
                <textarea
                  value={venueForm.method}
                  onChange={(event) => setVenueForm((prev) => ({ ...prev, method: event.target.value }))}
                  placeholder="方法描述"
                  className="h-24 resize-none rounded-md border border-input bg-background p-3 text-sm leading-6 outline-none focus:ring-2 focus:ring-ring"
                />
                <button
                  onClick={recommendVenues}
                  disabled={recommending || (!venueForm.title.trim() && !selectedProject?.title)}
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground disabled:opacity-50"
                >
                  {recommending ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
                  推荐选刊
                </button>
              </div>
            </section>

            <section className="min-h-0 overflow-auto rounded-lg border border-border bg-card p-4">
              <SectionTitle icon={BookMarked} title="推荐结果" />
              <div className="mt-4 grid gap-3">
                {venueResults.length === 0 ? (
                  <EmptyState text="输入标题、摘要和方法后生成推荐列表。" />
                ) : (
                  venueResults.map((item, index) => (
                    <VenueCard key={item.name} item={item} rank={index + 1} onUse={() => setVenue(item.name)} />
                  ))
                )}
              </div>
            </section>
          </div>
        )}

        {activeTab === "format" && (
          <section className="flex h-full min-h-0 flex-col rounded-lg border border-border bg-card">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-4">
              <SectionTitle icon={FileCheck2} title="LaTeX 格式检查" />
              <div className="flex gap-2">
                <select
                  value={formatVenue}
                  onChange={(event) => setFormatVenue(event.target.value)}
                  className="h-10 rounded-md border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
                >
                  {FORMAT_VENUES.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
                <button
                  onClick={checkFormat}
                  disabled={checkingFormat || !selectedProject}
                  className="inline-flex h-10 items-center gap-2 rounded-md bg-primary px-3 text-sm text-primary-foreground disabled:opacity-50"
                >
                  {checkingFormat ? <Loader2 size={16} className="animate-spin" /> : <FileCheck2 size={16} />}
                  开始检查
                </button>
              </div>
            </div>
            <div className="min-h-0 flex-1 overflow-auto p-4">
              {!formatResult ? (
                <EmptyState text="选择模板规则后检查 main.tex 的页数、匿名、章节和参考文献格式。" />
              ) : (
                <div className="grid gap-4">
                  <div
                    className={clsx(
                      "rounded-lg border p-4",
                      formatResult.passed ? "border-emerald-400 bg-emerald-400/10" : "border-amber-400 bg-amber-400/10"
                    )}
                  >
                    <div className="flex items-center gap-2 text-sm font-semibold">
                      {formatResult.passed ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
                      {formatResult.passed ? "主要规则通过" : "需要修改后再投稿"}
                    </div>
                    <div className="mt-1 text-sm text-muted-foreground">
                      估算页数：{formatResult.total_pages_estimate} 页
                    </div>
                  </div>
                  <div className="grid gap-2">
                    {formatResult.issues.length === 0 ? (
                      <EmptyState text="未发现格式问题。" />
                    ) : (
                      formatResult.issues.map((issue, index) => <FormatIssueRow key={`${issue.rule}-${index}`} issue={issue} />)
                    )}
                  </div>
                </div>
              )}
            </div>
          </section>
        )}

        {activeTab === "simulate" && (
          <div className="grid h-full min-h-0 gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
            <section className="flex min-h-0 flex-col rounded-lg border border-border bg-card">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-4">
                <SectionTitle icon={ClipboardCheck} title="模拟审稿" />
                <button
                  onClick={simulateReview}
                  disabled={simulating || !selectedProject}
                  className="inline-flex h-10 items-center gap-2 rounded-md bg-primary px-3 text-sm text-primary-foreground disabled:opacity-50"
                >
                  {simulating ? <Loader2 size={16} className="animate-spin" /> : <ClipboardCheck size={16} />}
                  开始审稿
                </button>
              </div>
              <div className="min-h-0 flex-1 overflow-auto p-4">
                {reviewers.length === 0 ? (
                  <EmptyState text={reviewLog || "点击开始审稿，流式生成每位审稿人的结构化意见。"} />
                ) : (
                  <div className="grid gap-4">
                    {reviewers.map((review) => (
                      <ReviewCardView key={`${review.reviewer}-${review.role}`} review={review} />
                    ))}
                  </div>
                )}
              </div>
            </section>

            <aside className="rounded-lg border border-border bg-card p-4">
              <SectionTitle icon={ShieldCheck} title="决策总结" />
              {metaReview ? (
                <div className="mt-4 grid gap-4">
                  <div className="rounded-lg bg-muted/50 p-4">
                    <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Decision</div>
                    <div className="mt-2 text-2xl font-semibold capitalize">{metaReview.decision}</div>
                    <ScoreBar score={metaReview.average_score} max={10} />
                  </div>
                  <p className="text-sm leading-6 text-muted-foreground">{metaReview.summary}</p>
                  <div className="grid gap-2">
                    {metaReview.action_items.map((item, index) => (
                      <div key={index} className="rounded-md border border-border p-2 text-sm">
                        {item}
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <EmptyState text={simulating ? reviewLog : "Meta-review 会在所有审稿人完成后出现。"} />
              )}
            </aside>
          </div>
        )}

        {activeTab === "letters" && (
          <div className="grid h-full min-h-0 gap-5 xl:grid-cols-2">
            <section className="flex min-h-0 flex-col rounded-lg border border-border bg-card">
              <div className="flex items-center justify-between border-b border-border p-4">
                <SectionTitle icon={Mail} title="Cover Letter" />
                <button
                  onClick={generateCoverLetter}
                  disabled={letterBusy === "cover" || !selectedProject}
                  className="inline-flex h-9 items-center gap-2 rounded-md bg-primary px-3 text-sm text-primary-foreground disabled:opacity-50"
                >
                  {letterBusy === "cover" ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}
                  生成
                </button>
              </div>
              <div className="grid min-h-0 flex-1 grid-rows-[120px_minmax(0,1fr)]">
                <textarea
                  value={coverNotes}
                  onChange={(event) => setCoverNotes(event.target.value)}
                  placeholder="补充给编辑的说明"
                  className="resize-none border-b border-border bg-background p-3 text-sm leading-6 outline-none"
                />
                <textarea
                  value={coverLetter}
                  onChange={(event) => setCoverLetter(event.target.value)}
                  placeholder="Cover Letter 生成结果"
                  className="min-h-0 resize-none bg-background p-4 text-sm leading-6 outline-none"
                />
              </div>
            </section>

            <section className="flex min-h-0 flex-col rounded-lg border border-border bg-card">
              <div className="flex items-center justify-between border-b border-border p-4">
                <SectionTitle icon={MessageSquareReply} title="Rebuttal" />
                <button
                  onClick={generateRebuttal}
                  disabled={letterBusy === "rebuttal" || !selectedProject || !reviewText.trim()}
                  className="inline-flex h-9 items-center gap-2 rounded-md bg-primary px-3 text-sm text-primary-foreground disabled:opacity-50"
                >
                  {letterBusy === "rebuttal" ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}
                  生成
                </button>
              </div>
              <div className="grid min-h-0 flex-1 grid-rows-[180px_minmax(0,1fr)]">
                <textarea
                  value={reviewText}
                  onChange={(event) => setReviewText(event.target.value)}
                  placeholder="粘贴审稿意见"
                  className="resize-none border-b border-border bg-background p-3 text-sm leading-6 outline-none"
                />
                <textarea
                  value={rebuttal}
                  onChange={(event) => setRebuttal(event.target.value)}
                  placeholder="Rebuttal 生成结果"
                  className="min-h-0 resize-none bg-background p-4 text-sm leading-6 outline-none"
                />
              </div>
            </section>
          </div>
        )}

        {activeTab === "checklist" && (
          <div className="grid h-full min-h-0 gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
            <section className="flex min-h-0 flex-col rounded-lg border border-border bg-card">
              <div className="flex items-center justify-between border-b border-border p-4">
                <SectionTitle icon={AlertTriangle} title="7-mode AI Failure Checklist" />
                <button
                  onClick={runChecklist}
                  disabled={checklistBusy || (!selectedProject && !checklistText.trim())}
                  className="inline-flex h-9 items-center gap-2 rounded-md bg-primary px-3 text-sm text-primary-foreground disabled:opacity-50"
                >
                  {checklistBusy ? <Loader2 size={15} className="animate-spin" /> : <ClipboardCheck size={15} />}
                  运行检查
                </button>
              </div>
              <textarea
                value={checklistText}
                onChange={(event) => setChecklistText(event.target.value)}
                placeholder="可选：粘贴要检查的论文段落。留空时会读取当前写作项目 main.tex。"
                className="min-h-0 flex-1 resize-none bg-background p-4 text-sm leading-6 outline-none"
              />
            </section>

            <section className="min-h-0 overflow-auto rounded-lg border border-border bg-card p-4">
              <SectionTitle icon={ShieldCheck} title="检查结果" />
              {!checklistResult ? (
                <EmptyState text="运行后会显示 7 个失败模式的状态、理由和是否阻塞。" />
              ) : (
                <FailureChecklistView result={checklistResult} />
              )}
            </section>
          </div>
        )}
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
      const trimmed = line.trim();
      if (!trimmed.startsWith("data: ")) continue;
      try {
        onData(JSON.parse(trimmed.slice(6)));
      } catch {
        // Ignore malformed SSE rows.
      }
    }
  }
}

function SectionTitle({ icon: Icon, title }: { icon: LucideIcon; title: string }) {
  return (
    <div className="flex items-center gap-2 text-sm font-semibold">
      <Icon size={17} className="text-cyan-500" />
      {title}
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="flex min-h-40 items-center justify-center rounded-lg border border-dashed border-border bg-muted/30 p-6 text-center text-sm text-muted-foreground">
      {text}
    </div>
  );
}

function MetricTile({ label, value, icon: Icon, tone }: { label: string; value: string; icon: LucideIcon; tone: "cyan" | "emerald" | "amber" }) {
  const toneClass = {
    cyan: "text-cyan-500 bg-cyan-400/10",
    emerald: "text-emerald-500 bg-emerald-400/10",
    amber: "text-amber-500 bg-amber-400/10",
  }[tone];
  return (
    <div className="flex min-h-28 flex-col justify-between border-r border-border p-4 last:border-r-0">
      <div className={clsx("flex h-9 w-9 items-center justify-center rounded-md", toneClass)}>
        <Icon size={18} />
      </div>
      <div>
        <div className="text-2xl font-semibold">{value}</div>
        <div className="text-xs text-muted-foreground">{label}</div>
      </div>
    </div>
  );
}

function VenueCard({ item, rank, onUse }: { item: VenueResult; rank: number; onUse: () => void }) {
  return (
    <div className="rounded-lg border border-border bg-background p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-cyan-400/15 text-sm font-semibold text-cyan-500">
              {rank}
            </span>
            <h3 className="text-lg font-semibold">{item.name}</h3>
            <span className="rounded bg-amber-400/15 px-2 py-0.5 text-xs text-amber-600 dark:text-amber-300">
              CCF-{item.ccf_rank}
            </span>
            <span className="rounded bg-emerald-400/15 px-2 py-0.5 text-xs text-emerald-600 dark:text-emerald-300">
              {item.paper_type}
            </span>
          </div>
          <div className="mt-1 text-sm text-muted-foreground">{item.full_name}</div>
        </div>
        <button onClick={onUse} className="rounded-md border border-border px-3 py-1.5 text-xs hover:bg-muted">
          设为目标
        </button>
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-[1fr_140px]">
        <p className="text-sm leading-6 text-muted-foreground">{item.match_reason}</p>
        <div>
          <ScoreBar score={item.match_score} max={1} />
          <div className="mt-2 text-xs text-muted-foreground">
            录用率约 {(item.acceptance_rate * 100).toFixed(0)}% · 审稿 {item.avg_review_weeks} 周
          </div>
        </div>
      </div>
    </div>
  );
}

function FormatIssueRow({ issue }: { issue: FormatIssue }) {
  const Icon = issue.severity === "error" ? XCircle : issue.severity === "warning" ? AlertTriangle : CheckCircle2;
  const tone =
    issue.severity === "error"
      ? "border-destructive/40 bg-destructive/10 text-destructive"
      : issue.severity === "warning"
        ? "border-amber-400/40 bg-amber-400/10 text-amber-600 dark:text-amber-300"
        : "border-cyan-400/40 bg-cyan-400/10 text-cyan-600 dark:text-cyan-300";
  return (
    <div className={clsx("rounded-lg border p-3", tone)}>
      <div className="flex items-center gap-2 text-sm font-medium">
        <Icon size={16} />
        {issue.rule}
        {issue.line > 0 && <span className="text-xs opacity-75">line {issue.line}</span>}
      </div>
      <div className="mt-1 text-sm opacity-90">{issue.message}</div>
    </div>
  );
}

function ReviewCardView({ review }: { review: ReviewCard }) {
  return (
    <article className="rounded-lg border border-border bg-background p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Reviewer {review.reviewer}</div>
          <h3 className="mt-1 text-lg font-semibold">{review.role}</h3>
        </div>
        <div className="w-44">
          <ScoreBar score={review.overall_score} max={10} />
          <div className="mt-1 text-xs text-muted-foreground">Confidence {review.confidence}/5</div>
        </div>
      </div>
      <p className="mt-3 text-sm leading-6 text-muted-foreground">{review.summary}</p>
      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        <ReviewList title="Strengths" items={review.strengths} tone="emerald" />
        <ReviewList title="Weaknesses" items={review.weaknesses} tone="amber" />
        <ReviewList title="Questions" items={review.questions} tone="cyan" />
      </div>
    </article>
  );
}

function ReviewList({ title, items, tone }: { title: string; items: string[]; tone: "emerald" | "amber" | "cyan" }) {
  const toneClass = {
    emerald: "text-emerald-600 dark:text-emerald-300",
    amber: "text-amber-600 dark:text-amber-300",
    cyan: "text-cyan-600 dark:text-cyan-300",
  }[tone];
  return (
    <div className="rounded-md bg-muted/40 p-3">
      <div className={clsx("text-xs font-semibold uppercase tracking-[0.14em]", toneClass)}>{title}</div>
      <ul className="mt-2 grid gap-2 text-sm leading-5">
        {(items || []).map((item, index) => (
          <li key={index}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function FailureChecklistView({ result }: { result: FailureChecklistResult }) {
  return (
    <div className="mt-4 grid gap-4">
      <div
        className={clsx(
          "rounded-lg border p-4",
          result.blocking ? "border-destructive/40 bg-destructive/10" : "border-emerald-400/40 bg-emerald-400/10"
        )}
      >
        <div className="flex items-center gap-2 text-sm font-semibold">
          {result.blocking ? <XCircle size={17} /> : <CheckCircle2 size={17} />}
          {result.blocking ? "存在阻塞项" : "未发现阻塞项"}
        </div>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">{result.summary}</p>
      </div>

      <div className="grid gap-3">
        {result.modes.map((mode) => (
          <div key={mode.mode} className="rounded-lg border border-border bg-background p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-sm font-semibold">
                Mode {mode.mode}: {mode.name}
              </div>
              <span
                className={clsx(
                  "rounded px-2 py-0.5 text-xs",
                  mode.status === "clear"
                    ? "bg-emerald-400/15 text-emerald-600 dark:text-emerald-300"
                    : mode.status === "suspected"
                      ? "bg-destructive/15 text-destructive"
                      : "bg-amber-400/15 text-amber-600 dark:text-amber-300"
                )}
              >
                {mode.status}
              </span>
            </div>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{mode.reasoning}</p>
            {mode.action_required && (
              <div className="mt-3 flex flex-wrap gap-2">
                <button className="rounded-md border border-border px-2 py-1 text-xs hover:bg-muted">
                  Confirm flag
                </button>
                <button className="rounded-md border border-border px-2 py-1 text-xs hover:bg-muted">
                  Override with reasoning
                </button>
                <button className="rounded-md border border-border px-2 py-1 text-xs hover:bg-muted">
                  Revise passage
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function ScoreBar({ score, max }: { score: number; max: number }) {
  const percent = Math.max(0, Math.min(100, (score / max) * 100));
  return (
    <div>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>Score</span>
        <span>{score.toFixed(max === 1 ? 2 : 1)}</span>
      </div>
      <div className="mt-1 h-2 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-gradient-to-r from-cyan-400 via-emerald-400 to-amber-300"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}
