import { FileText, Construction } from "lucide-react";

export default function WritePage() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
      <Construction size={64} className="mb-4 opacity-30" />
      <div className="text-center max-w-md">
        <h2 className="text-xl font-semibold mb-2">论文写作</h2>
        <p className="text-sm">
          此功能将在 Phase 3 实现。
          <br />
          功能包括：引导式写作 Agent、中英文学术润色、BibTeX 管理、
          LaTeX 模板管理。编辑调用外部编辑器（VS Code / TeXstudio）。
        </p>
      </div>
    </div>
  );
}
