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
import { t } from "../i18n";
import { useSettingsStore } from "../stores/settingsStore";
import clsx from "clsx";

export function Sidebar() {
  const { theme, toggleTheme, language } = useSettingsStore();
  const ThemeIcon = theme === "dark" ? Sun : Moon;
  const navItems = [
    { path: "/", icon: Search, label: t(language, "navSearch") },
    { path: "/knowledge", icon: Network, label: t(language, "navKnowledge") },
    { path: "/ideas", icon: Lightbulb, label: t(language, "navIdeas") },
    { path: "/write", icon: FileText, label: t(language, "navWrite") },
    { path: "/review", icon: ClipboardCheck, label: t(language, "navReview") },
    { path: "/settings", icon: Settings, label: t(language, "navSettings") },
  ];

  return (
    <aside className="flex w-16 shrink-0 flex-col items-center gap-2 border-r border-border bg-card py-4">
      <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-primary">
        <span className="text-sm font-bold text-primary-foreground">RA</span>
      </div>

      <nav className="flex flex-1 flex-col gap-1">
        {navItems.map(({ path, icon: Icon, label }) => (
          <NavLink
            key={path}
            to={path}
            end={path === "/"}
            className={({ isActive }) =>
              clsx(
                "group relative flex h-10 w-10 items-center justify-center rounded-lg transition-colors",
                isActive
                  ? "bg-primary/15 text-primary"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )
            }
            title={label}
          >
            <Icon size={20} />
            <span className="pointer-events-none absolute left-14 top-1/2 z-50 -translate-y-1/2 whitespace-nowrap rounded-md bg-popover px-2 py-1 text-xs text-popover-foreground opacity-0 shadow-md transition-opacity group-hover:opacity-100">
              {label}
            </span>
          </NavLink>
        ))}
      </nav>

      <button
        onClick={toggleTheme}
        className="flex h-10 w-10 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        title={theme === "dark" ? t(language, "switchLight") : t(language, "switchDark")}
      >
        <ThemeIcon size={18} />
      </button>
    </aside>
  );
}
