import { useEffect, useRef, useState } from "react";
type PDFDocumentProxy = any;

function PdfThumbnail({ pdf, pageNumber, active, onClick }: { pdf: PDFDocumentProxy; pageNumber: number; active: boolean; onClick: () => void }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setFailed(false);
    pdf.getPage(pageNumber).then((page: any) => {
      if (cancelled || !canvasRef.current) return;
      const viewport = page.getViewport({ scale: 0.18 });
      const canvas = canvasRef.current;
      const context = canvas.getContext("2d");
      if (!context) return;
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      return page.render({ canvasContext: context, viewport }).promise;
    }).catch(() => setFailed(true));
    return () => { cancelled = true; };
  }, [pdf, pageNumber]);

  return (
    <button onClick={onClick} className={
      "mb-2 w-full rounded-md border p-1 text-left text-[10px] transition " +
      (active ? "border-primary bg-primary/10" : "border-border hover:bg-muted")
    }>
      {failed ? <div className="flex h-24 items-center justify-center text-muted-foreground">p.{pageNumber}</div> : <canvas ref={canvasRef} className="mx-auto max-w-full bg-white" />}
      <div className="mt-1 text-center text-muted-foreground">{pageNumber}</div>
    </button>
  );
}

export function PdfThumbnailBar({ pdf, totalPages, currentPage, onPageClick }: { pdf: PDFDocumentProxy | null; totalPages: number; currentPage: number; onPageClick: (page: number) => void }) {
  if (!pdf || !totalPages) return null;
  return (
    <aside className="w-28 shrink-0 overflow-auto border-r border-border bg-muted/10 p-2">
      {Array.from({ length: totalPages }, (_, index) => index + 1).map((page) => (
        <PdfThumbnail key={page} pdf={pdf} pageNumber={page} active={page === currentPage} onClick={() => onPageClick(page)} />
      ))}
    </aside>
  );
}
