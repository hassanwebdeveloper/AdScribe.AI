import React from 'react';
import { useChat } from '@/contexts/ChatContext';
import { Button } from '@/components/ui/button';
import { PlusCircle, MessageSquare, Trash2 } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const ChatSidebar: React.FC = () => {
  const { sessions, currentSessionId, createNewSession, selectSession, deleteSession } = useChat();

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 flex-shrink-0">
        <Button 
          onClick={createNewSession} 
          className="w-full flex items-center gap-2"
          variant="secondary"
        >
          <PlusCircle className="h-4 w-4" />
          New Analysis
        </Button>
      </div>
      
      <div className="flex-1 overflow-y-auto px-2">
        <div className="space-y-1">
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
            <div className="text-center text-muted-foreground p-4">
              No chats yet
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChatSidebar;