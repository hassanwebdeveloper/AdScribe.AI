import { createBrowserRouter, Navigate } from "react-router-dom";
import { lazy, Suspense } from "react";
import { FullPageLoader } from "@/components/ui/full-page-loader";

// Layout
import AppLayout from "@/layouts/AppLayout";
import AuthLayout from "@/layouts/AuthLayout";

// Auth
import LoginPage from "@/pages/auth/LoginPage";
import RegisterPage from "@/pages/auth/RegisterPage";
import ForgotPasswordPage from "@/pages/auth/ForgotPasswordPage";
import ResetPasswordPage from "@/pages/auth/ResetPasswordPage";

// Regular imports for frequently accessed pages
import DashboardPage from "@/pages/DashboardPage";

// Lazy-loaded components
const AccountPage = lazy(() => import("@/pages/AccountPage"));
const AdAccountsPage = lazy(() => import("@/pages/AdAccountsPage"));
const ContentAnalysisPage = lazy(() => import("@/pages/ContentAnalysisPage"));
const ContentArchivesPage = lazy(() => import("@/pages/ContentArchivesPage"));
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
    path: "/auth",
    element: <AuthLayout />,
    children: [
      {
        path: "",
        element: <Navigate to="/auth/login" replace />,
      },
      {
        path: "login",
        element: <LoginPage />,
      },
      {
        path: "register",
        element: <RegisterPage />,
      },
      {
        path: "forgot-password",
        element: <ForgotPasswordPage />,
      },
      {
        path: "reset-password",
        element: <ResetPasswordPage />,
      },
    ],
  },
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
        path: "account",
        element: <SuspenseWrapper><AccountPage /></SuspenseWrapper>,
      },
      {
        path: "ad-accounts",
        element: <SuspenseWrapper><AdAccountsPage /></SuspenseWrapper>,
      },
      {
        path: "content-analysis",
        element: <SuspenseWrapper><ContentAnalysisPage /></SuspenseWrapper>,
      },
      {
        path: "content-archives",
        element: <SuspenseWrapper><ContentArchivesPage /></SuspenseWrapper>,
      },
      {
        path: "ad-metrics",
        element: <SuspenseWrapper><AdMetricsPage /></SuspenseWrapper>,
      },
    ],
  },
  {
    path: "/admin/prompts",
    element: <SuspenseWrapper><PromptAdminPanel /></SuspenseWrapper>,
  },
  {
    path: "*",
    element: <Navigate to="/app/dashboard" replace />,
  },
]);

export default router; 