import { create } from "zustand";
import { api, type Paper, type SearchResponse } from "../lib/api";

interface PaperStore {
  papers: Paper[];
  selectedPaperId: string | null;
  loading: boolean;
  searchQuery: string;
  totalCount: number;
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
  searchQuery: "",
  totalCount: 0,
  page: 1,
  pageSize: 20,

  search: async (query, sources = ["arxiv", "semantic_scholar", "dblp"]) => {
    set({ loading: true, searchQuery: query });
    try {
      const resp = await api
        .post("search", {
          json: { query, sources, max_results_per_source: 50, sort_by: "relevance" },
        })
        .json<SearchResponse>();
      set({
        papers: resp.papers,
        totalCount: resp.total_count,
        loading: false,
      });
    } catch {
      set({ loading: false });
    }
  },

  importPapers: async (projectId, paperIds) => {
    await api.post("search/import", {
      json: { project_id: projectId, paper_ids: paperIds },
    });
  },

  fetchPapers: async (projectId, params = {}) => {
    set({ loading: true });
    try {
      const searchParams = new URLSearchParams({
        project_id: projectId,
        page: String(get().page),
        page_size: String(get().pageSize),
        ...params,
      });
      const resp = await api.get(`papers?${searchParams}`).json<{ items: Paper[]; total: number }>();
      set({ papers: resp.items, totalCount: resp.total, loading: false });
    } catch {
      set({ loading: false });
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
