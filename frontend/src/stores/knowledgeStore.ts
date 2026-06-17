import { create } from "zustand";
import { api, type GraphData, type MindMapData } from "../lib/api";

interface KnowledgeStore {
  graphData: GraphData | null;
  mindmapData: Record<string, MindMapData>;
  queryResult: string;
  querying: boolean;

  fetchGraph: (projectId: string) => Promise<void>;
  fetchMindMap: (paperId: string) => Promise<void>;
  query: (projectId: string, query: string) => Promise<void>;
  saveMindMap: (paperId: string, nodes: MindMapData["nodes"]) => Promise<void>;
}

export const useKnowledgeStore = create<KnowledgeStore>((set) => ({
  graphData: null,
  mindmapData: {},
  queryResult: "",
  querying: false,

  fetchGraph: async (projectId) => {
    try {
      const resp = await api
        .get(`knowledge/graph`, { searchParams: { project_id: projectId } })
        .json<GraphData>();
      set({ graphData: resp });
    } catch {
      // ignore
    }
  },

  fetchMindMap: async (paperId) => {
    try {
      const resp = await api.get(`knowledge/mindmap/${paperId}`).json<MindMapData>();
      set((s) => ({ mindmapData: { ...s.mindmapData, [paperId]: resp } }));
    } catch {
      // ignore
    }
  },

  query: async (projectId, query) => {
    set({ querying: true, queryResult: "" });
    try {
      const resp = await api
        .post("knowledge/query", { json: { project_id: projectId, query, top_k: 5 } })
        .json<{ answer: string; sources: Array<{ paper_id: string; title: string }>; context: string }>();
      const answer = resp.answer;
      const sourcesList = resp.sources
        .map((s) => `📄 ${s.title}`)
        .join("\n");
      set({ queryResult: `${answer}\n\n**Sources:**\n${sourcesList}`, querying: false });
    } catch {
      set({ queryResult: "Query failed.", querying: false });
    }
  },

  saveMindMap: async (paperId, nodes) => {
    await api.patch(`knowledge/mindmap/${paperId}`, { json: { nodes } });
    set((s) => ({
      mindmapData: { ...s.mindmapData, [paperId]: { nodes } },
    }));
  },
}));
