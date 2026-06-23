import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as pdfjsLib from "pdfjs-dist";
import workerSrc from "pdfjs-dist/build/pdf.worker.mjs?url";
import { PdfToolbar } from "./PdfToolbar";
import { PdfThumbnailBar } from "./PdfThumbnailBar";
import type { NewPdfAnnotation, PdfAnnotation, PdfSearchResult } from "./pdfTypes";

pdfjsLib.GlobalWorkerOptions.workerSrc = workerSrc;

type PDFDocumentProxy = any;
type PDFPageProxy = any;
type TextItem = { str: string; transform: number[]; width: number; [key: string]: any };

type LoadedPage = {
  pageNumber: number;
  page: PDFPageProxy;
  text: string;
  items: TextItem[];
};

const COLORS = ["#fde047", "#86efac", "#93c5fd", "#f9a8d4", "#fdba74"];

function normalizeText(value: string) {
  return value.toLowerCase().replace(/\s+/g, " ");
}

function textMatches(value: string, query: string) {
  const q = normalizeText(query.trim());
  return Boolean(q) && normalizeText(value).includes(q);
}

function PageRender({
  loaded,
  scale,
  query,
  active,
  annotations,
  onAnnotationAdd,
}: {
  loaded: LoadedPage;
  scale: number;
  query: string;
  active: boolean;
  annotations: PdfAnnotation[];
  onAnnotationAdd: (annotation: NewPdfAnnotation) => Promise<void> | void;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const pageRef = useRef<HTMLDivElement | null>(null);
  const viewport = useMemo(() => loaded.page.getViewport({ scale }), [loaded.page, scale]);
  const pageAnnotations = annotations.filter((item) => item.page_number === loaded.pageNumber);

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context) return;
    const outputScale = window.devicePixelRatio || 1;
    canvas.width = Math.floor(viewport.width * outputScale);
    canvas.height = Math.floor(viewport.height * outputScale);
    canvas.style.width = viewport.width + "px";
    canvas.style.height = viewport.height + "px";
    context.setTransform(outputScale, 0, 0, outputScale, 0, 0);
    const task = loaded.page.render({ canvasContext: context, viewport });
    task.promise.catch(() => undefined);
    return () => task.cancel();
  }, [loaded.page, viewport]);

  const addAnnotationFromSelection = (color: string) => {
    const selection = window.getSelection();
    const pageElement = pageRef.current;
    if (!selection || selection.isCollapsed || !pageElement || selection.rangeCount === 0) return;
    const selectedText = selection.toString().trim();
    if (!selectedText) return;
    const pageRect = pageElement.getBoundingClientRect();
    const rects = Array.from(selection.getRangeAt(0).getClientRects())
      .map((rect) => ({
        left: (rect.left - pageRect.left) / pageRect.width,
        top: (rect.top - pageRect.top) / pageRect.height,
        width: rect.width / pageRect.width,
        height: rect.height / pageRect.height,
      }))
      .filter((rect) => rect.width > 0.002 && rect.height > 0.002);
    if (!rects.length) return;
    void onAnnotationAdd({
      page_number: loaded.pageNumber,
      rects,
      highlighted_text: selectedText,
      color,
      annotation_type: "highlight",
    });
    selection.removeAllRanges();
  };

  return (
    <div className="mb-6 flex justify-center" data-page-number={loaded.pageNumber}>
      <div ref={pageRef} className={("relative bg-white shadow " + (active ? "ring-2 ring-primary/40" : ""))} style={{ width: viewport.width, height: viewport.height }}>
        <canvas ref={canvasRef} className="absolute inset-0" />
        <div className="absolute inset-0 pointer-events-none">
          {pageAnnotations.flatMap((annotation) => annotation.rects.map((rect, index) => (
            <div
              key={annotation.id + "-" + index}
              title={annotation.note || annotation.highlighted_text}
              className="absolute rounded-[2px] mix-blend-multiply"
              style={{
                left: (rect.left * 100) + "%",
                top: (rect.top * 100) + "%",
                width: (rect.width * 100) + "%",
                height: (rect.height * 100) + "%",
                background: annotation.color || "#fde047",
                opacity: 0.45,
              }}
            />
          )))}
        </div>
        <div className="absolute inset-0 text-transparent" style={{ userSelect: "text" }}>
          {loaded.items.map((item, index) => {
            const tx = pdfjsLib.Util.transform(viewport.transform, item.transform);
            const fontHeight = Math.hypot(tx[2], tx[3]);
            const left = tx[4];
            const top = tx[5] - fontHeight;
            const width = Math.max(1, item.width * scale);
            const matched = textMatches(item.str, query);
            return (
              <span
                key={index}
                className={matched ? "bg-yellow-300/40 text-transparent" : "text-transparent"}
                style={{
                  position: "absolute",
                  left,
                  top,
                  fontSize: fontHeight + "px",
                  fontFamily: "sans-serif",
                  transformOrigin: "0 0",
                  whiteSpace: "pre",
                  width,
                  lineHeight: 1,
                }}
              >
                {item.str}
              </span>
            );
          })}
        </div>
        <div className="absolute left-2 top-2 rounded bg-background/90 px-2 py-1 text-[10px] text-muted-foreground shadow">p.{loaded.pageNumber}</div>
        <div className="absolute bottom-2 left-1/2 z-10 flex -translate-x-1/2 gap-1 rounded-md border border-border bg-background/95 p-1 shadow">
          {COLORS.map((color) => (
            <button key={color} onMouseDown={(event) => event.preventDefault()} onClick={() => addAnnotationFromSelection(color)} className="h-6 w-6 rounded border border-border" style={{ background: color }} title="Highlight selected text" />
          ))}
        </div>
      </div>
    </div>
  );
}

