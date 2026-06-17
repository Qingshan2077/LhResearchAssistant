import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  Check,
  ClipboardCheck,
  Download,
  ExternalLink,
  FileCode2,
  FileText,
  Folder,
  Loader2,
  Plus,
  Save,
  ShieldCheck,
  Sparkles,
  Wand2,
} from "lucide-react";
import clsx from "clsx";
import { api, type Paper } from "../lib/api";
import { t } from "../i18n";
import { useSettingsStore } from "../stores/settingsStore";

type Template = {
  name: string;
  display_name: string;
  language: string;
};

type WritingProject = {
  id: string;
  project_id: string;
  title: string;
  target_venue: string;
  language: string;
  template: string;
  external_editor_path: string;
  outline: Array<{ title: string; goal?: string; subsections?: Array<string | { title: string; goal?: string }> }>;
  latex_project_path: string;
  files: Array<{ path: string; type: "file" | "directory"; size: number }>;
  created_at: string;
};

type PolishResult = {
  original: string;
  polished: string;
};

type VerifyResult = {
  index: number;
  doi?: string;
  valid: boolean;
  status: string;
  message: string;
};

type WritingQualityFlag = {
  issue: string;
  severity: "info" | "warning" | "error";
  count: number;
  examples: string[];
  suggestion: string;
};

type WritingQualityResult = {
  flags: WritingQualityFlag[];
  overall_rating: string;
};

const DEFAULT_OUTLINE = [
  { title: "Introduction", goal: "Motivation, problem statement, and contributions." },
  { title: "Related Work", goal: "Position the work against key papers." },
  { title: "Method", goal: "Describe the proposed method and design choices." },
  { title: "Experiments", goal: "Datasets, baselines, metrics, and results." },
  { title: "Conclusion", goal: "Summary, limitations, and future work." },
];

