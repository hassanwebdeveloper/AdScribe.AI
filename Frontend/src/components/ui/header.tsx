import { cn } from "@/lib/utils";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Calendar, Settings, LogOut, User } from "lucide-react";
import { useChat } from "@/contexts/ChatContext";
import { useAuth } from "@/contexts/AuthContext";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface HeaderProps {
  className?: string;
}

export function Header({ className }: HeaderProps) {
  const { dateRange, toggleAnalysisPanel } = useChat();
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  
  // Calculate days between if dates are set
  const getDaysString = () => {
    if (dateRange?.startDate && dateRange?.endDate) {
      // Parse dates in 'yyyy-MM-dd' format
      const start = new Date(dateRange.startDate);
      const end = new Date(dateRange.endDate);
      const days = Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24));
      return `${days} day${days !== 1 ? 's' : ''} selected`;
    }
    return "10 days selected"; // Default fallback
  };

  // Handle logout
  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  // Get user initials for avatar
  const getUserInitials = () => {
    if (!user?.name) return "US";
    const names = user.name.split(" ");
    if (names.length === 1) return names[0].substring(0, 2).toUpperCase();
    return (names[0][0] + names[names.length - 1][0]).toUpperCase();
  };
  
  return (
    <header className={cn("w-full bg-background border-b", className)}>
      <div className="w-full px-6 flex h-16 items-center">
        <div className="flex items-center gap-2">
          <Link to="/" className="flex items-center gap-2">
            <svg 
              className="h-8 w-8 text-primary" 
              width="32" 
              height="32" 
              viewBox="0 0 32 32" 
              fill="none" 
              xmlns="http://www.w3.org/2000/svg"
            >
              <rect width="32" height="32" rx="6" fill="currentColor"/>
              <path 
                d="M10 8L16 14L22 8M8 12L16 20L24 12M10 24L16 18L22 24" 
                stroke="white" 
                strokeWidth="2" 
                strokeLinecap="round" 
                strokeLinejoin="round"
              />
            </svg>
            <span className="text-xl font-bold">AdScribe.AI</span>
          </Link>
        </div>
        
        <div className="ml-8 flex space-x-4">
          <Link 
            to="/dashboard" 
            className={cn(
              "px-3 py-2 text-sm font-medium rounded-md",
              location.pathname === "/dashboard" ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
            )}
          >
            Dashboard
          </Link>
          <Link 
            to="/recommendations" 
            className={cn(
              "px-3 py-2 text-sm font-medium rounded-md",
              location.pathname === "/recommendations" ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
            )}
          >
            Recommendations
          </Link>
          <Link 
            to="/ai-scripter" 
            className={cn(
              "px-3 py-2 text-sm font-medium rounded-md",
              location.pathname === "/ai-scripter" ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
            )}
          >
            AI Scripter
          </Link>
          <Link 
            to="/ad-analysis" 
            className={cn(
              "px-3 py-2 text-sm font-medium rounded-md",
              location.pathname === "/ad-analysis" ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
            )}
          >
            Analyze Ads
          </Link>
        </div>
        
        <div className="ml-auto flex items-center gap-4">
          {location.pathname === "/ai-scripter" && (
            <Button 
              variant="outline" 
              size="sm" 
              onClick={toggleAnalysisPanel}
              className="flex items-center gap-2"
              data-panel-toggle="true"
            >
              <Calendar className="h-4 w-4" />
              {getDaysString()}
            </Button>
          )}
          
          {/* Settings Icon */}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate("/settings")}
            className="h-9 w-9"
          >
            <Settings className="h-4 w-4" />
          </Button>
          
          {/* User Dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="relative h-9 w-9 rounded-full">
                <Avatar className="h-8 w-8">
                  <AvatarFallback>{getUserInitials()}</AvatarFallback>
                </Avatar>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-56" align="end" forceMount>
              <DropdownMenuLabel className="font-normal">
                <div className="flex flex-col space-y-1">
                  <p className="text-sm font-medium leading-none">{user?.name || 'User'}</p>
                  <p className="text-xs leading-none text-muted-foreground">
                    {user?.email || 'user@example.com'}
                  </p>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => navigate("/settings")}>
                <Settings className="mr-2 h-4 w-4" />
                <span>Settings</span>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleLogout}>
                <LogOut className="mr-2 h-4 w-4" />
                <span>Log out</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
} 