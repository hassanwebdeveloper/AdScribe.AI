import { createBrowserRouter, Navigate } from "react-router-dom";
import { lazy, Suspense } from "react";
import { FullPageLoader } from "@/components/ui/full-page-loader";

// Layout
import AppLayout from "@/layouts/AppLayout";

// Regular imports for frequently accessed pages
import DashboardPage from "@/pages/Dashboard";
import Index from "@/pages/Index";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import NotFound from "@/pages/NotFound";
import SelectAdAccount from "@/pages/SelectAdAccount";
import AdminLogin from "@/pages/AdminLogin";

// Lazy-loaded components
const RecommendationsPage = lazy(() => import("@/pages/RecommendationsPage"));
const AdMetricsPage = lazy(() => import("@/pages/AdMetricsPage"));
const PromptAdminPanel = lazy(() => import("@/pages/PromptAdminPanel"));

// Wrap lazy components with Suspense
const SuspenseWrapper = ({ children }: { children: React.ReactNode }) => (
  <Suspense fallback={<FullPageLoader />}>{children}</Suspense>
);

// Router configuration
const router = createBrowserRouter([
  {
    path: "/",
    element: <Navigate to="/app/dashboard" replace />,
  },
  {
    path: "/login",
    element: <Login />,
  },
  {
    path: "/register",
    element: <Register />,
  },
  
  // Facebook OAuth callback routes
  {
    path: "/auth/facebook/success",
    element: <Login />,
  },
  {
    path: "/auth/facebook/error",
    element: <Login />,
  },
  
  // Ad account selection
  {
    path: "/select-ad-account",
    element: <SelectAdAccount />,
  },
  
  // Admin Panel
  {
    path: "/admin/login",
    element: <AdminLogin />,
  },
  {
    path: "/admin/prompts",
    element: <SuspenseWrapper><PromptAdminPanel /></SuspenseWrapper>,
  },
  
  // Main app routes with AppLayout
  {
    path: "/app",
    element: <AppLayout />,
    children: [
      {
        path: "",
        element: <Navigate to="/app/dashboard" replace />,
      },
      {
        path: "dashboard",
        element: <DashboardPage />,
      },
      {
        path: "recommendations",
        element: <SuspenseWrapper><RecommendationsPage /></SuspenseWrapper>,
      },
      {
        path: "ad-metrics",
        element: <SuspenseWrapper><AdMetricsPage /></SuspenseWrapper>,
      },
    ],
  },
  
  {
    path: "*",
    element: <NotFound />,
  },
]);

export default router; 