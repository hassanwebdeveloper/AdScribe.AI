import { ReactNode } from "react";
import { Header } from "./header";
import AnalysisSettingsPanel from "@/components/chat/AnalysisSettingsPanel";
import { useChat } from "@/contexts/ChatContext";

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const { toggleAnalysisPanel, isAnalysisPanelOpen } = useChat();
  
  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <Header />
      <main className="flex-1 overflow-hidden">
        {children}
      </main>
      <AnalysisSettingsPanel isOpen={isAnalysisPanelOpen} togglePanel={toggleAnalysisPanel} />
    </div>
  );
} 