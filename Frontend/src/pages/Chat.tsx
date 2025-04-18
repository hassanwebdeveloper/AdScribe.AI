import React, { useState, useEffect } from 'react';
import { useChat } from '@/contexts/ChatContext';
import ChatSidebar from '@/components/chat/ChatSidebar';
import ChatWindow from '@/components/chat/ChatWindow';
import ChatInput from '@/components/chat/ChatInput';
import AnalysisSettingsPanel from '@/components/chat/AnalysisSettingsPanel';
import { useIsMobile } from '@/hooks/use-mobile';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Menu, Calendar } from 'lucide-react';

const Chat: React.FC = () => {
  const { getCurrentSession, dateRange } = useChat();
  const isMobile = useIsMobile();
  const currentSession = getCurrentSession();
  const [isDatePanelOpen, setIsDatePanelOpen] = useState(false);
  
  // Debug state changes
  useEffect(() => {
    console.log('Chat component - Current date range:', dateRange);
  }, [dateRange]);
  
  const toggleDatePanel = () => {
    setIsDatePanelOpen(!isDatePanelOpen);
  };
  
  // Calculate days between if dates are set
  const getDaysString = () => {
    if (dateRange.startDate && dateRange.endDate) {
      // Parse dates in 'yyyy-MM-dd' format
      const start = new Date(dateRange.startDate);
      const end = new Date(dateRange.endDate);
      const days = Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24));
      return `${days} day${days !== 1 ? 's' : ''} selected`;
    }
    return null;
  };
  
  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <div className="flex flex-1 overflow-hidden">
        {isMobile ? (
          <Sheet>
            <div className="flex items-center h-16 px-4 border-b">
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="mr-2">
                  <Menu className="h-5 w-5" />
                </Button>
              </SheetTrigger>
              <h1 className="font-semibold">AdScribe AI</h1>
              <div className="ml-auto">
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={toggleDatePanel}
                  className="flex items-center gap-2"
                  data-panel-toggle="true"
                >
                  <Calendar className="h-4 w-4" />
                  {getDaysString() || "Analysis Settings"}
                </Button>
              </div>
            </div>
            <SheetContent side="left" className="p-0 flex flex-col h-full w-72">
              <ChatSidebar />
            </SheetContent>
            <div className="flex flex-col flex-1 overflow-hidden">
              <div className="flex-1 overflow-hidden">
                <ChatWindow />
              </div>
              <div className="p-4 border-t">
                <ChatInput />
              </div>
            </div>
          </Sheet>
        ) : (
          <>
            <div className="w-80 h-full border-r hidden md:block">
              <ChatSidebar />
            </div>
            <div className="flex flex-col flex-1 overflow-hidden">
              <div className="h-16 px-4 border-b flex items-center justify-between">
                <h1 className="font-semibold">AdScribe AI</h1>
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={toggleDatePanel}
                  className="flex items-center gap-2"
                  data-panel-toggle="true"
                >
                  <Calendar className="h-4 w-4" />
                  {getDaysString() || "Analysis Settings"}
                </Button>
              </div>
              <div className="flex-1 overflow-hidden">
                <ChatWindow />
              </div>
              <div className="p-4 border-t">
                <ChatInput />
              </div>
            </div>
            {/* Analysis Settings Panel */}
            <AnalysisSettingsPanel 
              isOpen={isDatePanelOpen}
              togglePanel={toggleDatePanel}
            />
          </>
        )}
      </div>
    </div>
  );
};

export default Chat;
