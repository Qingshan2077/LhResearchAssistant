import { create } from "zustand";
import { api, type Paper, type SearchResponse } from "../lib/api";

interface PaperStore {
  papers: Paper[];
  selectedPaperId: string | null;
  loading: boolean;
  error: string | null;
  searchQuery: string;
  totalCount: number;
  sourceBreakdown: Record<string, number>;
  page: number;
  pageSize: number;

  search: (query: string, sources?: string[]) => Promise<void>;
  importPapers: (projectId: string, paperIds: string[]) => Promise<void>;
  fetchPapers: (projectId: string, params?: Record<string, unknown>) => Promise<void>;
  updatePaper: (id: string, data: Record<string, unknown>) => Promise<void>;
  deletePaper: (id: string) => Promise<void>;
  setSelected: (id: string | null) => void;
}

export const usePaperStore = create<PaperStore>((set, get) => ({
  papers: [],
  selectedPaperId: null,
  loading: false,
  error: null,
  searchQuery: "",
  totalCount: 0,
  sourceBreakdown: {},
  page: 1,
  pageSize: 20,

  search: async (query, sources = ["arxiv", "semantic_scholar", "dblp"]) => {
    set({
      loading: true,
      error: null,
      searchQuery: query,
      papers: [],
      totalCount: 0,
      sourceBreakdown: {},
    });
    try {
      const resp = await api
        .post("search", {
          json: { query, sources, max_results_per_source: 50, sort_by: "relevance" },
        })
        .json<SearchResponse>();
      set({
        papers: Array.isArray(resp.papers) ? resp.papers : [],
        totalCount: resp.total_count ?? resp.papers?.length ?? 0,
        sourceBreakdown: resp.source_breakdown ?? {},
        loading: false,
      });
    } catch (error) {
      set({
        loading: false,
        error: error instanceof Error ? error.message : "Search failed",
      });
    }
  },

  importPapers: async (projectId, paperIds) => {
    await api.post("search/import", {
      json: { project_id: projectId, paper_ids: paperIds },
    });
  },

  fetchPapers: async (projectId, params = {}) => {
    set({ loading: true, error: null });
    try {
      const searchParams = new URLSearchParams({
        project_id: projectId,
        page: String(get().page),
        page_size: String(get().pageSize),
        ...params,
      });
      const resp = await api.get(`papers?${searchParams}`).json<{ items: Paper[]; total: number }>();
      set({ papers: resp.items, totalCount: resp.total, loading: false });
    } catch (error) {
      set({
        loading: false,
        error: error instanceof Error ? error.message : "Failed to load papers",
      });
    }
  },

  updatePaper: async (id, data) => {
    await api.patch(`papers/${id}`, { json: data });
  },

  deletePaper: async (id) => {
    await api.delete(`papers/${id}`);
    set((s) => ({ papers: s.papers.filter((p) => p.id !== id) }));
  },

  setSelected: (id) => set({ selectedPaperId: id }),
}));
