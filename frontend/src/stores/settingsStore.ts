import { create } from "zustand";
import {
  api,
  type DataStats,
  type LLMProvider,
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
}

export const useSettingsStore = create<SettingsStore>((set, get) => ({
  theme: "dark",
  language: getInitialLanguage(),
  providers: [],
  activeProviderId: null,
  usageSummary: null,
  usageByProvider: [],
  usageByFunction: [],
  recentUsage: [],
  dataStats: null,
  systemInfo: null,
  loadingUsage: false,
  loadingData: false,

  toggleTheme: () => {
    set((s) => {
      const next = s.theme === "dark" ? "light" : "dark";
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
}));
