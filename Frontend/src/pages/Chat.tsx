
import React from 'react';
import { useChat } from '@/contexts/ChatContext';
import ChatSidebar from '@/components/chat/ChatSidebar';
import ChatWindow from '@/components/chat/ChatWindow';
import ChatInput from '@/components/chat/ChatInput';
import QuestionnaireModal from '@/components/chat/QuestionnaireModal';
import { useIsMobile } from '@/hooks/use-mobile';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Menu } from 'lucide-react';

const Chat: React.FC = () => {
  const { isFirstPrompt, getCurrentSession } = useChat();
  const isMobile = useIsMobile();
  const currentSession = getCurrentSession();
  const showQuestionnaire = isFirstPrompt && currentSession?.messages.length === 1;
  
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
            </div>
            <SheetContent side="left" className="p-0 flex flex-col h-full w-72">
              <ChatSidebar />
            </SheetContent>
            <div className="flex flex-col flex-1 overflow-hidden">
              <div className="flex-1 overflow-hidden">
                {showQuestionnaire ? (
                  <div className="h-full flex items-center justify-center p-4">
                    <QuestionnaireModal />
                  </div>
                ) : (
                  <ChatWindow />
                )}
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
              <div className="flex-1 overflow-hidden">
                {showQuestionnaire ? (
                  <div className="h-full flex items-center justify-center p-4">
                    <QuestionnaireModal />
                  </div>
                ) : (
                  <ChatWindow />
                )}
              </div>
              <div className="p-4 border-t">
                <ChatInput />
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default Chat;
