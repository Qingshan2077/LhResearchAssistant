import { NavLink } from "react-router-dom";
import {
  Search,
  Network,
  Lightbulb,
  FileText,
  ClipboardCheck,
  Settings,
  Moon,
  Sun,
} from "lucide-react";
import { useSettingsStore } from "../stores/settingsStore";
import clsx from "clsx";

const NAV_ITEMS = [
  { path: "/", icon: Search, label: "文献检索" },
  { path: "/knowledge", icon: Network, label: "知识库" },
  { path: "/ideas", icon: Lightbulb, label: "Idea 生成" },
  { path: "/write", icon: FileText, label: "论文写作" },
  { path: "/review", icon: ClipboardCheck, label: "审稿" },
];

export function Sidebar() {
  const { theme, toggleTheme } = useSettingsStore();
  const ThemeIcon = theme === "dark" ? Sun : Moon;

  return (
    <aside className="flex flex-col w-16 border-r border-border bg-card items-center py-4 gap-2 shrink-0">
      {/* Logo */}
      <div className="w-10 h-10 rounded-lg bg-primary flex items-center justify-center mb-4">
        <span className="text-primary-foreground font-bold text-sm">RA</span>
      </div>

      {/* 导航 */}
      <nav className="flex flex-col gap-1 flex-1">
        {NAV_ITEMS.map(({ path, icon: Icon, label }) => (
          <NavLink
            key={path}
            to={path}
            end={path === "/"}
            className={({ isActive }) =>
              clsx(
                "w-10 h-10 rounded-lg flex items-center justify-center transition-colors relative group",
                isActive
                  ? "bg-primary/15 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              )
            }
            title={label}
          >
            <Icon size={20} />
            <span className="absolute left-14 top-1/2 -translate-y-1/2 px-2 py-1 rounded-md bg-popover text-popover-foreground text-xs shadow-md opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-50 pointer-events-none">
              {label}
            </span>
          </NavLink>
        ))}
      </nav>

      {/* 主题切换 */}
      <button
        onClick={toggleTheme}
        className="w-10 h-10 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        title={theme === "dark" ? "切换亮色" : "切换暗色"}
      >
        <ThemeIcon size={18} />
      </button>
    </aside>
  );
}
