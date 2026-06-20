import { useMemo, useState } from "react";
import { Bot, Loader2, Send, Trash2 } from "lucide-react";
import { t } from "../i18n";
import { useChatStore } from "../stores/chatStore";
import { useSettingsStore } from "../stores/settingsStore";

interface ChatPanelProps {
  paperContext?: {
    title: string;
    abstract: string;
    extractedData?: Record<string, unknown>;
  };
  defaultOpen?: boolean;
}

export function ChatPanel({ paperContext, defaultOpen = true }: ChatPanelProps) {
  const { messages, streaming, error, sendMessage, clearMessages } = useChatStore();
  const language = useSettingsStore((s) => s.language);
  const [open, setOpen] = useState(defaultOpen);
  const [input, setInput] = useState("");

  const context = useMemo(() => {
    if (!paperContext) return "";
    const sections = [
      "You are answering inside a research assistant app.",
      "Use the current paper as context when it is relevant.",
      `Current paper title: ${paperContext.title}`,
      `Current paper abstract: ${paperContext.abstract || "N/A"}`,
    ];
    if (paperContext.extractedData && Object.keys(paperContext.extractedData).length > 0) {
      sections.push(
        `Current paper extracted data (method components, datasets, metrics and other structured analysis):\n${JSON.stringify(paperContext.extractedData, null, 2)}`
      );
    }
    return sections.join("\n");
  }, [paperContext]);

  const submitMessage = async () => {
    const text = input.trim();
    if (!text || streaming) return;
    setInput("");
    await sendMessage(text, context);
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm hover:bg-muted"
      >
        <Bot size={16} />
        {t(language, "llmChat")}
      </button>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border bg-muted/30 px-3 py-2">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Bot size={16} />
          {t(language, "llmChat")}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={clearMessages}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
            title={t(language, "clearChat")}
          >
            <Trash2 size={14} />
          </button>
          <button
            onClick={() => setOpen(false)}
            className="rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            {t(language, "collapse")}
          </button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto p-3">
        {messages.length === 0 ? (
          <div className="flex h-full items-center justify-center text-center text-sm text-muted-foreground">
            {t(language, "chatEmpty")}
          </div>
        ) : (
          <div className="space-y-3">
            {messages.filter((m) => m.role !== "system").map((message, index) => (
              <div key={index} className={message.role === "user" ? "text-right" : "text-left"}>
                <div
                  className={
                    message.role === "user"
                      ? "inline-block max-w-[92%] rounded-lg bg-primary px-3 py-2 text-left text-sm text-primary-foreground"
                      : "inline-block max-w-[92%] rounded-lg bg-muted px-3 py-2 text-left text-sm"
                  }
                >
                  <div
                    className="prose prose-sm max-w-none dark:prose-invert"
                    dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content || "") }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {error && (
        <div className="border-t border-border px-3 py-2 text-xs text-destructive">
          {error}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submitMessage();
        }}
        className="flex gap-2 border-t border-border p-3"
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={t(language, "chatPlaceholder")}
          className="max-h-24 min-h-10 flex-1 resize-none rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submitMessage();
            }
          }}
        />
        <button
          type="submit"
          disabled={streaming || !input.trim()}
          className="inline-flex h-10 w-10 items-center justify-center rounded-md bg-primary text-primary-foreground disabled:opacity-50"
          title={t(language, "send")}
        >
          {streaming ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
        </button>
      </form>
    </div>
  );
}

function renderMarkdown(text: string): string {
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  return escaped
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/^# (.+)$/gm, "<h1>$1</h1>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`(.+?)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br/>");
}
