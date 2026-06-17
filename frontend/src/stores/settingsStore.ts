import { create } from "zustand";
import { api, type LLMProvider } from "../lib/api";

interface SettingsStore {
  theme: "dark" | "light";
  providers: LLMProvider[];
  activeProviderId: string | null;

  toggleTheme: () => void;
  fetchProviders: () => Promise<void>;
  addProvider: (p: Partial<LLMProvider>) => Promise<void>;
  removeProvider: (id: string) => Promise<void>;
  testProvider: (id: string) => Promise<{ success: boolean; latency_ms: number }>;
}

export const useSettingsStore = create<SettingsStore>((set, get) => ({
  theme: "dark",
  providers: [],
  activeProviderId: null,

  toggleTheme: () => {
    set((s) => {
      const next = s.theme === "dark" ? "light" : "dark";
      document.documentElement.classList.toggle("dark", next === "dark");
      return { theme: next };
    });
  },

  fetchProviders: async () => {
    try {
      const providers = await api.get("settings/providers").json<LLMProvider[]>();
      set({ providers });
      const active = providers.find((p) => p.is_active);
      if (active) set({ activeProviderId: active.id });
    } catch {
      // ignore
    }
  },

  addProvider: async (p) => {
    await api.post("settings/providers", { json: p });
    await get().fetchProviders();
  },

  removeProvider: async (id) => {
    await api.delete(`settings/providers/${id}`);
    await get().fetchProviders();
  },

  testProvider: async (id) => {
    const resp = await api
      .post("settings/providers/test", { json: { provider_id: id } })
      .json<{ success: boolean; latency_ms: number }>();
    return resp;
  },
}));
