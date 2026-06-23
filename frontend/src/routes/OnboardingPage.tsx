import { useState } from "react";
import { Brain, CheckCircle2, Loader2 } from "lucide-react";
import { api } from "../lib/api";
import { type Language } from "../i18n";
import { useSettingsStore } from "../stores/settingsStore";

type Step = "welcome" | "api-key" | "saving" | "done";

export default function OnboardingPage({ onComplete }: { onComplete: () => void }) {
  const language = useSettingsStore((s) => s.language);
  const setLanguage = useSettingsStore((s) => s.setLanguage);
  const [step, setStep] = useState<Step>("welcome");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("https://api.deepseek.com");
  const [modelName, setModelName] = useState("deepseek-v4-flash");
  const [error, setError] = useState("");

  const zh = language === "zh";

  const saveProvider = async () => {
    if (!apiKey.trim()) {
      setError(zh ? "请输入 API Key" : "Please enter an API key.");
      return;
    }
    setError("");
    setStep("saving");
    try {
      await api.post("settings/providers", {
        json: {
          name: "deepseek",
          display_name: "DeepSeek",
          api_key: apiKey.trim(),
          base_url: baseUrl.trim(),
          default_model: modelName.trim(),
          is_active: true,
          priority: 100,
          max_tokens: 8192,
          temperature: 0.7,
        },
      }).json();
      setStep("done");
      window.setTimeout(onComplete, 900);
    } catch (err) {
      setError(err instanceof Error ? err.message : (zh ? "保存失败" : "Save failed"));
      setStep("api-key");
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-background to-muted/50 p-4 text-foreground">
      <div className="w-full max-w-md">
        {step === "welcome" && (
          <div className="rounded-xl border border-border bg-card p-8 text-center shadow-lg">
            <Brain size={48} className="mx-auto mb-4 text-primary" />
            <h1 className="mb-2 text-2xl font-bold">Research Assistant</h1>
            <p className="mb-6 text-sm leading-6 text-muted-foreground">
              {zh
                ? "首次使用建议先配置一个大模型 Provider，否则解析、生成、对话等 AI 功能会不可用。"
                : "Configure an LLM provider first so parsing, generation, and chat features work correctly."}
            </p>
            <div className="flex justify-center gap-3">
              <button onClick={onComplete} className="rounded-lg border border-border px-4 py-2 text-sm text-muted-foreground hover:bg-muted">
                {zh ? "稍后设置" : "Set up later"}
              </button>
              <button onClick={() => setStep("api-key")} className="rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90">
                {zh ? "开始配置" : "Get started"}
              </button>
            </div>
          </div>
        )}

        {step === "api-key" && (
          <div className="rounded-xl border border-border bg-card p-8 shadow-lg">
            <h2 className="mb-2 text-lg font-semibold">{zh ? "配置 LLM Provider" : "Configure LLM Provider"}</h2>
            <p className="mb-5 text-xs leading-5 text-muted-foreground">
              {zh ? "默认使用 DeepSeek。你之后也可以在 LLM 设置页面添加 OpenAI、Claude、Ollama 或自定义 Provider。" : "DeepSeek is used by default. You can add OpenAI, Claude, Ollama, or custom providers later in LLM Settings."}
            </p>
            {error && <div className="mb-3 rounded-lg bg-destructive/10 p-2 text-xs text-destructive">{error}</div>}
            <label className="mb-3 block">
              <span className="mb-1 block text-xs font-medium">API Key <span className="text-destructive">*</span></span>
              <input value={apiKey} onChange={(event) => setApiKey(event.target.value)} type="password" placeholder="sk-..." className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring" />
            </label>
            <label className="mb-3 block">
              <span className="mb-1 block text-xs font-medium">Base URL</span>
              <input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring" />
            </label>
            <label className="mb-6 block">
              <span className="mb-1 block text-xs font-medium">{zh ? "默认模型" : "Default model"}</span>
              <input value={modelName} onChange={(event) => setModelName(event.target.value)} className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring" />
            </label>
            <div className="flex justify-end gap-3">
              <button onClick={onComplete} className="rounded-lg border border-border px-4 py-2 text-sm text-muted-foreground hover:bg-muted">
                {zh ? "跳过" : "Skip"}
              </button>
              <button onClick={() => void saveProvider()} className="rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90">
                {zh ? "保存并继续" : "Save & continue"}
              </button>
            </div>
          </div>
        )}

        {(step === "saving" || step === "done") && (
          <div className="rounded-xl border border-border bg-card p-8 text-center shadow-lg">
            {step === "saving" ? (
              <>
                <Loader2 size={36} className="mx-auto mb-4 animate-spin text-primary" />
                <p className="text-sm text-muted-foreground">{zh ? "正在保存配置..." : "Saving configuration..."}</p>
              </>
            ) : (
              <>
                <CheckCircle2 size={36} className="mx-auto mb-4 text-green-500" />
                <h2 className="mb-2 text-lg font-semibold text-green-500">{zh ? "配置完成" : "Configuration complete"}</h2>
                <p className="text-xs text-muted-foreground">{zh ? "正在进入主界面..." : "Opening the main interface..."}</p>
              </>
            )}
          </div>
        )}

        <div className="mt-4 text-center">
          <select value={language} onChange={(event) => setLanguage(event.target.value as Language)} className="rounded border border-border bg-background px-2 py-1 text-xs text-muted-foreground outline-none">
            <option value="zh">中文</option>
            <option value="en">English</option>
          </select>
        </div>
      </div>
    </div>
  );
}
