import { useEffect, useState } from "react";
import { Database, Loader2, Trash2 } from "lucide-react";
import { t, type Language } from "../i18n";
import { useSettingsStore } from "../stores/settingsStore";

export function DataManagement() {
  const { dataStats, loadingData, fetchDataStats, clearVectorCache, language } = useSettingsStore();
  const [clearing, setClearing] = useState(false);

  useEffect(() => {
    fetchDataStats();
  }, [fetchDataStats]);

  const clearCache = async () => {
    const ok = window.confirm(t(language, "clearVectorCacheConfirm"));
    if (!ok) return;
    setClearing(true);
    try {
      await clearVectorCache();
    } finally {
      setClearing(false);
    }
  };

  return (
    <section className="rounded-lg border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Database size={17} className="text-emerald-500" />
          {t(language, "dataManagement")}
        </div>
        {loadingData && <Loader2 size={14} className="animate-spin text-muted-foreground" />}
      </div>

      <div className="grid gap-4 p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Stat label={t(language, "papers")} value={dataStats?.paper_count || 0} suffix={t(language, "items")} language={language} />
          <Stat label={t(language, "vectorChunks")} value={dataStats?.chroma_count || 0} suffix={t(language, "rows")} language={language} />
          <Stat label={t(language, "writingProjects")} value={dataStats?.writing_project_count || 0} suffix={t(language, "items")} language={language} />
          <Stat label={t(language, "providers")} value={dataStats?.provider_count || 0} suffix={t(language, "configs")} language={language} />
          <Stat label={t(language, "pdfCache")} value={dataStats?.cache_size_mb || 0} suffix="MB" language={language} />
          <Stat label={t(language, "database")} value={dataStats?.db_size_mb || 0} suffix="MB" language={language} />
        </div>

        <div className="rounded-lg border border-border bg-background/60 p-3">
          <div className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {t(language, "maintenance")}
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-xs text-muted-foreground">
              {t(language, "cachePath")}: <span className="text-foreground">{dataStats?.cache_path || "-"}</span>
            </div>
            <button
              onClick={clearCache}
              disabled={clearing}
              className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-destructive/40 px-3 text-xs text-destructive hover:bg-destructive/10 disabled:opacity-50"
            >
              {clearing ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
              {t(language, "clearVectorCache")}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

function Stat({
  label,
  value,
  suffix,
  language,
}: {
  label: string;
  value: number;
  suffix: string;
  language: Language;
}) {
  return (
    <div className="rounded-lg border border-border bg-background/60 p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-lg font-semibold">
        {typeof value === "number" ? value.toLocaleString(language === "zh" ? "zh-CN" : "en") : value}
      </div>
      <div className="text-[11px] text-muted-foreground">{suffix}</div>
    </div>
  );
}