export function PdfViewer({
  pdfUrl,
  paperId,
  annotations,
  jumpToPage,
  onAnnotationAdd,
  onFallbackOpen,
}: {
  pdfUrl: string;
  paperId: string;
  annotations: PdfAnnotation[];
  jumpToPage?: number | null;
  onAnnotationAdd: (annotation: NewPdfAnnotation) => Promise<void> | void;
  onFallbackOpen: () => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null);
  const [pages, setPages] = useState<LoadedPage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [scale, setScale] = useState(1.2);
  const [currentPage, setCurrentPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeSearchIndex, setActiveSearchIndex] = useState(0);
  const [showThumbnails, setShowThumbnails] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    setPdf(null);
    setPages([]);
    setCurrentPage(1);
    pdfjsLib.getDocument({ url: pdfUrl }).promise
      .then(async (doc) => {
        if (cancelled) return;
        setPdf(doc);
        const loadedPages: LoadedPage[] = [];
        for (let pageNumber = 1; pageNumber <= doc.numPages; pageNumber += 1) {
          const page = await doc.getPage(pageNumber);
          const textContent = await page.getTextContent();
          const items = textContent.items.filter((item): item is TextItem => "str" in item);
          loadedPages.push({ pageNumber, page, items, text: items.map((item) => item.str).join(" ") });
          if (cancelled) return;
        }
        setPages(loadedPages);
      })
      .catch((err) => setError(String(err)))
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [pdfUrl]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const onScroll = () => {
      const containerTop = container.getBoundingClientRect().top;
      let bestPage = currentPage;
      let bestDistance = Number.POSITIVE_INFINITY;
      container.querySelectorAll<HTMLElement>("[data-page-number]").forEach((element) => {
        const page = Number(element.dataset.pageNumber || 1);
        const distance = Math.abs(element.getBoundingClientRect().top - containerTop - 80);
        if (distance < bestDistance) {
          bestDistance = distance;
          bestPage = page;
        }
      });
      setCurrentPage(bestPage);
    };
    container.addEventListener("scroll", onScroll, { passive: true });
    return () => container.removeEventListener("scroll", onScroll);
  }, [currentPage, pages.length]);

  const searchResults = useMemo<PdfSearchResult[]>(() => {
    const query = normalizeText(searchQuery.trim());
    if (!query) return [];
    return pages.flatMap((page) => {
      const text = normalizeText(page.text);
      const results: PdfSearchResult[] = [];
      let from = 0;
      while (true) {
        const index = text.indexOf(query, from);
        if (index < 0) break;
        results.push({ page: page.pageNumber, index, preview: page.text.slice(Math.max(0, index - 40), index + query.length + 80) });
        from = index + query.length;
      }
      return results;
    });
  }, [pages, searchQuery]);

  const goToPage = useCallback((page: number) => {
    const target = Math.min(Math.max(1, page), pdf?.numPages || 1);
    setCurrentPage(target);
    const selector = "[data-page-number=\"" + target + "\"]";
    const element = containerRef.current?.querySelector<HTMLElement>(selector);
    element?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [pdf?.numPages]);

  useEffect(() => {
    if (!jumpToPage) return;
    goToPage(jumpToPage);
  }, [goToPage, jumpToPage]);

  const goToSearchIndex = useCallback((index: number) => {
    if (!searchResults.length) return;
    const next = (index + searchResults.length) % searchResults.length;
    setActiveSearchIndex(next);
    goToPage(searchResults[next].page);
  }, [goToPage, searchResults]);

  useEffect(() => {
    if (!searchResults.length) {
      setActiveSearchIndex(0);
      return;
    }
    goToSearchIndex(0);
  }, [searchQuery]);

  const fitWidth = () => {
    const width = containerRef.current?.clientWidth || 900;
    const first = pages[0];
    if (!first) return;
    const viewport = first.page.getViewport({ scale: 1 });
    setScale(Math.max(0.5, Math.min(3, (width - 48) / viewport.width)));
  };

  const fitPage = () => {
    const container = containerRef.current;
    const first = pages[0];
    if (!container || !first) return;
    const viewport = first.page.getViewport({ scale: 1 });
    const byWidth = (container.clientWidth - 48) / viewport.width;
    const byHeight = (container.clientHeight - 48) / viewport.height;
    setScale(Math.max(0.4, Math.min(3, Math.min(byWidth, byHeight))));
  };

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-sm text-muted-foreground">
        <div>PDF.js failed to load this PDF.</div>
        <div className="max-w-lg text-center text-xs">{error}</div>
        <button onClick={onFallbackOpen} className="rounded-md border border-border px-3 py-2 text-xs hover:bg-muted">Open with browser viewer</button>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col bg-card">
      <PdfToolbar
        currentPage={currentPage}
        totalPages={pdf?.numPages || 0}
        scale={scale}
        searchQuery={searchQuery}
        searchResults={searchResults}
        activeSearchIndex={activeSearchIndex}
        showThumbnails={showThumbnails}
        onPageChange={goToPage}
        onZoomIn={() => setScale((value) => Math.min(4, value + 0.15))}
        onZoomOut={() => setScale((value) => Math.max(0.3, value - 0.15))}
        onFitWidth={fitWidth}
        onFitPage={fitPage}
        onSearchChange={setSearchQuery}
        onSearchPrev={() => goToSearchIndex(activeSearchIndex - 1)}
        onSearchNext={() => goToSearchIndex(activeSearchIndex + 1)}
        onToggleThumbnails={() => setShowThumbnails((value) => !value)}
      />
      <div className="flex min-h-0 flex-1">
        {showThumbnails && <PdfThumbnailBar pdf={pdf} totalPages={pdf?.numPages || 0} currentPage={currentPage} onPageClick={goToPage} />}
        <div ref={containerRef} className="min-h-0 flex-1 overflow-auto bg-muted/30 p-4">
          {loading ? (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">Loading PDF...</div>
          ) : pages.length ? (
            pages.map((page) => (
              <PageRender key={paperId + "-" + page.pageNumber + "-" + scale} loaded={page} scale={scale} query={searchQuery} active={page.pageNumber === currentPage} annotations={annotations} onAnnotationAdd={onAnnotationAdd} />
            ))
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">No PDF pages available.</div>
          )}
        </div>
      </div>
    </div>
  );
}
