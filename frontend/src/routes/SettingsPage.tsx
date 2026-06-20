import { useEffect, useState } from "react";
import {
  Check,
  Loader2,
  Moon,
  Save,
  Server,
  Sun,
  Wifi,
  XCircle,
} from "lucide-react";
import { DataManagement } from "../components/DataManagement";
import { t } from "../i18n";
import { useSettingsStore } from "../stores/settingsStore";

export default function SettingsPage() {
  const {
    theme,
    language,
    toggleTheme,
    setLanguage,
    systemInfo,
    fetchSystemInfo,
    proxyConfig,
    proxyTesting,
    proxyTestResult,
    fetchProxyConfig,
    updateProxyConfig,
    testProxyConfig,
    semanticScholarConfig,
    fetchSemanticScholarConfig,
    updateSemanticScholarConfig,
  } = useSettingsStore();
  const [proxyUrl, setProxyUrl] = useState(proxyConfig.url);
  const [proxySaving, setProxySaving] = useState(false);
  const [proxyError, setProxyError] = useState("");
  const [s2ApiKey, setS2ApiKey] = useState(semanticScholarConfig.api_key);
  const [s2Saving, setS2Saving] = useState(false);
  const [s2Error, setS2Error] = useState("");
  const [s2Saved, setS2Saved] = useState(false);

  useEffect(() => {
    fetchSystemInfo();
    fetchProxyConfig();
    fetchSemanticScholarConfig();
  }, [fetchSystemInfo, fetchProxyConfig, fetchSemanticScholarConfig]);

  useEffect(() => {
    setProxyUrl(proxyConfig.url);
  }, [proxyConfig.url]);

  useEffect(() => {
    setS2ApiKey(semanticScholarConfig.api_key);
  }, [semanticScholarConfig.api_key]);
  const saveProxy = async (enabled = proxyConfig.enabled) => {
    setProxySaving(true);
    setProxyError("");
    try {
      await updateProxyConfig({ enabled, url: proxyUrl.trim() });
    } catch (error) {
      setProxyError(error instanceof Error ? error.message : t(language, "proxySaveFailed"));
    } finally {
      setProxySaving(false);
    }
  };

  const toggleProxy = async (enabled: boolean) => {
    await saveProxy(enabled);
  };

  const testProxy = async () => {
    setProxyError("");
    try {
      await testProxyConfig({ enabled: proxyConfig.enabled, url: proxyUrl.trim() });
    } catch (error) {
      setProxyError(error instanceof Error ? error.message : t(language, "proxyTestFailed"));
    }
  };

  const saveSemanticScholarKey = async () => {
    setS2Saving(true);
    setS2Error("");
    setS2Saved(false);
    try {
      await updateSemanticScholarConfig({ api_key: s2ApiKey.trim() });
      setS2Saved(true);
    } catch (error) {
      setS2Error(error instanceof Error ? error.message : t(language, "s2ApiKeySaveFailed"));
    } finally {
      setS2Saving(false);
    }
  };

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <header>
        <h1 className="text-2xl font-semibold">{t(language, "settingsTitle")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {t(language, "settingsSubtitle")}
        </p>
      </header>
      <section className="rounded-lg border border-border bg-card">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div className="text-sm font-semibold">{t(language, "appearance")}</div>
          <button
            onClick={toggleTheme}
            className="inline-flex h-9 items-center gap-2 rounded-md border border-border px-3 text-sm hover:bg-muted"
          >
            {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
            {theme === "dark" ? t(language, "lightMode") : t(language, "darkMode")}
          </button>
        </div>
        <div className="flex items-center justify-between px-4 py-3">
          <div className="text-sm text-muted-foreground">{t(language, "language")}</div>
          <div className="inline-flex rounded-md border border-border bg-background p-1">
            <button
              onClick={() => setLanguage("zh")}
              className={`h-8 rounded px-3 text-xs transition-colors ${
                language === "zh" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {t(language, "chinese")}
            </button>
            <button
              onClick={() => setLanguage("en")}
              className={`h-8 rounded px-3 text-xs transition-colors ${
                language === "en" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {t(language, "english")}
            </button>
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-border bg-card">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div>
            <div className="text-sm font-semibold">{t(language, "networkProxy")}</div>
            <div className="mt-0.5 text-xs text-muted-foreground">{t(language, "proxyHelp")}</div>
          </div>
          <label className="relative inline-flex cursor-pointer items-center">
            <input
              type="checkbox"
              checked={proxyConfig.enabled}
              disabled={proxySaving}
              onChange={(event) => void toggleProxy(event.target.checked)}
              className="peer sr-only"
            />
            <span className="h-6 w-11 rounded-full bg-muted transition-colors after:absolute after:left-0.5 after:top-0.5 after:h-5 after:w-5 after:rounded-full after:bg-white after:shadow after:transition-transform peer-checked:bg-primary peer-checked:after:translate-x-5 peer-disabled:opacity-50" />
          </label>
        </div>
        <div className="grid gap-3 p-4">
          <label className="grid gap-1.5 text-xs text-muted-foreground">
            {t(language, "proxyUrl")}
            <input
              value={proxyUrl}
              onChange={(event) => setProxyUrl(event.target.value)}
              placeholder="http://127.0.0.1:7897"
              className="h-9 rounded-md border border-input bg-background px-3 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring"
            />
          </label>
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={() => void saveProxy()}
              disabled={proxySaving || !proxyUrl.trim()}
              className="inline-flex h-9 items-center gap-2 rounded-md bg-primary px-3 text-sm text-primary-foreground disabled:opacity-50"
            >
              {proxySaving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
              {t(language, "saveChanges")}
            </button>
            <button
              onClick={() => void testProxy()}
              disabled={proxyTesting || !proxyUrl.trim()}
              className="inline-flex h-9 items-center gap-2 rounded-md border border-border px-3 text-sm hover:bg-muted disabled:opacity-50"
            >
              {proxyTesting ? <Loader2 size={14} className="animate-spin" /> : <Wifi size={14} />}
              {t(language, "testProxy")}
            </button>
            <span className="text-xs text-muted-foreground">
              {proxyConfig.enabled ? t(language, "proxyEnabled") : t(language, "proxyDisabled")}
            </span>
          </div>
          {(proxyTestResult || proxyError) && (
            <div className={`flex items-start gap-2 text-xs ${proxyTestResult?.success && !proxyError ? "text-green-500" : "text-destructive"}`}>
              {proxyTestResult?.success && !proxyError ? <Check size={14} /> : <XCircle size={14} />}
              <span>{proxyError || proxyTestResult?.message}</span>
            </div>
          )}
        </div>
      </section>

      <section className="rounded-lg border border-border bg-card">
        <div className="border-b border-border px-4 py-3">
          <div className="text-sm font-semibold">{t(language, "semanticScholarSettings")}</div>
          <div className="mt-0.5 text-xs text-muted-foreground">{t(language, "s2ApiKeyHelp")}</div>
        </div>
        <div className="grid gap-3 p-4">
          <label className="grid gap-1.5 text-xs text-muted-foreground">
            {t(language, "s2ApiKey")}
            <input
              type="password"
              value={s2ApiKey}
              onChange={(event) => {
                setS2ApiKey(event.target.value);
                setS2Saved(false);
              }}
              placeholder={t(language, "s2ApiKeyPlaceholder")}
              autoComplete="off"
              className="h-9 rounded-md border border-input bg-background px-3 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring"
            />
          </label>
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={() => void saveSemanticScholarKey()}
              disabled={s2Saving}
              className="inline-flex h-9 items-center gap-2 rounded-md bg-primary px-3 text-sm text-primary-foreground disabled:opacity-50"
            >
              {s2Saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
              {t(language, "saveChanges")}
            </button>
            {s2Saved && <span className="text-xs text-green-500">{t(language, "s2ApiKeySaved")}</span>}
            {s2Error && <span className="text-xs text-destructive">{s2Error}</span>}
          </div>
        </div>
      </section>

      <DataManagement />

      <section className="rounded-lg border border-border bg-card">
        <div className="flex items-center gap-2 border-b border-border px-4 py-3 text-sm font-semibold">
          <Server size={17} className="text-violet-500" />
          {t(language, "systemInfo")}
        </div>
        <div className="grid gap-2 p-4 text-sm md:grid-cols-2">
          <Info label={t(language, "backendVersion")} value={systemInfo?.backend_version || "-"} />
          <Info label={t(language, "python")} value={systemInfo?.python_version || "-"} />
          <Info label={t(language, "databasePath")} value={systemInfo?.db_path || "-"} />
          <Info label={t(language, "chromaPath")} value={systemInfo?.chroma_path || "-"} />
          <Info label={t(language, "cachePath")} value={systemInfo?.cache_path || "-"} />
          <Info label={t(language, "cacheSize")} value={`${systemInfo?.cache_size_mb ?? 0} MB`} />
        </div>
      </section>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-background/60 px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-0.5 break-all text-sm">{value}</div>
    </div>
  );
}