export default function WritePage() {
  const language = useSettingsStore((s) => s.language);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [projects, setProjects] = useState<WritingProject[]>([]);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedPaperIds, setSelectedPaperIds] = useState<Set<string>>(new Set());
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [generatingOutline, setGeneratingOutline] = useState(false);
  const [generatingSection, setGeneratingSection] = useState<string | null>(null);
  const [citationBusy, setCitationBusy] = useState(false);
  const [polishing, setPolishing] = useState(false);
  const [form, setForm] = useState({
    title: "",
    author: "",
    targetVenue: "",
    template: "neurips_2024",
  });

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedId) || projects[0] || null,
    [projects, selectedId]
  );

  const [outlineText, setOutlineText] = useState("");
  const [activeSection, setActiveSection] = useState("");
  const [sectionContent, setSectionContent] = useState<Record<string, string>>({});
  const [bibtex, setBibtex] = useState("");
  const [verifyResults, setVerifyResults] = useState<VerifyResult[]>([]);
  const [polishResult, setPolishResult] = useState<PolishResult | null>(null);
  const [polishStyle, setPolishStyle] = useState("academic");
  const [qualityChecking, setQualityChecking] = useState(false);
  const [qualityResult, setQualityResult] = useState<WritingQualityResult | null>(null);

  useEffect(() => {
    api
      .get("writing/templates")
      .json<{ items: Template[] }>()
      .then((resp) => {
        setTemplates(resp.items);
        if (resp.items[0]) {
          setForm((prev) => ({ ...prev, template: prev.template || resp.items[0].name }));
        }
      })
      .catch(() => setTemplates([]));

    refreshProjects();
    api
      .get("papers", { searchParams: { project_id: "default", page_size: 500 } })
      .json<{ items: Paper[] }>()
      .then((resp) => setPapers(resp.items))
      .catch(() => setPapers([]));
  }, []);

  useEffect(() => {
    if (!selectedProject) {
      setOutlineText("");
      setActiveSection("");
      return;
    }
    const outline = selectedProject.outline?.length ? selectedProject.outline : DEFAULT_OUTLINE;
    setOutlineText(outlineToText(outline));
    setActiveSection(outline[0]?.title || "");
  }, [selectedProject?.id]);

  const outlineItems = useMemo(() => parseOutline(outlineText), [outlineText]);
  const selectedPaperArray = useMemo(() => Array.from(selectedPaperIds), [selectedPaperIds]);

  const refreshProjects = async () => {
    const resp = await api
      .get("writing/projects", { searchParams: { project_id: "default" } })
      .json<{ items: WritingProject[] }>();
    setProjects(resp.items);
    if (!selectedId && resp.items[0]) setSelectedId(resp.items[0].id);
  };

  const createProject = async () => {
    if (!form.title.trim()) return;
    setCreating(true);
    try {
      const project = await api
        .post("writing/projects", {
          json: {
            project_id: "default",
            title: form.title.trim(),
            author: form.author.trim(),
            target_venue: form.targetVenue.trim(),
            template: form.template,
            language: templates.find((t) => t.name === form.template)?.language || "en",
          },
        })
        .json<WritingProject>();
      setProjects((prev) => [project, ...prev]);
      setSelectedId(project.id);
      setForm((prev) => ({ ...prev, title: "", targetVenue: "" }));
    } finally {
      setCreating(false);
    }
  };

  const saveOutline = async () => {
    if (!selectedProject) return;
    setSaving(true);
    try {
      const updated = await api
        .patch(`writing/projects/${selectedProject.id}`, { json: { outline: outlineItems } })
        .json<WritingProject>();
      setProjects((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
    } finally {
      setSaving(false);
    }
  };

  const generateOutline = async () => {
    if (!selectedProject) return;
    setGeneratingOutline(true);
    try {
      const updated = await api
        .post(`writing/projects/${selectedProject.id}/generate-outline`, {
          json: {
            project_id: "default",
            title: selectedProject.title,
            paper_ids: selectedPaperArray,
            language: selectedProject.language,
          },
        })
        .json<WritingProject>();
      setProjects((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
      setOutlineText(outlineToText(updated.outline));
    } finally {
      setGeneratingOutline(false);
    }
  };

  const generateSection = async (sectionName: string) => {
    if (!selectedProject || !sectionName) return;
    setGeneratingSection(sectionName);
    setSectionContent((prev) => ({ ...prev, [sectionName]: "" }));
    try {
      const response = await fetch(`/api/v1/writing/projects/${selectedProject.id}/generate-section`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          section_name: sectionName,
          paper_ids: selectedPaperArray,
          style: "academic",
          language: selectedProject.language,
        }),
      });
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
              setSectionContent((prev) => ({
                ...prev,
                [sectionName]: (prev[sectionName] || "") + data.content,
              }));
            }
          } catch {
            // ignore malformed SSE row
          }
        }
      }
    } finally {
      setGeneratingSection(null);
    }
  };

  const exportBibtex = async () => {
    setCitationBusy(true);
    try {
      const resp = await api
        .post("writing/citations/export", { json: { paper_ids: selectedPaperArray } })
        .json<{ bibtex: string }>();
      setBibtex(resp.bibtex);
      const blob = new Blob([resp.bibtex], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "bibliography.bib";
      anchor.click();
      URL.revokeObjectURL(url);
    } finally {
      setCitationBusy(false);
    }
  };

  const verifyBibtex = async () => {
    if (!bibtex.trim()) return;
    setCitationBusy(true);
    try {
      const entries = bibtex
        .split(/\n(?=@\w+\{)/g)
        .map((entry) => entry.trim())
        .filter(Boolean);
      const resp = await api
        .post("writing/citations/verify", { json: { bibtex_entries: entries } })
        .json<{ items: VerifyResult[] }>();
      setVerifyResults(resp.items);
    } finally {
      setCitationBusy(false);
    }
  };

  const polishSection = async () => {
    if (!activeSection || !sectionContent[activeSection]) return;
    setPolishing(true);
    try {
      const resp = await api
        .post("writing/polish", {
          json: {
            text: sectionContent[activeSection],
            style: polishStyle,
            language: selectedProject?.language || "en",
            preserve_technical: true,
          },
        })
        .json<PolishResult>();
      setPolishResult(resp);
    } finally {
      setPolishing(false);
    }
  };

  const applyPolish = () => {
    if (!activeSection || !polishResult) return;
    setSectionContent((prev) => ({ ...prev, [activeSection]: polishResult.polished }));
    setPolishResult(null);
  };

  const openExternalEditor = async () => {
    if (!selectedProject?.latex_project_path) return;
    const resp = await api
      .post(`writing/projects/${selectedProject.id}/open`)
      .json<{ path: string; editor: string; args: string[]; message: string }>();
    window.alert(`${resp.message}\n\n${resp.editor} ${resp.args.join(" ")}`);
  };

  const checkWritingQuality = async () => {
    if (!selectedProject) return;
    setQualityChecking(true);
    try {
      const resp = await api
        .post("review/check-writing-quality", {
          json: {
            writing_project_id: selectedProject.id,
            text: activeSection ? sectionContent[activeSection] || "" : "",
          },
        })
        .json<WritingQualityResult>();
      setQualityResult(resp);
    } finally {
      setQualityChecking(false);
    }
  };

  const togglePaper = (paperId: string) => {
    setSelectedPaperIds((prev) => {
      const next = new Set(prev);
      if (next.has(paperId)) next.delete(paperId);
      else next.add(paperId);
      return next;
    });
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-5">
      <section className="rounded-lg border border-border bg-card p-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-cyan-500">
              <FileText size={14} />
              LaTeX Workspace
            </div>
            <h1 className="mt-2 text-3xl font-semibold">{t(language, "writingProject")}</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {t(language, "writeSubtitle")}
            </p>
          </div>

          <div className="grid gap-2 md:grid-cols-[180px_150px_150px_170px_auto]">
            <input
              value={form.title}
              onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))}
              placeholder="论文标题"
              className="h-10 rounded-md border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
            <input
              value={form.author}
              onChange={(e) => setForm((prev) => ({ ...prev, author: e.target.value }))}
              placeholder={t(language, "authorName")}
              className="h-10 rounded-md border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
            <input
              value={form.targetVenue}
              onChange={(e) => setForm((prev) => ({ ...prev, targetVenue: e.target.value }))}
              placeholder={t(language, "targetVenue")}
              className="h-10 rounded-md border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
            <select
              value={form.template}
              onChange={(e) => setForm((prev) => ({ ...prev, template: e.target.value }))}
              className="h-10 rounded-md border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
            >
              {templates.map((template) => (
                <option key={template.name} value={template.name}>
                  {template.display_name}
                </option>
              ))}
            </select>
            <button
              onClick={createProject}
              disabled={creating || !form.title.trim()}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground disabled:opacity-50"
            >
              {creating ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
              创建
            </button>
          </div>
        </div>
      </section>

      <div className="grid min-h-0 flex-1 gap-5 xl:grid-cols-[320px_minmax(0,1fr)_360px]">
        <aside className="min-h-0 overflow-hidden rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3 text-sm font-medium">{t(language, "writingProject")}</div>
          <div className="h-full overflow-auto p-3">
            {projects.length === 0 ? (
              <div className="flex h-48 items-center justify-center text-center text-sm text-muted-foreground">
                {t(language, "noWritingProjects")}
              </div>
            ) : (
              <div className="grid gap-2">
                {projects.map((project) => (
                  <button
                    key={project.id}
                    onClick={() => setSelectedId(project.id)}
                    className={clsx(
                      "rounded-lg border p-3 text-left transition",
                      selectedProject?.id === project.id
                        ? "border-cyan-400 bg-cyan-400/10"
                        : "border-border hover:bg-muted"
                    )}
                  >
                    <div className="line-clamp-2 text-sm font-medium">{project.title}</div>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                      <span>{project.template || "template"}</span>
                      <span>{project.target_venue || "venue N/A"}</span>
                      <span>{project.language}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </aside>

        <section className="min-h-0 overflow-hidden rounded-lg border border-border bg-card">
          {selectedProject ? (
            <div className="flex h-full min-h-0 flex-col">
              <div className="flex items-center justify-between border-b border-border px-4 py-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold">{selectedProject.title}</div>
                  <div className="truncate text-xs text-muted-foreground">
                    {selectedProject.latex_project_path}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={checkWritingQuality}
                    disabled={qualityChecking}
                    className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-xs hover:bg-muted disabled:opacity-50"
                  >
                    {qualityChecking ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />}
                    写作质量检查
                  </button>
                  <button
                    onClick={openExternalEditor}
                    className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-xs hover:bg-muted"
                  >
                    <ExternalLink size={14} />
                    外部编辑器
                  </button>
                </div>
              </div>

              <div className="grid min-h-0 flex-1 gap-0 lg:grid-cols-[260px_minmax(0,1fr)]">
                <div className="min-h-0 border-r border-border">
                  <div className="border-b border-border px-4 py-2 text-xs font-medium text-muted-foreground">
                    项目结构
                  </div>
                  <div className="h-48 overflow-auto border-b border-border p-3">
                    {selectedProject.files.map((file) => (
                      <div key={file.path} className="flex items-center gap-2 rounded px-2 py-1.5 text-xs hover:bg-muted">
                        {file.type === "directory" ? (
                          <Folder size={14} className="text-cyan-500" />
                        ) : (
                          <FileCode2 size={14} className="text-muted-foreground" />
                        )}
                        <span className="truncate">{file.path}</span>
                      </div>
                    ))}
                  </div>

                  <div className="flex items-center justify-between border-b border-border px-4 py-2">
                    <span className="text-xs font-medium text-muted-foreground">大纲</span>
                    <button
                      onClick={generateOutline}
                      disabled={generatingOutline}
                      className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[11px] hover:bg-muted disabled:opacity-50"
                    >
                      {generatingOutline ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
                      {t(language, "generateOutline")}
                    </button>
                  </div>
                  <div className="h-[calc(100%-13rem)] overflow-auto p-2">
                    {outlineItems.map((item) => (
                      <button
                        key={item.title}
                        onClick={() => setActiveSection(item.title)}
                        className={clsx(
                          "mb-2 w-full rounded-md border p-2 text-left text-xs transition",
                          activeSection === item.title ? "border-cyan-400 bg-cyan-400/10" : "border-border hover:bg-muted"
                        )}
                      >
                        <div className="font-medium">{item.title}</div>
                        <div className="mt-1 line-clamp-2 text-muted-foreground">{item.goal}</div>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex min-h-0 flex-col">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-2">
                    <div className="flex items-center gap-2 text-sm font-medium">
                      <BookOpen size={15} />
                      {activeSection || "大纲编辑"}
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={saveOutline}
                        disabled={saving}
                        className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-xs hover:bg-muted disabled:opacity-50"
                      >
                        {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
                        保存大纲
                      </button>
                      <button
                        onClick={() => generateSection(activeSection)}
                        disabled={!activeSection || generatingSection === activeSection}
                        className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-xs text-primary-foreground disabled:opacity-50"
                      >
                        {generatingSection === activeSection ? <Loader2 size={13} className="animate-spin" /> : <Wand2 size={13} />}
                        {t(language, "generateSection")}
                      </button>
                    </div>
                  </div>
                  <div className="grid min-h-0 flex-1 grid-rows-[180px_minmax(0,1fr)]">
                    <textarea
                      value={outlineText}
                      onChange={(e) => setOutlineText(e.target.value)}
                      className="resize-none border-b border-border bg-background p-4 text-sm leading-6 outline-none"
                      placeholder="每行一个章节：Introduction: motivation and contributions"
                    />
                    <div className="flex min-h-0 flex-col">
                      <div className="flex items-center justify-between border-b border-border px-4 py-2">
                        <span className="text-xs text-muted-foreground">章节内容</span>
                        <div className="flex items-center gap-2">
                          <select
                            value={polishStyle}
                            onChange={(e) => setPolishStyle(e.target.value)}
                            className="h-7 rounded border border-input bg-background px-2 text-xs"
                          >
                            <option value="academic">学术</option>
                            <option value="concise">简洁</option>
                            <option value="fluent">流畅</option>
                          </select>
                          <button
                            onClick={polishSection}
                            disabled={polishing || !activeSection || !sectionContent[activeSection]}
                            className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs hover:bg-muted disabled:opacity-50"
                          >
                            {polishing ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
                            {t(language, "polishText")}
                          </button>
                        </div>
                      </div>
                      <textarea
                        value={sectionContent[activeSection] || ""}
                        onChange={(e) =>
                          setSectionContent((prev) => ({ ...prev, [activeSection]: e.target.value }))
                        }
                        className="min-h-0 flex-1 resize-none bg-background p-4 font-mono text-sm leading-6 outline-none"
                        placeholder={t(language, "sectionContentPlaceholder")}
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              {t(language, "selectOrCreateProject")}
            </div>
          )}
        </section>

        <aside className="flex min-h-0 flex-col gap-4 overflow-hidden">
          <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-border bg-card">
            <div className="border-b border-border px-4 py-3 text-sm font-medium">
              引用管理
            </div>
            <div className="min-h-0 flex-1 overflow-auto p-3">
              {papers.map((paper) => {
                const selected = selectedPaperIds.has(paper.id);
                return (
                  <button
                    key={paper.id}
                    onClick={() => togglePaper(paper.id)}
                    className={clsx(
                      "mb-2 flex w-full items-start gap-2 rounded-md border p-2 text-left text-xs",
                      selected ? "border-cyan-400 bg-cyan-400/10" : "border-border hover:bg-muted"
                    )}
                  >
                    <span
                      className={clsx(
                        "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border",
                        selected ? "border-cyan-400 bg-cyan-400 text-slate-950" : "border-border"
                      )}
                    >
                      {selected && <Check size={12} />}
                    </span>
                    <span className="min-w-0">
                      <span className="line-clamp-2 font-medium">{paper.title}</span>
                      <span className="mt-1 block text-muted-foreground">
                        {paper.year || "N/A"} · {paper.venue || "N/A"}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
            <div className="grid gap-2 border-t border-border p-3">
              <button
                onClick={exportBibtex}
                disabled={citationBusy || selectedPaperIds.size === 0}
                className="inline-flex items-center justify-center gap-2 rounded-md bg-primary px-3 py-2 text-xs text-primary-foreground disabled:opacity-50"
              >
                <Download size={13} />
                {t(language, "exportLatex")}
              </button>
              <button
                onClick={verifyBibtex}
                disabled={citationBusy || !bibtex.trim()}
                className="inline-flex items-center justify-center gap-2 rounded-md border border-border px-3 py-2 text-xs hover:bg-muted disabled:opacity-50"
              >
                <ClipboardCheck size={13} />
                验证引用
              </button>
            </div>
          </section>

          <section className="max-h-[38%] overflow-auto rounded-lg border border-border bg-card p-3">
            <div className="mb-2 text-sm font-medium">润色对比</div>
            {polishResult ? (
              <div className="grid gap-3 text-xs">
                <DiffBlock title="原文" text={polishResult.original} />
                <DiffBlock title="润色后" text={polishResult.polished} />
                <button
                  onClick={applyPolish}
                  className="rounded-md bg-primary px-3 py-2 text-xs text-primary-foreground"
                >
                  应用润色结果
                </button>
              </div>
            ) : (
              <div className="text-xs text-muted-foreground">
                {t(language, "polishResultHint")}
              </div>
            )}

            {verifyResults.length > 0 && (
              <div className="mt-4 border-t border-border pt-3">
                <div className="mb-2 text-sm font-medium">引用验证</div>
                <div className="grid gap-2">
                  {verifyResults.map((item) => (
                    <div key={item.index} className="rounded-md bg-muted/40 p-2 text-xs">
                      <div className={item.valid ? "text-green-500" : "text-destructive"}>
                        #{item.index} {item.status}
                      </div>
                      <div className="mt-1 text-muted-foreground">{item.message}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {qualityResult && (
              <div className="mt-4 border-t border-border pt-3">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <div className="text-sm font-medium">写作质量检查</div>
                  <span className="rounded bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                    {qualityResult.overall_rating}
                  </span>
                </div>
                <div className="grid gap-2">
                  {qualityResult.flags.length === 0 ? (
                    <div className="rounded-md bg-muted/40 p-2 text-xs text-muted-foreground">
                      {t(language, "noQualityIssues")}
                    </div>
                  ) : (
                    qualityResult.flags.map((flag) => (
                      <QualityFlagRow key={flag.issue} flag={flag} />
                    ))
                  )}
                </div>
              </div>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}

function QualityFlagRow({ flag }: { flag: WritingQualityFlag }) {
  const tone =
    flag.severity === "error"
      ? "border-destructive/40 bg-destructive/10 text-destructive"
      : flag.severity === "warning"
        ? "border-amber-400/40 bg-amber-400/10 text-amber-600 dark:text-amber-300"
        : "border-border bg-muted/40 text-muted-foreground";
  return (
    <div className={`rounded-md border p-2 text-xs ${tone}`}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1 font-medium">
          <AlertTriangle size={13} />
          {flag.issue}
        </div>
        <span>{flag.count}</span>
      </div>
      {flag.examples.length > 0 && (
        <div className="mt-2 grid gap-1">
          {flag.examples.slice(0, 3).map((example) => (
            <div key={example} className="rounded bg-background/60 px-2 py-1">
              {example}
            </div>
          ))}
        </div>
      )}
      <div className="mt-2 text-muted-foreground">{flag.suggestion}</div>
    </div>
  );
}

function outlineToText(outline: WritingProject["outline"]) {
  return outline.map((item) => `${item.title}: ${item.goal || ""}`).join("\n");
}

function parseOutline(text: string) {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [title, ...rest] = line.split(":");
      return { title: title.trim(), goal: rest.join(":").trim(), subsections: [] };
    });
}

function DiffBlock({ title, text }: { title: string; text: string }) {
  return (
    <div>
      <div className="mb-1 text-muted-foreground">{title}</div>
      <div className="max-h-36 overflow-auto rounded-md bg-background p-2 leading-5">
        {text}
      </div>
    </div>
  );
}
