import { create } from "zustand";
import { api, type CategorizeResponse, type Paper, type PaperCategory } from "../lib/api";

const DEFAULT_SOURCES = ["arxiv", "semantic_scholar", "dblp"];
let categorizeGeneration = 0;

type ValueUpdater<T> = T | ((previous: T) => T);

interface SearchPageState {
  query: string;
  sources: string[];
  selectedIds: Set<string>;
  categories: PaperCategory[];
  uncategorizedIds: string[];
  activeCategory: string | null;
  categorizing: boolean;
  categorizationEnabled: boolean;
  yearRange: [number, number] | null;
  sourceFilter: string | null;
  textFilter: string;
  setQuery: (query: string) => void;
  setSources: (value: ValueUpdater<string[]>) => void;
  setSelectedIds: (value: ValueUpdater<Set<string>>) => void;
  categorizeResults: (papers: Array<Pick<Paper, "id" | "title">>) => Promise<void>;
  setActiveCategory: (name: string | null) => void;
  setYearRange: (range: [number, number] | null) => void;
  setSourceFilter: (source: string | null) => void;
  setTextFilter: (text: string) => void;
  setCategorizationEnabled: (enabled: boolean) => void;
  clearFilters: () => void;
  resetResultView: () => void;
}

export const useSearchPageStore = create<SearchPageState>((set) => ({
  query: "",
  sources: [...DEFAULT_SOURCES],
  selectedIds: new Set<string>(),
  categories: [],
  uncategorizedIds: [],
  activeCategory: null,
  categorizing: false,
  categorizationEnabled: true,
  yearRange: null,
  sourceFilter: null,
  textFilter: "",

  setQuery: (query) => set({ query }),
  setSources: (value) => set((state) => ({
    sources: typeof value === "function" ? value(state.sources) : value,
  })),
  setSelectedIds: (value) => set((state) => ({
    selectedIds: typeof value === "function" ? value(state.selectedIds) : value,
  })),

  categorizeResults: async (papers) => {
    const requestGeneration = ++categorizeGeneration;
    const snapshot = papers
      .filter((paper) => paper.id && paper.title.trim())
      .slice(0, 200)
      .map((paper) => ({ id: paper.id, title: paper.title.slice(0, 1000) }));
    if (snapshot.length < 2) {
      set({ categories: [], uncategorizedIds: [], activeCategory: null, categorizing: false });
      return;
    }

    set({ categorizing: true, categories: [], uncategorizedIds: [], activeCategory: null });
    try {
      const response = await api
        .post("search/categorize", { json: { papers: snapshot } })
        .json<CategorizeResponse>();
      if (requestGeneration !== categorizeGeneration) return;

      const validIds = new Set(snapshot.map((paper) => paper.id));
      const assigned = new Set<string>();
      const categories = (response.groups || [])
        .slice(0, 5)
        .map((group) => ({
          name: String(group.name || "").trim().slice(0, 32),
          paper_ids: (group.paper_ids || []).filter((id) => {
            if (!validIds.has(id) || assigned.has(id)) return false;
            assigned.add(id);
            return true;
          }),
        }))
        .filter((group) => group.name && group.paper_ids.length > 0);
      const uncategorizedIds = snapshot
        .map((paper) => paper.id)
        .filter((id) => !assigned.has(id));
      set({ categories, uncategorizedIds });
    } catch {
      if (requestGeneration === categorizeGeneration) {
        set({ categories: [], uncategorizedIds: [], activeCategory: null });
      }
    } finally {
      if (requestGeneration === categorizeGeneration) set({ categorizing: false });
    }
  },

  setActiveCategory: (activeCategory) => set({ activeCategory }),
  setYearRange: (yearRange) => set({ yearRange }),
  setSourceFilter: (sourceFilter) => set({ sourceFilter }),
  setTextFilter: (textFilter) => set({ textFilter }),
  setCategorizationEnabled: (categorizationEnabled) => {
    if (!categorizationEnabled) {
      categorizeGeneration += 1;
      set({
        categorizationEnabled: false,
        categorizing: false,
        categories: [],
        uncategorizedIds: [],
        activeCategory: null,
      });
      return;
    }
    set({ categorizationEnabled: true });
  },
  clearFilters: () => set({
    activeCategory: null,
    yearRange: null,
    sourceFilter: null,
    textFilter: "",
  }),
  resetResultView: () => {
    categorizeGeneration += 1;
    set({
      categories: [],
      uncategorizedIds: [],
      activeCategory: null,
      categorizing: false,
      yearRange: null,
      sourceFilter: null,
      textFilter: "",
    });
  },
}));
