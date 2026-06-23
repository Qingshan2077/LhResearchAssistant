import ky from "ky";

// Dev: Vite proxy handles /api → 127.0.0.1:8787.
// Prod: connect directly to the bundled sidecar backend.
export const API_BASE = (
  import.meta.env.VITE_API_BASE ||
  (import.meta.env.PROD ? "http://127.0.0.1:8787/api/v1" : "/api/v1")
).replace(/\/$/, "");

export function apiUrl(path = ""): string {
  return `${API_BASE}/${path.replace(/^\//, "")}`;
}

export function websocketUrl(path: string): string {
  const normalizedPath = path.replace(/^\//, "");

  if (API_BASE.startsWith("http")) {
    const url = new URL(apiUrl(normalizedPath));
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    return url.toString();
  }

  // Vite serves the frontend in development; connect directly because its
  // HTTP proxy is not present in an installed Tauri application.
  return `ws://127.0.0.1:8787/api/v1/${normalizedPath}`;
}

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
  pdf_download_error: string;
  extracted_data: Record<string, unknown>;
  citation_verified: Array<Record<string, unknown>>;
  citation_data: string;
  citation_cached_at: string | null;
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
  source_errors: Record<string, string>;
};

export type PaperCategory = {
  name: string;
  paper_ids: string[];
};

export type CategorizeResponse = {
  groups: PaperCategory[];
  uncategorized: string[];
};

export type ProxyConfig = {
  enabled: boolean;
  url: string;
};

export type ProxyTestResult = {
  success: boolean;
  message: string;
  latency_ms: number;
};

export type SemanticScholarConfig = {
  api_key: string;
};

export type SocraticHistoryItem = {
  id: string;
  title: string;
  turn_count: number;
  message_count: number;
  layer: number;
  insights_count: number;
  has_summary: boolean;
  created_at: string;
  updated_at: string;
};

export type IdeaHistoryItem = {
  id: string;
  project_id: string | null;
  title: string;
  created_at: string;
  mode: string;
  paper_ids: string[];
  custom_prompt: string;
  domain_a: string;
  domain_b: string;
  evaluations_count: number;
};

export type IdeaHistoryDetail = IdeaHistoryItem & {
  generated_content: string;
  evaluations: Array<Record<string, unknown>>;
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
  last_test_at: string | null;
  last_test_success: boolean | null;
  last_test_latency: number;
};

export type UsageSummary = {
  calls_today: number;
  calls_week: number;
  calls_month: number;
  tokens_in_week: number;
  tokens_out_week: number;
  cache_hit_rate: number | null;
  cache_hit_tokens: number;
  cache_miss_tokens: number;
  estimated_cost: number;
  cost_by_model: Record<string, {
    total: number;
    breakdown: { cache_hit: number; cache_miss: number; output: number };
    currency: string;
  }>;
};

export type UsageByProvider = Array<{
  provider_name: string;
  model: string;
  calls: number;
  tokens_in: number;
  tokens_out: number;
  cache_hit_tokens: number;
  cache_miss_tokens: number;
}>;

export type UsageByFunction = Array<{
  function_name: string;
  calls: number;
  tokens_total: number;
  percentage: number;
}>;

export type UsageRecord = {
  id: string;
  timestamp: string;
  provider_name: string;
  model: string;
  function_name: string;
  tokens_in: number;
  tokens_out: number;
  duration_ms: number;
  status: string;
  cache_hit_tokens: number | null;
  cache_miss_tokens: number | null;
};

export type DataStats = {
  paper_count: number;
  chroma_count: number;
  writing_project_count: number;
  provider_count: number;
  cache_size_mb: number;
  db_size_mb: number;
  cache_path: string;
};

export type SystemInfo = {
  backend_version: string;
  python_version: string;
  db_path: string;
  cache_path: string;
  cache_size_mb: number;
  chroma_path: string;
  data_dir: string;
  cwd: string;
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

export type CitationGraphData = {
  paper: CitationGraphNode;
  references: CitationGraphNode[];
  citations: CitationGraphNode[];
  graph: {
    nodes: CitationGraphNode[];
    edges: Array<{ source: string; target: string; type: string }>;
  };
  error?: string;
};

export type CitationGraphNode = {
  id: string;
  title: string;
  label: string;
  year: number | null;
  authors?: string[];
  venue?: string;
  external_ids?: Record<string, string>;
  citation_count: number;
  url?: string;
  is_seed: boolean;
  group: "seed" | "reference" | "citation";
  local_id?: string;
  tags?: string[];
  notes?: string;
  read_status?: string;
};

export type ComparisonTable = {
  table: Array<{
    id: string;
    title: string;
    year: number | null;
    venue: string;
    values: Record<string, string>;
  }>;
  notes: string;
};
