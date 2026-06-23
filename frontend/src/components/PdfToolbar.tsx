import { ChevronLeft, ChevronRight, Columns3, Minus, PanelLeft, Plus, Search, X } from "lucide-react";
import type { PdfPageTheme, PdfSearchResult } from "./pdfTypes";

export function PdfToolbar({
  currentPage,
  totalPages,
  scale,
  searchQuery,
  searchResults,
  activeSearchIndex,
  showThumbnails,
  pageTheme,
  onPageChange,
  onZoomIn,
  onZoomOut,
  onFitWidth,
  onFitPage,
  onSearchChange,
  onSearchPrev,
  onSearchNext,
  onToggleThumbnails,
  onPageThemeChange,
}: {
  currentPage: number;
  totalPages: number;
  scale: number;
  searchQuery: string;
  searchResults: PdfSearchResult[];
  activeSearchIndex: number;
  showThumbnails: boolean;
  pageTheme: PdfPageTheme;
  onPageChange: (page: number) => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFitWidth: () => void;
  onFitPage: () => void;
  onSearchChange: (query: string) => void;
  onSearchPrev: () => void;
  onSearchNext: () => void;
  onToggleThumbnails: () => void;
  onPageThemeChange: (theme: PdfPageTheme) => void;
}) {
  const searchCount = searchResults.length;
  const activeLabel = searchCount > 0 ? activeSearchIndex + 1 : 0;

  return (
    <div className="flex flex-nowrap items-center gap-2 overflow-x-auto whitespace-nowrap border-b border-border bg-muted/20 px-3 py-2 text-xs">
      <button onClick={onToggleThumbnails} className="rounded-md border border-border px-2 py-1 hover:bg-muted" title="Thumbnails">
        <PanelLeft size={14} className={showThumbnails ? "text-primary" : "text-muted-foreground"} />
      </button>
      <button onClick={onZoomOut} className="rounded-md border border-border px-2 py-1 hover:bg-muted" title="Zoom out">
        <Minus size={14} />
      </button>
      <div className="min-w-[54px] text-center text-muted-foreground">{Math.round(scale * 100)}%</div>
      <button onClick={onZoomIn} className="rounded-md border border-border px-2 py-1 hover:bg-muted" title="Zoom in">
        <Plus size={14} />
      </button>
      <button onClick={onFitWidth} className="rounded-md border border-border px-2 py-1 hover:bg-muted">Fit width</button>
      <button onClick={onFitPage} className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 hover:bg-muted">
        <Columns3 size={13} /> Fit page
      </button>
      <select
        value={pageTheme}
        onChange={(event) => onPageThemeChange(event.target.value as PdfPageTheme)}
        className="h-7 rounded-md border border-input bg-background px-2 text-muted-foreground outline-none"
        title="PDF page background"
      >
        <option value="white">白底</option>
        <option value="khaki">护眼黄</option>
        <option value="green">护眼绿</option>
        <option value="gray">灰底</option>
      </select>

      <div className="mx-1 h-5 w-px bg-border" />
      <button onClick={() => onPageChange(Math.max(1, currentPage - 1))} disabled={currentPage <= 1} className="rounded-md border border-border px-2 py-1 hover:bg-muted disabled:opacity-40">
        <ChevronLeft size={14} />
      </button>
      <input
        value={currentPage || 1}
        onChange={(event) => onPageChange(Number(event.target.value) || 1)}
        className="h-7 w-14 rounded-md border border-input bg-background px-2 text-center outline-none"
      />
      <span className="text-muted-foreground">/ {totalPages || "-"}</span>
      <button onClick={() => onPageChange(Math.min(totalPages || 1, currentPage + 1))} disabled={!totalPages || currentPage >= totalPages} className="rounded-md border border-border px-2 py-1 hover:bg-muted disabled:opacity-40">
        <ChevronRight size={14} />
      </button>

      <div className="ml-auto flex min-w-[260px] shrink-0 items-center gap-1 rounded-md border border-input bg-background px-2 py-1">
        <Search size={14} className="text-muted-foreground" />
        <input
          value={searchQuery}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Search in PDF..."
          className="min-w-0 flex-1 bg-transparent outline-none"
        />
        {searchQuery && <button onClick={() => onSearchChange("")} className="text-muted-foreground hover:text-foreground"><X size={13} /></button>}
      </div>
      <span className="min-w-[56px] text-muted-foreground">{activeLabel}/{searchCount}</span>
      <button onClick={onSearchPrev} disabled={!searchCount} className="rounded-md border border-border px-2 py-1 hover:bg-muted disabled:opacity-40">Prev</button>
      <button onClick={onSearchNext} disabled={!searchCount} className="rounded-md border border-border px-2 py-1 hover:bg-muted disabled:opacity-40">Next</button>
    </div>
  );
}
