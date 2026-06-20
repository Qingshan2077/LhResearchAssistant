import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Check,
  ChevronDown,
  ChevronRight,
  Loader2,
  Moon,
  Plus,
  Save,
  Server,
  Sun,
  Trash2,
  Wifi,
  XCircle,
} from "lucide-react";
import { DataManagement } from "../components/DataManagement";
import { UsageDashboard } from "../components/UsageDashboard";
import { t, type Language } from "../i18n";
import { type LLMProvider } from "../lib/api";
import { useSettingsStore } from "../stores/settingsStore";

const MODEL_SUGGESTIONS: Record<string, string[]> = {
  deepseek: ["deepseek-v4-flash", "deepseek-v4-pro", "deepseek-chat"],
  openai: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1-mini", "o1-preview"],
  ollama: ["qwen2.5:7b", "llama3.2:3b", "llama3.1:8b", "mistral:7b", "codellama:7b"],
};

const DEFAULTS: Record<string, { display_name: string; base_url: string; default_model: string }> = {
  deepseek: { display_name: "DeepSeek", base_url: "https://api.deepseek.com", default_model: "deepseek-chat" },
  openai: { display_name: "OpenAI", base_url: "https://api.openai.com/v1", default_model: "gpt-4o-mini" },
  ollama: { display_name: "Ollama", base_url: "http://localhost:11434/v1", default_model: "qwen2.5:7b" },
  custom: { display_name: "Custom", base_url: "", default_model: "" },
};

type ProviderDraft = Partial<LLMProvider> & { api_key?: string };

