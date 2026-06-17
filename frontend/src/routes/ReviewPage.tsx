import { ClipboardCheck, Construction } from "lucide-react";

export default function ReviewPage() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
      <Construction size={64} className="mb-4 opacity-30" />
      <div className="text-center max-w-md">
        <h2 className="text-xl font-semibold mb-2">审稿与选刊</h2>
        <p className="text-sm">
          此功能将在 Phase 3 实现。
          <br />
          功能包括：选刊推荐（CCF 列表）、格式检查、模拟审稿、
          Cover Letter 和 Rebuttal Letter 生成。
        </p>
      </div>
    </div>
  );
}
