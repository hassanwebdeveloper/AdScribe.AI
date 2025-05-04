import { useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import {
  LayoutDashboard,
  FileText,
  Archive,
  Facebook,
  User,
  Menu,
  X,
  BarChart3,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";

// Navigation items for the sidebar
const NAV_ITEMS = [
  {
    title: "Dashboard",
    href: "/app/dashboard",
    icon: <LayoutDashboard className="h-5 w-5" />,
    variant: "default",
  },
  {
    title: "Ad Accounts",
    href: "/app/ad-accounts",
    icon: <Facebook className="h-5 w-5" />,
    variant: "ghost",
  },
  {
    title: "Ad Metrics",
    href: "/app/ad-metrics",
    icon: <BarChart3 className="h-5 w-5" />,
    variant: "ghost",
  },
  {
    title: "Content Analysis",
    href: "/app/content-analysis",
    icon: <FileText className="h-5 w-5" />,
    variant: "ghost",
  },
  {
    title: "Content Archives",
    href: "/app/content-archives",
    icon: <Archive className="h-5 w-5" />,
    variant: "ghost",
  },
];

const AppLayout = () => {
  const { user, logout, loading } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!loading && !user) {
      navigate("/auth/login");
    }
  }, [user, loading, navigate]);

  // Handle logout
  const handleLogout = async () => {
    await logout();
    navigate("/auth/login");
  };

  // Get user initials for avatar
  const getUserInitials = () => {
    if (!user?.name) return "US";
    const names = user.name.split(" ");
    if (names.length === 1) return names[0].substring(0, 2).toUpperCase();
    return (names[0][0] + names[names.length - 1][0]).toUpperCase();
  };

  // Toggle sidebar on desktop
  const toggleSidebar = () => {
    setSidebarOpen(!sidebarOpen);
  };

  // Toggle mobile menu
  const toggleMobileMenu = () => {
    setMobileMenuOpen(!mobileMenuOpen);
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="space-y-2">
          <Skeleton className="h-12 w-12 rounded-full" />
          <Skeleton className="h-4 w-[250px]" />
          <Skeleton className="h-4 w-[200px]" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-background">
      {/* Desktop Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex h-full flex-col border-r bg-card transition-all duration-300 ease-in-out lg:relative ${
          sidebarOpen ? "w-64" : "w-20"
        }`}
      >
        <div className="flex items-center justify-between border-b px-6 py-4">
          <Link to="/app/dashboard" className="flex items-center gap-3">
            {sidebarOpen ? (
              <h1 className="text-xl font-bold">AdScribe.AI</h1>
            ) : (
              <h1 className="text-xl font-bold">AS</h1>
            )}
          </Link>
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleSidebar}
            className="hidden lg:flex"
          >
            <Menu className="h-5 w-5" />
          </Button>
        </div>

        <nav className="flex-grow space-y-1 p-4">
          {NAV_ITEMS.map((item) => {
            const isActive = location.pathname === item.href;
            return (
              <Link
                key={item.href}
                to={item.href}
                className={`flex items-center rounded-md px-3 py-2 transition-all ${
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-foreground hover:bg-muted"
                } ${!sidebarOpen && "justify-center"}`}
              >
                {item.icon}
                {sidebarOpen && (
                  <span className="ml-3 text-sm font-medium">
                    {item.title}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        <div className="border-t p-4">
          <div
            className={`flex items-center rounded-md bg-muted p-2 ${
              !sidebarOpen && "justify-center"
            }`}
          >
            <Avatar className="h-8 w-8">
              <AvatarFallback>{getUserInitials()}</AvatarFallback>
            </Avatar>
            {sidebarOpen && (
              <div className="ml-3">
                <p className="text-sm font-medium">{user?.name}</p>
                <p className="text-xs text-muted-foreground">
                  {user?.email?.split("@")[0]}
                </p>
              </div>
            )}
          </div>
        </div>
      </aside>

      {/* Mobile Menu Button */}
      <div className="fixed left-0 top-0 z-50 flex h-16 w-full items-center justify-between border-b bg-card px-4 lg:hidden">
        <Link to="/app/dashboard" className="flex items-center gap-2">
          <h1 className="text-lg font-bold">AdScribe.AI</h1>
        </Link>
        <div className="flex items-center gap-4">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="rounded-full">
                <Avatar className="h-8 w-8">
                  <AvatarFallback>{getUserInitials()}</AvatarFallback>
                </Avatar>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>My Account</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => navigate("/app/account")}>
                <User className="mr-2 h-4 w-4" />
                Profile
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleLogout}>
                Logout
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleMobileMenu}
            className="lg:hidden"
          >
            {mobileMenuOpen ? (
              <X className="h-6 w-6" />
            ) : (
              <Menu className="h-6 w-6" />
            )}
          </Button>
        </div>
      </div>

      {/* Mobile Menu */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-40 flex h-screen w-screen flex-col bg-background pt-16 lg:hidden">
          <nav className="flex-grow space-y-1 p-4">
            {NAV_ITEMS.map((item) => {
              const isActive = location.pathname === item.href;
              return (
                <Link
                  key={item.href}
                  to={item.href}
                  className={`flex items-center rounded-md px-3 py-3 transition-all ${
                    isActive
                      ? "bg-primary text-primary-foreground"
                      : "text-foreground hover:bg-muted"
                  }`}
                  onClick={() => setMobileMenuOpen(false)}
                >
                  {item.icon}
                  <span className="ml-3 text-base font-medium">
                    {item.title}
                  </span>
                </Link>
              );
            })}
          </nav>
          <div className="border-t p-4">
            <Button
              variant="outline"
              className="w-full justify-start"
              onClick={() => {
                setMobileMenuOpen(false);
                navigate("/app/account");
              }}
            >
              <User className="mr-2 h-5 w-5" />
              Account Settings
            </Button>
            <Button
              variant="outline"
              className="mt-2 w-full justify-start"
              onClick={() => {
                handleLogout();
                setMobileMenuOpen(false);
              }}
            >
              Logout
            </Button>
          </div>
        </div>
      )}

      {/* Main Content */}
      <main
        className={`flex-1 overflow-auto pt-0 transition-all duration-300 ease-in-out lg:pt-0 ${
          sidebarOpen ? "lg:ml-64" : "lg:ml-20"
        } ${mobileMenuOpen ? "hidden" : ""} lg:block`}
      >
        <div className="flex min-h-screen flex-col">
          {/* Desktop Header */}
          <header className="sticky top-0 z-30 hidden h-16 items-center justify-between border-b bg-card px-4 lg:flex">
            <div className="flex-1" />
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" className="gap-2">
                  <Avatar className="h-8 w-8">
                    <AvatarFallback>{getUserInitials()}</AvatarFallback>
                  </Avatar>
                  <span>{user?.name}</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>My Account</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => navigate("/app/account")}>
                  <User className="mr-2 h-4 w-4" />
                  Profile
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleLogout}>
                  Logout
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </header>

          {/* Content Area */}
          <div className="flex-grow p-0 pt-16 lg:p-0">
            <Outlet />
          </div>
        </div>
      </main>
    </div>
  );
};

export default AppLayout; 