export default function SettingsPage() {
  const {
    theme,
    language,
    toggleTheme,
    setLanguage,
    providers,
    fetchProviders,
    addProvider,
    updateProvider,
    setActiveProvider,
    removeProvider,
    testProvider,
    systemInfo,
    fetchSystemInfo,
    proxyConfig,
    proxyTesting,
    proxyTestResult,
    fetchProxyConfig,
    updateProxyConfig,
    testProxyConfig,
  } = useSettingsStore();
  const [showAddForm, setShowAddForm] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [testing, setTesting] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const [formData, setFormData] = useState<ProviderDraft>({
    name: "deepseek",
    display_name: "DeepSeek",
    api_key: "",
    base_url: "https://api.deepseek.com",
    default_model: "deepseek-chat",
    priority: 1,
    max_tokens: 8192,
    temperature: 0.7,
    is_active: true,
  });
  const [drafts, setDrafts] = useState<Record<string, ProviderDraft>>({});
  const [proxyUrl, setProxyUrl] = useState(proxyConfig.url);
  const [proxySaving, setProxySaving] = useState(false);
  const [proxyError, setProxyError] = useState("");

  useEffect(() => {
    fetchProviders();
    fetchSystemInfo();
    fetchProxyConfig();
  }, [fetchProviders, fetchSystemInfo, fetchProxyConfig]);

  useEffect(() => {
    setProxyUrl(proxyConfig.url);
  }, [proxyConfig.url]);

  const activeProvider = useMemo(() => providers.find((provider) => provider.is_active), [providers]);

  const handleAddType = (name: string) => {
    const defaults = DEFAULTS[name] || DEFAULTS.custom;
    setFormData((prev) => ({ ...prev, name, ...defaults }));
  };

  const handleAdd = async () => {
    await addProvider(formData);
    setShowAddForm(false);
    setFormData({
      name: "deepseek",
      display_name: "DeepSeek",
      api_key: "",
      base_url: "https://api.deepseek.com",
      default_model: "deepseek-chat",
      priority: 1,
      max_tokens: 8192,
      temperature: 0.7,
      is_active: true,
    });
  };

  const openEditor = (provider: LLMProvider) => {
    setExpandedId((current) => current === provider.id ? null : provider.id);
    setDrafts((prev) => ({
      ...prev,
      [provider.id]: {
        display_name: provider.display_name,
        base_url: provider.base_url,
        default_model: provider.default_model,
        priority: provider.priority,
        max_tokens: provider.max_tokens,
        temperature: provider.temperature,
        api_key: "",
      },
    }));
  };

  const updateDraft = (id: string, patch: ProviderDraft) => {
    setDrafts((prev) => ({ ...prev, [id]: { ...prev[id], ...patch } }));
  };

  const saveProvider = async (provider: LLMProvider) => {
    const draft = drafts[provider.id] || {};
    const patch: ProviderDraft = {
      display_name: draft.display_name,
      base_url: draft.base_url,
      default_model: draft.default_model,
      priority: Number(draft.priority ?? provider.priority),
      max_tokens: Number(draft.max_tokens ?? provider.max_tokens),
      temperature: Number(draft.temperature ?? provider.temperature),
    };
    if (draft.api_key) patch.api_key = draft.api_key;

    setSaving(provider.id);
    try {
      await updateProvider(provider.id, patch);
      setExpandedId(null);
    } finally {
      setSaving(null);
    }
  };

  const handleTest = async (id: string) => {
    setTesting(id);
    try {
      await testProvider(id);
    } finally {
      setTesting(null);
    }
  };

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

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{t(language, "settingsTitle")}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {t(language, "settingsSubtitle")}
          </p>
        </div>
        <div className="rounded-lg border border-border bg-card px-3 py-2 text-xs text-muted-foreground">
          {t(language, "activeProvider")}:{" "}
          <span className="text-foreground">{activeProvider?.display_name || activeProvider?.name || t(language, "none")}</span>
        </div>
      </header>

      <UsageDashboard />

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
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div>
            <div className="text-sm font-semibold">{t(language, "llmProviders")}</div>
            <div className="mt-0.5 text-xs text-muted-foreground">{t(language, "providerHelp")}</div>
          </div>
          <button
            onClick={() => setShowAddForm((prev) => !prev)}
            className="inline-flex h-9 items-center gap-2 rounded-md bg-primary px-3 text-sm text-primary-foreground"
          >
            <Plus size={15} />
            {t(language, "addProvider")}
          </button>
        </div>

        <div className="grid gap-3 p-4">
          {showAddForm && (
            <div className="rounded-lg border border-border bg-background/60 p-4">
              <ProviderFields
                value={formData}
                onChange={(patch) => setFormData((prev) => ({ ...prev, ...patch }))}
                onTypeChange={handleAddType}
                apiKeyHint=""
                language={language}
              />
              <div className="mt-3 flex justify-end gap-2">
                <button
                  onClick={() => setShowAddForm(false)}
                  className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted"
                >
                  {t(language, "cancel")}
                </button>
                <button
                  onClick={handleAdd}
                  className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground disabled:opacity-50"
                >
                  {t(language, "add")}
                </button>
              </div>
            </div>
          )}

          {providers.length === 0 && (
            <div className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
              {t(language, "noProviders")}
            </div>
          )}

          {providers.map((provider) => {
            const expanded = expandedId === provider.id;
            const draft = drafts[provider.id] || {};
            return (
              <div key={provider.id} className="rounded-lg border border-border bg-background/60">
                <div className="flex flex-wrap items-center justify-between gap-3 p-4">
                  <button
                    onClick={() => openEditor(provider)}
                    className="flex min-w-0 items-center gap-3 text-left"
                  >
                    {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{provider.display_name || provider.name}</span>
                        {provider.is_active && <span className="rounded bg-green-500/10 px-1.5 py-0.5 text-[11px] text-green-500">{t(language, "active")}</span>}
                        <ProviderStatus provider={provider} language={language} />
                      </div>
                      <div className="mt-0.5 truncate text-xs text-muted-foreground">
                        {provider.default_model || t(language, "noModel")} / {t(language, "priority")} {provider.priority} / {maskApiKey(provider.api_key, language)}
                      </div>
                    </div>
                  </button>

                  <div className="flex items-center gap-2">
                    {!provider.is_active && (
                      <button
                        onClick={() => setActiveProvider(provider.id)}
                        className="rounded-md border border-border px-3 py-1.5 text-xs hover:bg-muted"
                      >
                        {t(language, "setActive")}
                      </button>
                    )}
                    <button
                      onClick={() => handleTest(provider.id)}
                      disabled={testing === provider.id}
                      className="inline-flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-xs hover:bg-muted disabled:opacity-50"
                    >
                      {testing === provider.id ? <Loader2 size={13} className="animate-spin" /> : <Wifi size={13} />}
                      {t(language, "test")}
                    </button>
                    <button
                      onClick={() => removeProvider(provider.id)}
                      className="rounded-md p-1.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>

                {expanded && (
                  <div className="border-t border-border p-4">
                    <ProviderFields
                      value={{ ...provider, ...draft }}
                      onChange={(patch) => updateDraft(provider.id, patch)}
                      apiKeyHint={maskApiKey(provider.api_key, language)}
                      fixedType={provider.name}
                      language={language}
                    />
                    <div className="mt-3 flex justify-end">
                      <button
                        onClick={() => saveProvider(provider)}
                        disabled={saving === provider.id}
                        className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground disabled:opacity-50"
                      >
                        {saving === provider.id ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                        {t(language, "saveChanges")}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
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

function ProviderFields({
  value,
  onChange,
  onTypeChange,
  apiKeyHint,
  fixedType,
  language,
}: {
  value: ProviderDraft;
  onChange: (patch: ProviderDraft) => void;
  onTypeChange?: (name: string) => void;
  apiKeyHint: string;
  fixedType?: string;
  language: Language;
}) {
  const type = fixedType || value.name || "custom";
  const suggestions = MODEL_SUGGESTIONS[type] || [];

  return (
    <div className="grid gap-3 md:grid-cols-2">
      {!fixedType && (
        <Field label={t(language, "type")}>
          <select
            value={value.name || "custom"}
            onChange={(e) => onTypeChange?.(e.target.value)}
            className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
          >
            <option value="deepseek">DeepSeek</option>
            <option value="openai">OpenAI</option>
            <option value="ollama">Ollama</option>
            <option value="custom">Custom</option>
          </select>
        </Field>
      )}
      <Field label={t(language, "displayName")}>
        <input value={value.display_name || ""} onChange={(e) => onChange({ display_name: e.target.value })} className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm" />
      </Field>
      <Field label={t(language, "model")}>
        <input
          list={`models-${type}`}
          value={value.default_model || ""}
          onChange={(e) => onChange({ default_model: e.target.value })}
          className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
        />
        {suggestions.length > 0 && (
          <datalist id={`models-${type}`}>
            {suggestions.map((model) => <option key={model} value={model} />)}
          </datalist>
        )}
      </Field>
      <Field label={t(language, "baseUrl")}>
        <input value={value.base_url || ""} onChange={(e) => onChange({ base_url: e.target.value })} className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm" />
      </Field>
      <Field label={t(language, "apiKey")}>
        <input type="password" value={value.api_key || ""} onChange={(e) => onChange({ api_key: e.target.value })} placeholder={apiKeyHint || "sk-..."} className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm" />
      </Field>
      <Field label={t(language, "maxTokens")}>
        <input type="number" value={value.max_tokens ?? 8192} onChange={(e) => onChange({ max_tokens: Number(e.target.value) })} className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm" />
      </Field>
      <Field label={`${t(language, "temperature")} ${value.temperature ?? 0.7}`}>
        <input type="range" min={0} max={2} step={0.1} value={value.temperature ?? 0.7} onChange={(e) => onChange({ temperature: Number(e.target.value) })} className="w-full" />
      </Field>
      <Field label={t(language, "priority")}>
        <input type="number" value={value.priority ?? 0} onChange={(e) => onChange({ priority: Number(e.target.value) })} className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm" />
      </Field>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="grid gap-1 text-xs text-muted-foreground">
      {label}
      {children}
    </label>
  );
}

function ProviderStatus({ provider, language }: { provider: LLMProvider; language: Language }) {
  if (provider.last_test_success === true) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-green-500">
        <Check size={12} />
        {provider.last_test_latency}ms
      </span>
    );
  }
  if (provider.last_test_success === false) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-red-500">
        <XCircle size={12} />
        {t(language, "failed")}
      </span>
    );
  }
  return <span className="text-xs text-muted-foreground">{t(language, "untested")}</span>;
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-background/60 px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-0.5 break-all text-sm">{value}</div>
    </div>
  );
}

function maskApiKey(key: string, language: Language) {
  if (!key) return t(language, "noKey");
  if (key.length < 8) return "****";
  return `${key.slice(0, 3)}****${key.slice(-4)}`;
}
