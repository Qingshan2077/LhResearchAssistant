export type PdfAnnotation = {
  id: string;
  paper_id: string;
  page_number: number;
  rects: PdfAnnotationRect[];
  highlighted_text: string;
  color: string;
  note: string;
  annotation_type: "highlight" | "underline" | "note";
  created_at: string;
  updated_at: string;
};

export type PdfAnnotationRect = {
  left: number;
  top: number;
  width: number;
  height: number;
};

export type NewPdfAnnotation = {
  page_number: number;
  rects: PdfAnnotationRect[];
  highlighted_text: string;
  color: string;
  note?: string;
  annotation_type: "highlight" | "underline" | "note";
};

export type PdfSearchResult = {
  page: number;
  index: number;
  preview: string;
};
