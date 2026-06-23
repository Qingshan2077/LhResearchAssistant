import { Routes, Route } from "react-router-dom";
import { useEffect, useState } from "react";
import { Layout } from "./components/Layout";
import SearchPage from "./routes/SearchPage";
import ReaderPage from "./routes/ReaderPage";
import KnowledgeBasePage from "./routes/KnowledgeBasePage";
import IdeaPage from "./routes/IdeaPage";
import IdeaSocraticPage from "./routes/IdeaSocraticPage";
import WritePage from "./routes/WritePage";
import ReviewPage from "./routes/ReviewPage";
import SettingsPage from "./routes/SettingsPage";
import LLMSettingsPage from "./routes/LLMSettingsPage";
import OnboardingPage from "./routes/OnboardingPage";
import { api } from "./lib/api";
import { useSettingsStore } from "./stores/settingsStore";

function App() {
  const theme = useSettingsStore((s) => s.theme);
  const language = useSettingsStore((s) => s.language);
  const [onboardingStatus, setOnboardingStatus] = useState<"loading" | "onboarded" | "not-onboarded">("loading");

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  }, [theme, language]);

  useEffect(() => {
    if (localStorage.getItem("research-assistant-onboarding-skipped") === "true") {
      setOnboardingStatus("onboarded");
      return;
    }
    api.get("settings/onboarding-status")
      .json<{ onboarded: boolean }>()
      .then((data) => setOnboardingStatus(data.onboarded ? "onboarded" : "not-onboarded"))
      .catch(() => setOnboardingStatus("onboarded"));
  }, []);

  const completeOnboarding = () => {
    localStorage.setItem("research-assistant-onboarding-skipped", "true");
    setOnboardingStatus("onboarded");
  };

  if (onboardingStatus === "loading") {
    return <div className="h-screen bg-background" />;
  }

  if (onboardingStatus === "not-onboarded") {
    return <OnboardingPage onComplete={completeOnboarding} />;
  }

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
        <Route path="llm-settings" element={<LLMSettingsPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}

export default App;
