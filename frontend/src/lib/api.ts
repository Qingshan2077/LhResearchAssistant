import ky from "ky";

const API_BASE = import.meta.env.VITE_API_BASE || "/api/v1";

export const api = ky.create({
  prefixUrl: API_BASE,
  timeout: 60000,
  headers: {
    "Content-Type": "application/json",
  },
});

export const apiForm = ky.create({
  prefixUrl: API_BASE,
  timeout: 120000,
});

export type Paper = {
  id: string;
  project_id: string | null;
  title: string;
  authors: string[];
  abstract: string;
  year: number | null;
  venue: string;
  paper_type: string;
  doi: string;
  arxiv_id: string;
  source: string;
  citation_count: number;
  keywords: string[];
  url: string;
  pdf_url: string;
  pdf_path: string;
  extracted_data: Record<string, unknown>;
  citation_verified: Array<Record<string, unknown>>;
  tags: string[];
  notes: string;
  read_status: string;
  rating: number;
  is_new: boolean;
  created_at: string;
  updated_at: string;
};

export type SearchResponse = {
  papers: Paper[];
  total_count: number;
  source_breakdown: Record<string, number>;
};

export type LLMProvider = {
  id: string;
  name: string;
  display_name: string;
  api_key: string;
  base_url: string;
  default_model: string;
  is_active: boolean;
  priority: number;
  max_tokens: number;
  temperature: number;
};

export type GraphData = {
  nodes: Array<{
    id: string;
    type: string;
    label: string;
    group: string;
    data?: Record<string, unknown>;
  }>;
  edges: Array<{
    source: string;
    target: string;
    type: string;
    label?: string;
    data?: Record<string, unknown>;
  }>;
};

export type MindMapData = {
  nodes: Array<{
    id: string;
    paper_id: string;
    parent_id: string | null;
    label: string;
    node_type: string;
    content: string;
    position: { x: number; y: number };
  }>;
};
