import { create } from "zustand";
import { api, websocketUrl } from "../lib/api";

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
  connecting: boolean;
  error: string | null;
  summary: ResearchPlan | null;
  createSession: (projectId: string, initialMessage?: string) => Promise<void>;
  sendMessage: (text: string) => Promise<void>;
  getSummary: () => Promise<ResearchPlan>;
  closeSession: () => void;
}

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
  convergence: { s1: false, s2: false, s3: false, s4: false, s5: false },
  turnCount: 0,
  isActive: false,
  connecting: false,
  error: null,
  summary: null,

  createSession: async (projectId, initialMessage = "") => {
    get().socket?.close();
    set({ connecting: true, error: null, messages: [], summary: null });
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
        } catch {
          set({ error: "Failed to parse Socratic response" });
        }
      };

      socket.onerror = () => set({ error: "WebSocket connection failed", connecting: false });
      socket.onclose = () => set((state) => ({ isActive: false, connecting: false, socket: state.socket === socket ? null : state.socket }));

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
    return summary;
  },

  closeSession: () => {
    get().socket?.close();
    set({ socket: null, isActive: false });
  },
}));
