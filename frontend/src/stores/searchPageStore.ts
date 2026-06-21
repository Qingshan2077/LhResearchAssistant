import { create } from "zustand";

const DEFAULT_SOURCES = ["arxiv", "semantic_scholar", "dblp"];

type ValueUpdater<T> = T | ((previous: T) => T);

interface SearchPageState {
  query: string;
  sources: string[];
  selectedIds: Set<string>;
  setQuery: (query: string) => void;
  setSources: (value: ValueUpdater<string[]>) => void;
  setSelectedIds: (value: ValueUpdater<Set<string>>) => void;
}

export const useSearchPageStore = create<SearchPageState>((set) => ({
  query: "",
  sources: [...DEFAULT_SOURCES],
  selectedIds: new Set<string>(),
  setQuery: (query) => set({ query }),
  setSources: (value) => set((state) => ({
    sources: typeof value === "function" ? value(state.sources) : value,
  })),
  setSelectedIds: (value) => set((state) => ({
    selectedIds: typeof value === "function" ? value(state.selectedIds) : value,
  })),
}));
