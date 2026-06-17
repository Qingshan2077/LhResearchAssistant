import { Lightbulb, Construction } from "lucide-react";

export default function IdeaPage() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
      <Construction size={64} className="mb-4 opacity-30" />
      <div className="text-center max-w-md">
        <h2 className="text-xl font-semibold mb-2">Idea 生成</h2>
        <p className="text-sm">
          此功能将在 Phase 2 实现。
          <br />
          功能包括：基于文献综述的 Gap 分析、跨领域 Idea 迁移、
          多维度的可行性评估（新颖性/可实现性/成本/风险）。
        </p>
      </div>
    </div>
  );
}
