import { create } from "zustand";
import { api, websocketUrl, type SocraticHistoryItem } from "../lib/api";

export type SocraticMessage = {
  role: "user" | "assistant";
  content: string;
  type?: string;
};

export type ResearchPlan = {
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
  title: string;
  messages: SocraticMessage[];
  layer: number;
  layer_name: string;
  insights: string[];
  convergence: Record<string, boolean>;
  turn_count: number;
  intent: string;
  is_active: boolean;
  summary: ResearchPlan | null;
};

interface SocraticState {
  sessionId: string | null;
  socket: WebSocket | null;
  messages: SocraticMessage[];
  currentLayer: number;
  layerName: string;
  insights: string[];
  convergence: Record<string, boolean>;
  turnCount: number;
  isActive: boolean;
  historyView: boolean;
  connecting: boolean;
  historyLoading: boolean;
  error: string | null;
  summary: ResearchPlan | null;
  historyList: SocraticHistoryItem[];
  createSession: (projectId: string, initialMessage?: string) => Promise<void>;
  sendMessage: (text: string) => Promise<void>;
  getSummary: () => Promise<ResearchPlan>;
  saveSession: (endSession?: boolean, releaseSession?: boolean) => Promise<void>;
  fetchHistory: (projectId?: string) => Promise<void>;
  loadHistory: (sessionId: string) => Promise<void>;
  deleteHistory: (sessionId: string) => Promise<void>;
  closeSession: (endSession?: boolean) => Promise<void>;
  resetSession: () => void;
}

const EMPTY_CONVERGENCE = { s1: false, s2: false, s3: false, s4: false, s5: false };

function socraticWsUrl(sessionId: string) {
  return websocketUrl(`ideas/socratic/${sessionId}`);
}

export const useSocraticStore = create<SocraticState>((set, get) => ({
  sessionId: null,
  socket: null,
  messages: [],
  currentLayer: 1,
  layerName: "Problem Framing",
  insights: [],
  convergence: { ...EMPTY_CONVERGENCE },
  turnCount: 0,
  isActive: false,
  historyView: false,
  connecting: false,
  historyLoading: false,
  error: null,
  summary: null,
  historyList: [],

  createSession: async (projectId, initialMessage = "") => {
    if (get().sessionId && get().isActive) await get().saveSession(true, true);
    get().socket?.close();
    set({
      connecting: true,
      error: null,
      messages: [],
      summary: null,
      historyView: false,
      currentLayer: 1,
      layerName: "Problem Framing",
      insights: [],
      convergence: { ...EMPTY_CONVERGENCE },
      turnCount: 0,
    });
    try {
      const resp = await api
        .post("ideas/socratic/create", {
          json: { project_id: projectId, initial_message: initialMessage },
        })
        .json<{ session_id: string }>();
      const socket = new WebSocket(socraticWsUrl(resp.session_id));

      socket.onopen = () => {
        const trimmed = initialMessage.trim();
        if (!trimmed) return;
        set((state) => ({ messages: [...state.messages, { role: "user", content: trimmed }] }));
        socket.send(JSON.stringify({ message: trimmed }));
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "ready") {
            set((state) => ({
              messages: [...state.messages, { role: "assistant", content: data.content || "Socratic Mentor 已连接。", type: "ready" }],
              currentLayer: data.layer || 1,
              insights: data.insights || [],
              convergence: data.convergence || get().convergence,
              turnCount: data.turn_count || 0,
              isActive: data.is_active ?? true,
              connecting: false,
            }));
            return;
          }
          if (data.type === "error") {
            set({ error: data.content || "Socratic session error", connecting: false });
            return;
          }
          set((state) => ({
            messages: [...state.messages, { role: "assistant", content: data.content || "", type: data.type }],
            currentLayer: data.layer || state.currentLayer,
            layerName: data.layer_name || state.layerName,
            insights: data.insights || state.insights,
            convergence: data.convergence || state.convergence,
            turnCount: data.turn_count || state.turnCount,
            isActive: data.is_active ?? state.isActive,
            summary: data.summary || state.summary,
          }));
          if (data.type === "converged") void get().fetchHistory();
        } catch {
          set({ error: "Failed to parse Socratic response" });
        }
      };

      socket.onerror = () => set({ error: "WebSocket connection failed", connecting: false });
      socket.onclose = () => set((state) => ({
        isActive: false,
        connecting: false,
        socket: state.socket === socket ? null : state.socket,
      }));

      set({ sessionId: resp.session_id, socket, isActive: true });
    } catch (error) {
      set({ error: String(error), connecting: false });
    }
  },

  sendMessage: async (text) => {
    const trimmed = text.trim();
    const socket = get().socket;
    if (!trimmed || !socket || socket.readyState !== WebSocket.OPEN) return;
    set((state) => ({ messages: [...state.messages, { role: "user", content: trimmed }] }));
    socket.send(JSON.stringify({ message: trimmed }));
  },

  getSummary: async () => {
    const sessionId = get().sessionId;
    if (!sessionId) return {};
    const summary = await api.get(`ideas/socratic/${sessionId}/summary`).json<ResearchPlan>();
    set({ summary });
    await get().fetchHistory();
    return summary;
  },

  saveSession: async (endSession = false, releaseSession = false) => {
    const sessionId = get().sessionId;
    if (!sessionId || get().historyView) return;
    await api.post(`ideas/socratic/${sessionId}/save`, { json: { end_session: endSession, release_session: releaseSession } });
    if (endSession) set({ isActive: false });
    await get().fetchHistory();
  },

  fetchHistory: async (projectId = "default") => {
    set({ historyLoading: true });
    try {
      const historyList = await api
        .get("ideas/socratic/history", { searchParams: { project_id: projectId } })
        .json<SocraticHistoryItem[]>();
      set({ historyList });
    } catch (error) {
      set({ error: String(error) });
    } finally {
      set({ historyLoading: false });
    }
  },

  loadHistory: async (sessionId) => {
    if (get().sessionId && get().isActive && !get().historyView) await get().saveSession(true, true);
    get().socket?.close();
    set({ historyLoading: true, error: null });
    try {
      const detail = await api
        .get(`ideas/socratic/history/${sessionId}`)
        .json<SocraticHistoryDetail>();
      set({
        sessionId: detail.session_id,
        socket: null,
        messages: detail.messages || [],
        currentLayer: detail.layer || 1,
        layerName: detail.layer_name || "Problem Framing",
        insights: detail.insights || [],
        convergence: detail.convergence || { ...EMPTY_CONVERGENCE },
        turnCount: detail.turn_count || 0,
        isActive: false,
        historyView: true,
        summary: detail.summary,
      });
    } finally {
      set({ historyLoading: false });
    }
  },

  deleteHistory: async (sessionId) => {
    await api.delete(`ideas/socratic/history/${sessionId}`);
    if (get().sessionId === sessionId) get().resetSession();
    await get().fetchHistory();
  },

  closeSession: async (endSession = true) => {
    if (get().sessionId && get().isActive && !get().historyView) {
      try {
        await get().saveSession(endSession, endSession);
      } catch (error) {
        set({ error: String(error) });
      }
    }
    get().socket?.close();
    set({ socket: null, isActive: false });
  },

  resetSession: () => {
    get().socket?.close();
    set({
      sessionId: null,
      socket: null,
      messages: [],
      currentLayer: 1,
      layerName: "Problem Framing",
      insights: [],
      convergence: { ...EMPTY_CONVERGENCE },
      turnCount: 0,
      isActive: false,
      historyView: false,
      connecting: false,
      error: null,
      summary: null,
    });
  },
}));
