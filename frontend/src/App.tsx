import { Routes, Route } from "react-router-dom";
import { useEffect } from "react";
import { Layout } from "./components/Layout";
import SearchPage from "./routes/SearchPage";
import ReaderPage from "./routes/ReaderPage";
import KnowledgeBasePage from "./routes/KnowledgeBasePage";
import IdeaPage from "./routes/IdeaPage";
import IdeaSocraticPage from "./routes/IdeaSocraticPage";
import WritePage from "./routes/WritePage";
import ReviewPage from "./routes/ReviewPage";
import SettingsPage from "./routes/SettingsPage";
import { useSettingsStore } from "./stores/settingsStore";

function App() {
  const theme = useSettingsStore((s) => s.theme);
  const language = useSettingsStore((s) => s.language);

  useEffect(() => {
    // 应用主题
    document.documentElement.classList.toggle("dark", theme === "dark");
    document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  }, [theme, language]);

  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<SearchPage />} />
        <Route path="papers/:id" element={<ReaderPage />} />
        <Route path="knowledge" element={<KnowledgeBasePage />} />
        <Route path="ideas" element={<IdeaPage />} />
        <Route path="ideas/socratic" element={<IdeaSocraticPage />} />
        <Route path="write" element={<WritePage />} />
        <Route path="review" element={<ReviewPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}

export default App;
