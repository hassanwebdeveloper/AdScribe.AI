import React from 'react';
import { useChat } from '@/contexts/ChatContext';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Link } from 'react-router-dom';
import { PlusCircle, MessageSquare, Settings, LogOut, Trash2 } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const ChatSidebar: React.FC = () => {
  const { sessions, currentSessionId, createNewSession, selectSession, deleteSession } = useChat();
  const { logout, user } = useAuth();

  return (
    <div className="flex flex-col h-full w-full p-4 border-r">
      <div className="flex items-center justify-center mb-8">
        <h1 className="text-xl font-bold">AdScribe AI</h1>
      </div>
      
      <Button 
        onClick={createNewSession} 
        className="mb-6 flex items-center gap-2"
        variant="secondary"
      >
        <PlusCircle className="h-4 w-4" />
        New Chat
      </Button>
      
      <div className="flex-1 overflow-y-auto space-y-2 mb-6">
        {sessions.length > 0 ? (
          sessions.map((session) => (
            <div key={session.id} className="flex items-center group">
              <Button
                variant={currentSessionId === session.id ? "default" : "ghost"}
                className="w-full justify-start overflow-hidden text-ellipsis whitespace-nowrap pr-2"
                onClick={() => selectSession(session.id)}
              >
                <MessageSquare className="h-4 w-4 mr-2 shrink-0" />
                <span className="truncate">{session.title}</span>
              </Button>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteSession(session.id);
                      }}
                    >
                      <Trash2 className="h-4 w-4 text-muted-foreground" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>Delete chat</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          ))
        ) : (
          <div className="text-center text-muted-foreground">
            No chats yet
          </div>
        )}
      </div>
      
      <div className="border-t pt-4 space-y-2">
        <div className="px-3 py-2">
          <p className="text-sm font-medium">
            {user?.name || 'User'}
          </p>
          <p className="text-xs text-muted-foreground truncate">
            {user?.email || 'user@example.com'}
          </p>
        </div>
        <Link to="/settings">
          <Button
            variant="ghost"
            className="w-full justify-start"
          >
            <Settings className="h-4 w-4 mr-2" />
            Settings
          </Button>
        </Link>
        <Button
          variant="ghost"
          className="w-full justify-start"
          onClick={logout}
        >
          <LogOut className="h-4 w-4 mr-2" />
          Logout
        </Button>
      </div>
    </div>
  );
};

export default ChatSidebar;