import { create } from "zustand";

export type ChatMessage = {
  role: "system" | "user" | "assistant";
  content: string;
};

interface ChatStore {
  messages: ChatMessage[];
  streaming: boolean;
  error: string | null;
  sendMessage: (text: string, context?: string) => Promise<void>;
  clearMessages: () => void;
}

function wsUrl() {
  const apiBase = import.meta.env.VITE_API_BASE as string | undefined;
  if (apiBase?.startsWith("http")) {
    const url = new URL(apiBase);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.pathname = `${url.pathname.replace(/\/$/, "")}/ws`;
    return url.toString();
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  if (window.location.port === "1420") {
    return `${protocol}//localhost:8787/api/v1/ws`;
  }
  return `${protocol}//${window.location.host}/api/v1/ws`;
}

export const useChatStore = create<ChatStore>((set, get) => ({
  messages: [],
  streaming: false,
  error: null,

  sendMessage: async (text, context = "") => {
    const trimmed = text.trim();
    if (!trimmed || get().streaming) return;

    const userMessage: ChatMessage = { role: "user", content: trimmed };
    const assistantMessage: ChatMessage = { role: "assistant", content: "" };

    const visibleMessages = [...get().messages, userMessage];
    set({
      messages: [...visibleMessages, assistantMessage],
      streaming: true,
      error: null,
    });

    await new Promise<void>((resolve) => {
      const socket = new WebSocket(wsUrl());
      let finished = false;

      const finish = () => {
        if (finished) return;
        finished = true;
        socket.close();
        set({ streaming: false });
        resolve();
      };

      socket.onopen = () => {
        const payloadMessages: ChatMessage[] = context
          ? [{ role: "system", content: context }, ...visibleMessages]
          : visibleMessages;

        socket.send(JSON.stringify({
          type: "chat",
          messages: payloadMessages,
        }));
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "chunk") {
            set((state) => {
              const next = [...state.messages];
              const last = next[next.length - 1];
              if (last?.role === "assistant") {
                next[next.length - 1] = {
                  ...last,
                  content: last.content + data.content,
                };
              }
              return { messages: next };
            });
          } else if (data.type === "done") {
            finish();
          } else if (data.type === "error") {
            set({ error: data.message || "Chat failed" });
            finish();
          }
        } catch {
          set({ error: "Failed to parse chat response" });
          finish();
        }
      };

      socket.onerror = () => {
        set({ error: "WebSocket connection failed", streaming: false });
        resolve();
      };

      socket.onclose = () => {
        if (!finished) {
          set({ streaming: false });
          resolve();
        }
      };
    });
  },

  clearMessages: () => set({ messages: [], error: null }),
}));
