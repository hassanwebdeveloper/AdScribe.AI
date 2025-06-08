import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import { ChatProvider } from "@/contexts/ChatContext";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import PrerequisiteGuard from "@/components/PrerequisiteGuard";
import { Layout } from "@/components/ui/layout";
import Index from "./pages/Index";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Chat from "./pages/Chat";
import Settings from "./pages/Settings";
import AdAnalysis from "./pages/AdAnalysis";
import AdDetail from "./pages/AdDetail";
import Dashboard from "./pages/Dashboard";
import NotFound from "./pages/NotFound";
import SelectAdAccount from "./pages/SelectAdAccount";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <BrowserRouter>
        <AuthProvider>
          <ChatProvider>
            <Toaster />
            <Sonner />
            <Routes>
              <Route path="/" element={<Index />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              
              {/* Facebook OAuth callback routes */}
              <Route path="/auth/facebook/success" element={<Login />} />
              <Route path="/auth/facebook/error" element={<Login />} />
              
              {/* Ad account selection */}
              <Route path="/select-ad-account" element={<SelectAdAccount />} />
              
              <Route element={<ProtectedRoute />}>
                <Route path="/chat" element={
                  <PrerequisiteGuard pageName="Chat">
                    <Layout>
                      <Chat />
                    </Layout>
                  </PrerequisiteGuard>
                } />
                <Route path="/settings" element={
                  <Layout>
                    <Settings />
                  </Layout>
                } />
                <Route path="/ad-analysis" element={
                  <Layout>
                    <AdAnalysis />
                  </Layout>
                } />
                <Route path="/ad-detail/:id" element={
                  <Layout>
                    <AdDetail />
                  </Layout>
                } />
                <Route path="/dashboard" element={
                  <PrerequisiteGuard pageName="Dashboard">
                    <Layout>
                      <Dashboard />
                    </Layout>
                  </PrerequisiteGuard>
                } />
              </Route>
              
              <Route path="*" element={<NotFound />} />
            </Routes>
          </ChatProvider>
        </AuthProvider>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
