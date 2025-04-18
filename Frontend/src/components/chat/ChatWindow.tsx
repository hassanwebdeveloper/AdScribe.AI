import React, { useEffect, useRef } from 'react';
import { useChat } from '@/contexts/ChatContext';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Bot, Loader2 } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import Markdown from 'react-markdown';

const ChatWindow: React.FC = () => {
  const { getCurrentSession, isLoading } = useChat();
  const { user } = useAuth();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const currentSession = getCurrentSession();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [currentSession?.messages, isLoading]);

  if (!currentSession) {
    return (
      <div className="h-full flex items-center justify-center">
        <p className="text-muted-foreground">No active chat session.</p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col overflow-y-auto p-4">
      {currentSession.messages.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center space-y-4 p-8 text-center">
          <Bot className="h-12 w-12 text-brand-500" />
          <h3 className="text-xl font-medium">Welcome to AdScribe AI</h3>
          <p className="text-muted-foreground max-w-md">
            I can help you analyze your Facebook ads and create optimized ad copy.
            Let's start by asking about your ad campaign goals.
          </p>
        </div>
      ) : (
        <>
          <div className="flex-1 space-y-4">
            {currentSession.messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${
                  message.role === 'user' ? 'justify-end' : 'justify-start'
                }`}
              >
                <div
                  className={`flex gap-3 max-w-[80%] ${
                    message.role === 'user' ? 'flex-row-reverse' : ''
                  }`}
                >
                  {message.role === 'user' ? (
                    <Avatar className="h-8 w-8">
                      <AvatarFallback>
                        {user?.name?.charAt(0) || 'U'}
                      </AvatarFallback>
                      {/* If the user has an avatar image, it would go here */}
                    </Avatar>
                  ) : (
                    <Avatar className="h-8 w-8">
                      <AvatarImage src="/logo.png" />
                      <AvatarFallback>AI</AvatarFallback>
                    </Avatar>
                  )}
                  <div
                    className={`rounded-lg p-3 ${
                      message.role === 'user'
                        ? 'bg-brand-100 text-brand-900'
                        : message.role === 'system'
                        ? 'bg-gray-100 text-gray-600'
                        : 'bg-secondary'
                    }`}
                  >
                    <div className="prose dark:prose-invert max-w-none">
                      <Markdown components={{
                        a: ({node, ...props}) => (
                          <a 
                            {...props} 
                            className="text-brand-600 hover:text-brand-800 underline" 
                            target="_blank" 
                            rel="noopener noreferrer" 
                          />
                        )
                      }}>
                        {message.content}
                      </Markdown>
                    </div>
                  </div>
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex justify-start">
                <div className="flex gap-3 max-w-[80%]">
                  <Avatar className="h-8 w-8">
                    <AvatarImage src="/logo.png" />
                    <AvatarFallback>AI</AvatarFallback>
                  </Avatar>
                  <div className="bg-secondary rounded-lg p-3 flex items-center">
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    <span>Thinking...</span>
                  </div>
                </div>
              </div>
            )}
          </div>
          <div ref={messagesEndRef} />
        </>
      )}
    </div>
  );
};

export default ChatWindow;
