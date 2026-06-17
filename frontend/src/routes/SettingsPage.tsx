import { useEffect, useState } from "react";
import { useSettingsStore } from "../stores/settingsStore";
import { Moon, Sun, Plus, Trash2, Check, X } from "lucide-react";

export default function SettingsPage() {
  const { theme, toggleTheme, providers, fetchProviders, addProvider, removeProvider, testProvider } =
    useSettingsStore();
  const [showAddForm, setShowAddForm] = useState(false);
  const [testResults, setTestResults] = useState<Record<string, { success: boolean; latency_ms: number }>>({});
  const [testing, setTesting] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    name: "deepseek",
    display_name: "DeepSeek",
    api_key: "",
    base_url: "https://api.deepseek.com",
    default_model: "deepseek-chat",
    priority: 1,
  });

  useEffect(() => {
    fetchProviders();
  }, [fetchProviders]);

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
    });
  };

  const handleTest = async (id: string) => {
    setTesting(id);
    const result = await testProvider(id);
    setTestResults((prev) => ({ ...prev, [id]: result }));
    setTesting(null);
  };

  return (
    <div className="max-w-2xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold mb-1">设置</h1>
        <p className="text-muted-foreground text-sm mb-8">
          配置 LLM API、外观和系统参数
        </p>
      </div>

      {/* 外观 */}
      <section className="mb-8">
        <h2 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wider">
          外观
        </h2>
        <div className="border border-border rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {theme === "dark" ? <Moon size={20} /> : <Sun size={20} />}
              <div>
                <p className="text-sm font-medium">主题</p>
                <p className="text-xs text-muted-foreground">
                  当前: {theme === "dark" ? "暗色模式" : "亮色模式"}
                </p>
              </div>
            </div>
            <button
              onClick={toggleTheme}
              className="px-4 py-2 rounded-lg bg-secondary text-secondary-foreground hover:bg-secondary/80 text-sm transition-colors"
            >
              切换
            </button>
          </div>
        </div>
      </section>

      {/* LLM 配置 */}
      <section className="mb-8">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
            LLM Provider
          </h2>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="flex items-center gap-1 text-xs text-primary hover:underline"
          >
            <Plus size={14} /> 添加 Provider
          </button>
        </div>

        {/* 添加表单 */}
        {showAddForm && (
          <div className="border border-border rounded-lg p-4 mb-3 bg-card">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-muted-foreground">类型</label>
                <select
                  value={formData.name}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      name: e.target.value,
                      base_url:
                        e.target.value === "deepseek"
                          ? "https://api.deepseek.com"
                          : e.target.value === "openai"
                          ? "https://api.openai.com/v1"
                          : e.target.value === "ollama"
                          ? "http://localhost:11434/v1"
                          : "",
                      default_model:
                        e.target.value === "deepseek"
                          ? "deepseek-chat"
                          : e.target.value === "openai"
                          ? "gpt-4o-mini"
                          : e.target.value === "ollama"
                          ? "qwen2.5:7b"
                          : "",
                    })
                  }
                  className="w-full mt-1 px-3 py-2 rounded-md border border-input bg-background text-sm"
                >
                  <option value="deepseek">DeepSeek</option>
                  <option value="openai">OpenAI</option>
                  <option value="ollama">Ollama (本地)</option>
                  <option value="custom">自定义</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-muted-foreground">显示名称</label>
                <input
                  type="text"
                  value={formData.display_name}
                  onChange={(e) =>
                    setFormData({ ...formData, display_name: e.target.value })
                  }
                  className="w-full mt-1 px-3 py-2 rounded-md border border-input bg-background text-sm"
                />
              </div>
              <div className="col-span-2">
                <label className="text-xs text-muted-foreground">API Key</label>
                <input
                  type="password"
                  value={formData.api_key}
                  onChange={(e) =>
                    setFormData({ ...formData, api_key: e.target.value })
                  }
                  className="w-full mt-1 px-3 py-2 rounded-md border border-input bg-background text-sm"
                  placeholder="sk-..."
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Base URL</label>
                <input
                  type="text"
                  value={formData.base_url}
                  onChange={(e) =>
                    setFormData({ ...formData, base_url: e.target.value })
                  }
                  className="w-full mt-1 px-3 py-2 rounded-md border border-input bg-background text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">默认模型</label>
                <input
                  type="text"
                  value={formData.default_model}
                  onChange={(e) =>
                    setFormData({ ...formData, default_model: e.target.value })
                  }
                  className="w-full mt-1 px-3 py-2 rounded-md border border-input bg-background text-sm"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-3">
              <button
                onClick={() => setShowAddForm(false)}
                className="px-4 py-1.5 rounded-md text-sm text-muted-foreground hover:bg-muted"
              >
                取消
              </button>
              <button
                onClick={handleAdd}
                disabled={!formData.api_key}
                className="px-4 py-1.5 rounded-md bg-primary text-primary-foreground text-sm disabled:opacity-50"
              >
                添加
              </button>
            </div>
          </div>
        )}

        {/* Provider 列表 */}
        <div className="space-y-2">
          {providers.length === 0 && (
            <div className="border border-dashed border-border rounded-lg p-8 text-center text-muted-foreground text-sm">
              暂无 LLM 配置。
              <br />
              点击"添加 Provider"配置 DeepSeek API Key。
            </div>
          )}
          {providers.map((p) => (
            <div
              key={p.id}
              className="border border-border rounded-lg p-4 flex items-center justify-between"
            >
              <div className="flex items-center gap-3">
                <div>
                  <p className="text-sm font-medium">
                    {p.display_name || p.name}
                    {p.is_active && (
                      <span className="ml-2 text-xs text-green-500">活跃</span>
                    )}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {p.default_model} · 优先级 {p.priority}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {testResults[p.id] && (
                  <span
                    className={`text-xs ${
                      testResults[p.id].success ? "text-green-500" : "text-red-500"
                    }`}
                  >
                    {testResults[p.id].success
                      ? `${testResults[p.id].latency_ms}ms`
                      : "Failed"}
                  </span>
                )}
                <button
                  onClick={() => handleTest(p.id)}
                  disabled={testing === p.id}
                  className="px-3 py-1 rounded-md text-xs border border-input hover:bg-muted disabled:opacity-50"
                >
                  {testing === p.id ? "测试中…" : "测试"}
                </button>
                <button
                  onClick={() => removeProvider(p.id)}
                  className="p-1 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
