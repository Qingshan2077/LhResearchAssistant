import { Highlighter, Trash2 } from "lucide-react";
import type { PdfAnnotation } from "./pdfTypes";

export function AnnotationSummaryPanel({
  annotations,
  onJumpToPage,
  onDeleteAnnotation,
}: {
  annotations: PdfAnnotation[];
  onJumpToPage: (page: number) => void;
  onDeleteAnnotation: (id: string) => void;
}) {
  if (!annotations.length) {
    return (
      <div className="flex h-40 flex-col items-center justify-center rounded-lg border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
        <Highlighter size={22} className="mb-2" />
        No annotations yet. Select text in the PDF and choose a highlight color.
      </div>
    );
  }

  return (
    <div className="space-y-2 text-xs">
      {annotations.map((annotation) => (
        <div key={annotation.id} className="rounded-md border border-border p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <button onClick={() => onJumpToPage(annotation.page_number)} className="inline-flex items-center gap-1 font-medium text-primary hover:underline">
              <span className="h-3 w-3 rounded-sm" style={{ background: annotation.color }} />
              p.{annotation.page_number}
            </button>
            <button onClick={() => onDeleteAnnotation(annotation.id)} className="rounded p-1 text-muted-foreground hover:text-destructive" title="Delete annotation">
              <Trash2 size={13} />
            </button>
          </div>
          <div className="line-clamp-3 text-foreground">{annotation.highlighted_text}</div>
          {annotation.note && <div className="mt-2 rounded bg-muted/40 p-2 text-muted-foreground">{annotation.note}</div>}
        </div>
      ))}
    </div>
  );
}
