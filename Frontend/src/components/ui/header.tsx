import { cn } from "@/lib/utils";
import { Link, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Calendar } from "lucide-react";
import { useChat } from "@/contexts/ChatContext";

interface HeaderProps {
  className?: string;
}

export function Header({ className }: HeaderProps) {
  const { dateRange, toggleAnalysisPanel } = useChat();
  const location = useLocation();
  
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
            to="/chat" 
            className={cn(
              "px-3 py-2 text-sm font-medium rounded-md",
              location.pathname === "/chat" ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
            )}
          >
            Chat
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
          <Link 
            to="/settings" 
            className={cn(
              "px-3 py-2 text-sm font-medium rounded-md",
              location.pathname === "/settings" ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
            )}
          >
            Settings
          </Link>
        </div>
        
        <div className="ml-auto flex items-center gap-4">
          {location.pathname === "/chat" && (
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
        </div>
      </div>
    </header>
  );
} 