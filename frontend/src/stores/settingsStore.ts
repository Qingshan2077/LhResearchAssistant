import { create } from "zustand";
import {
  api,
  type DataStats,
  type LLMProvider,
  type ProxyConfig,
  type ProxyTestResult,
  type SemanticScholarConfig,
  type SystemInfo,
  type UsageByFunction,
  type UsageByProvider,
  type UsageRecord,
  type UsageSummary,
} from "../lib/api";
import type { Language } from "../i18n";

const getInitialLanguage = (): Language => {
  const stored = localStorage.getItem("app-language");
  return stored === "en" || stored === "zh" ? stored : "zh";
};

const getInitialTheme = (): "dark" | "light" => {
  const stored = localStorage.getItem("app-theme");
  return stored === "dark" || stored === "light" ? stored : "light";
};

interface SettingsStore {
  theme: "dark" | "light";
  language: Language;
  providers: LLMProvider[];
  activeProviderId: string | null;
  usageSummary: UsageSummary | null;
  usageByProvider: UsageByProvider;
  usageByFunction: UsageByFunction;
  recentUsage: UsageRecord[];
  dataStats: DataStats | null;
  systemInfo: SystemInfo | null;
  proxyConfig: ProxyConfig;
  proxyTesting: boolean;
  proxyTestResult: ProxyTestResult | null;
  semanticScholarConfig: SemanticScholarConfig;
  loadingUsage: boolean;
  loadingData: boolean;

  toggleTheme: () => void;
  setLanguage: (language: Language) => void;
  fetchProviders: () => Promise<void>;
  addProvider: (p: Partial<LLMProvider>) => Promise<void>;
  updateProvider: (id: string, p: Partial<LLMProvider>) => Promise<void>;
  setActiveProvider: (id: string) => Promise<void>;
  removeProvider: (id: string) => Promise<void>;
  testProvider: (id: string) => Promise<{ success: boolean; latency_ms: number }>;
  fetchUsage: (days?: number) => Promise<void>;
  fetchDataStats: () => Promise<void>;
  clearVectorCache: () => Promise<void>;
  fetchSystemInfo: () => Promise<void>;
  fetchProxyConfig: () => Promise<void>;
  updateProxyConfig: (config: ProxyConfig) => Promise<void>;
  testProxyConfig: (config: ProxyConfig) => Promise<void>;
  fetchSemanticScholarConfig: () => Promise<void>;
  updateSemanticScholarConfig: (config: SemanticScholarConfig) => Promise<void>;
}

export const useSettingsStore = create<SettingsStore>((set, get) => ({
  theme: getInitialTheme(),
  language: getInitialLanguage(),
  providers: [],
  activeProviderId: null,
  usageSummary: null,
  usageByProvider: [],
  usageByFunction: [],
  recentUsage: [],
  dataStats: null,
  systemInfo: null,
  proxyConfig: { enabled: false, url: "http://127.0.0.1:7897" },
  proxyTesting: false,
  proxyTestResult: null,
  semanticScholarConfig: { api_key: "" },
  loadingUsage: false,
  loadingData: false,

  toggleTheme: () => {
    set((s) => {
      const next = s.theme === "dark" ? "light" : "dark";
      localStorage.setItem("app-theme", next);
      document.documentElement.classList.toggle("dark", next === "dark");
      return { theme: next };
    });
  },

  setLanguage: (language) => {
    localStorage.setItem("app-language", language);
    document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
    set({ language });
  },

  fetchProviders: async () => {
    try {
      const providers = await api.get("settings/providers").json<LLMProvider[]>();
      const active = providers.find((p) => p.is_active);
      set({ providers, activeProviderId: active?.id || null });
    } catch {
      // Keep settings usable if backend settings are temporarily unavailable.
    }
  },

  addProvider: async (p) => {
    await api.post("settings/providers", { json: p });
    await get().fetchProviders();
  },

  updateProvider: async (id, p) => {
    await api.patch(`settings/providers/${id}`, { json: p });
    await get().fetchProviders();
  },

  setActiveProvider: async (id) => {
    await get().updateProvider(id, { is_active: true });
  },

  removeProvider: async (id) => {
    await api.delete(`settings/providers/${id}`);
    await get().fetchProviders();
  },

  testProvider: async (id) => {
    const resp = await api
      .post("settings/providers/test", { json: { provider_id: id } })
      .json<{ success: boolean; latency_ms: number }>();
    await get().fetchProviders();
    return resp;
  },

  fetchUsage: async (days = 7) => {
    set({ loadingUsage: true });
    try {
      const [summary, byProvider, byFunction, recent] = await Promise.all([
        api.get("settings/usage/summary", { searchParams: { days } }).json<UsageSummary>(),
        api.get("settings/usage/by-provider", { searchParams: { days } }).json<UsageByProvider>(),
        api.get("settings/usage/by-function", { searchParams: { days } }).json<UsageByFunction>(),
        api.get("settings/usage/recent", { searchParams: { limit: 20 } }).json<UsageRecord[]>(),
      ]);
      set({ usageSummary: summary, usageByProvider: byProvider, usageByFunction: byFunction, recentUsage: recent });
    } finally {
      set({ loadingUsage: false });
    }
  },

  fetchDataStats: async () => {
    set({ loadingData: true });
    try {
      const dataStats = await api.get("settings/data/stats").json<DataStats>();
      set({ dataStats });
    } finally {
      set({ loadingData: false });
    }
  },

  clearVectorCache: async () => {
    await api.post("settings/data/clear-vector-cache");
    await get().fetchDataStats();
  },

  fetchSystemInfo: async () => {
    const systemInfo = await api.get("settings/system-info").json<SystemInfo>();
    set({ systemInfo });
  },

  fetchProxyConfig: async () => {
    const proxyConfig = await api.get("settings/proxy").json<ProxyConfig>();
    set({ proxyConfig, proxyTestResult: null });
  },

  updateProxyConfig: async (config) => {
    const proxyConfig = await api
      .put("settings/proxy", { json: config })
      .json<ProxyConfig>();
    set({ proxyConfig, proxyTestResult: null });
  },

  testProxyConfig: async (config) => {
    set({ proxyTesting: true, proxyTestResult: null });
    try {
      const proxyTestResult = await api
        .post("settings/proxy/test", { json: config })
        .json<ProxyTestResult>();
      set({ proxyTestResult });
    } finally {
      set({ proxyTesting: false });
    }
  },

  fetchSemanticScholarConfig: async () => {
    const semanticScholarConfig = await api
      .get("settings/semantic-scholar")
      .json<SemanticScholarConfig>();
    set({ semanticScholarConfig });
  },

  updateSemanticScholarConfig: async (config) => {
    const semanticScholarConfig = await api
      .put("settings/semantic-scholar", { json: config })
      .json<SemanticScholarConfig>();
    set({ semanticScholarConfig });
  },
}));
