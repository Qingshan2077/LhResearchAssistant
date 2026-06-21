import { create } from "zustand";
import { api, type SocraticHistoryItem } from "../lib/api";

export type SocraticResearchPlan = {
  research_question?: string;
  methodology?: string;
  evidence_plan?: string;
  limitations?: string;
  significance?: string;
  insights?: string[];
  convergence?: Record<string, boolean>;
  [key: string]: unknown;
};

type SocraticHistoryDetail = {
  session_id: string;
  insights?: string[];
  summary: SocraticResearchPlan | null;
};

type SocraticIdeaBridgeState = {
  availableSessions: SocraticHistoryItem[];
  loading: boolean;
  error: string | null;
  selectedSessionId: string | null;
  selectedSessionSummary: SocraticResearchPlan | null;
  useSocraticContext: boolean;
  fetchSocraticSessions: (projectId?: string) => Promise<void>;
  selectSession: (sessionId: string) => Promise<void>;
  clearSelection: () => void;
  setUseSocraticContext: (use: boolean) => void;
  buildContextPrompt: () => string;
};

export const useSocraticIdeaBridgeStore = create<SocraticIdeaBridgeState>((set, get) => ({
  availableSessions: [],
  loading: false,
  error: null,
  selectedSessionId: null,
  selectedSessionSummary: null,
  useSocraticContext: false,

  fetchSocraticSessions: async (projectId = "default") => {
    set({ loading: true, error: null });
    try {
      const availableSessions = await api
        .get("ideas/socratic/history", { searchParams: { project_id: projectId } })
        .json<SocraticHistoryItem[]>();
      set({ availableSessions });
    } catch (error) {
      set({ availableSessions: [], error: String(error) });
    } finally {
      set({ loading: false });
    }
  },

  selectSession: async (sessionId) => {
    if (!sessionId) return;
    set({ loading: true, error: null, selectedSessionId: sessionId, selectedSessionSummary: null });
    try {
      const detail = await api
        .get(`ideas/socratic/history/${sessionId}`)
        .json<SocraticHistoryDetail>();
      const summary = detail.summary
        ? {
            ...detail.summary,
            insights:
              detail.summary.insights && detail.summary.insights.length > 0
                ? detail.summary.insights
                : detail.insights || [],
          }
        : null;
      set({ selectedSessionId: sessionId, selectedSessionSummary: summary });
    } catch (error) {
      set({ selectedSessionId: null, selectedSessionSummary: null, error: String(error) });
    } finally {
      set({ loading: false });
    }
  },

  clearSelection: () => set({ selectedSessionId: null, selectedSessionSummary: null, error: null }),

  setUseSocraticContext: (use) => {
    if (use) {
      set({ useSocraticContext: true, error: null });
      return;
    }
    set({
      useSocraticContext: false,
      selectedSessionId: null,
      selectedSessionSummary: null,
      error: null,
    });
  },

  buildContextPrompt: () => {
    const summary = get().selectedSessionSummary;
    if (!summary) return "";

    const sections = ["=== 来自 Socratic 引导讨论 ==="];
    if (summary.research_question?.trim()) {
      sections.push(`研究问题：\n${summary.research_question.trim()}`);
    }
    if (summary.methodology?.trim()) {
      sections.push(`方法论方向：\n${summary.methodology.trim()}`);
    }
    const insights = (summary.insights || []).map((value) => value.trim()).filter(Boolean);
    if (insights.length > 0) {
      sections.push(`关键洞见：\n${insights.map((value) => `- ${value}`).join("\n")}`);
    }
    if (summary.evidence_plan?.trim()) {
      sections.push(`证据计划：\n${summary.evidence_plan.trim()}`);
    }
    if (summary.significance?.trim()) {
      sections.push(`研究意义：\n${summary.significance.trim()}`);
    }
    return sections.length > 1 ? sections.join("\n\n") : "";
  },
}));