import { useEffect, useMemo, useState } from "react";
import {
  BookOpen,
  ExternalLink,
  FileCode2,
  FileText,
  Folder,
  Loader2,
  Plus,
  Save,
} from "lucide-react";
import clsx from "clsx";
import { api } from "../lib/api";

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
  outline: Array<{ title: string; goal?: string }>;
  latex_project_path: string;
  files: Array<{ path: string; type: "file" | "directory"; size: number }>;
  created_at: string;
};

const DEFAULT_OUTLINE = [
  { title: "Introduction", goal: "Motivation, problem statement, and contributions." },
  { title: "Related Work", goal: "Position the work against key papers." },
  { title: "Method", goal: "Describe the proposed method and design choices." },
  { title: "Experiments", goal: "Datasets, baselines, metrics, and results." },
  { title: "Conclusion", goal: "Summary, limitations, and future work." },
];

export default function WritePage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [projects, setProjects] = useState<WritingProject[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
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
  }, []);

  useEffect(() => {
    if (!selectedProject) {
      setOutlineText("");
      return;
    }
    const outline = selectedProject.outline?.length ? selectedProject.outline : DEFAULT_OUTLINE;
    setOutlineText(outline.map((item) => `${item.title}: ${item.goal || ""}`).join("\n"));
  }, [selectedProject?.id]);

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
      const outline = outlineText
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => {
          const [title, ...rest] = line.split(":");
          return { title: title.trim(), goal: rest.join(":").trim() };
        });
      const updated = await api
        .patch(`writing/projects/${selectedProject.id}`, { json: { outline } })
        .json<WritingProject>();
      setProjects((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
    } finally {
      setSaving(false);
    }
  };

  const openExternalEditor = async () => {
    if (!selectedProject?.latex_project_path) return;
    const resp = await api
      .post(`writing/projects/${selectedProject.id}/open`)
      .json<{ path: string; editor: string; args: string[]; message: string }>();
    window.alert(`${resp.message}\n\n${resp.editor} ${resp.args.join(" ")}`);
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
            <h1 className="mt-2 text-3xl font-semibold">论文写作</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              创建 LaTeX 项目、管理模板和维护论文大纲。
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
              placeholder="作者"
              className="h-10 rounded-md border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
            <input
              value={form.targetVenue}
              onChange={(e) => setForm((prev) => ({ ...prev, targetVenue: e.target.value }))}
              placeholder="目标会议"
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

      <div className="grid min-h-0 flex-1 gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
        <aside className="min-h-0 overflow-hidden rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3 text-sm font-medium">写作项目</div>
          <div className="h-full overflow-auto p-3">
            {projects.length === 0 ? (
              <div className="flex h-48 items-center justify-center text-center text-sm text-muted-foreground">
                还没有写作项目。
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
                <button
                  onClick={openExternalEditor}
                  className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-xs hover:bg-muted"
                >
                  <ExternalLink size={14} />
                  外部编辑器
                </button>
              </div>

              <div className="grid min-h-0 flex-1 gap-0 lg:grid-cols-[320px_minmax(0,1fr)]">
                <div className="min-h-0 border-r border-border">
                  <div className="border-b border-border px-4 py-2 text-xs font-medium text-muted-foreground">
                    项目结构
                  </div>
                  <div className="h-full overflow-auto p-3">
                    {selectedProject.files.map((file) => (
                      <div
                        key={file.path}
                        className="flex items-center gap-2 rounded px-2 py-1.5 text-xs hover:bg-muted"
                      >
                        {file.type === "directory" ? (
                          <Folder size={14} className="text-cyan-500" />
                        ) : (
                          <FileCode2 size={14} className="text-muted-foreground" />
                        )}
                        <span className="truncate">{file.path}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex min-h-0 flex-col">
                  <div className="flex items-center justify-between border-b border-border px-4 py-2">
                    <div className="flex items-center gap-2 text-sm font-medium">
                      <BookOpen size={15} />
                      大纲
                    </div>
                    <button
                      onClick={saveOutline}
                      disabled={saving}
                      className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-xs text-primary-foreground disabled:opacity-50"
                    >
                      {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
                      保存大纲
                    </button>
                  </div>
                  <textarea
                    value={outlineText}
                    onChange={(e) => setOutlineText(e.target.value)}
                    className="min-h-0 flex-1 resize-none bg-background p-4 text-sm leading-6 outline-none"
                    placeholder="每行一个章节：Introduction: motivation and contributions"
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              创建或选择一个写作项目。
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
