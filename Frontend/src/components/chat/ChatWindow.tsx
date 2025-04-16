
import React, { useRef, useEffect } from 'react';
import { useChat } from '@/contexts/ChatContext';
import { useAuth } from '@/contexts/AuthContext';
import ChatMessage from './ChatMessage';
import { Bot, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Link } from 'react-router-dom';

const ChatWindow: React.FC = () => {
  const { getCurrentSession, isLoading } = useChat();
  const { user } = useAuth();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const currentSession = getCurrentSession();

  const isSettingsComplete = user?.fbGraphApiKey && user?.fbAdAccountId;

  // Scroll to bottom when messages change
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [currentSession?.messages]);

  if (!isSettingsComplete) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center p-4">
        <div className="bg-yellow-100 p-6 rounded-full mb-4">
          <AlertCircle className="h-8 w-8 text-yellow-600" />
        </div>
        <h3 className="text-lg font-semibold mb-2">Complete Your Settings</h3>
        <p className="text-muted-foreground max-w-sm mb-4">
          Please set up your Facebook Graph API key and Ad Account ID to start using AdScribe AI.
        </p>
        <Link to="/settings">
          <Button>Go to Settings</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto chat-container p-4">
      {currentSession && currentSession.messages.length > 0 ? (
        <>
          {currentSession.messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))}
        </>
      ) : (
        <div className="h-full flex flex-col items-center justify-center text-center">
          <div className="bg-brand-100 p-6 rounded-full mb-4">
            <Bot className="h-8 w-8 text-brand-600" />
          </div>
          <h3 className="text-lg font-semibold mb-2">Welcome to AdScribe AI</h3>
          <p className="text-muted-foreground max-w-sm">
            I'm here to help you analyze and generate Facebook ads. Start by sending a message.
          </p>
        </div>
      )}
      
      {isLoading && (
        <div className="flex items-start gap-4 py-4 px-4 bg-chat-bot-light animate-fade-in">
          <div className="h-8 w-8 rounded-full bg-chat-bot flex items-center justify-center">
            <Bot className="h-5 w-5 text-white" />
          </div>
          <div className="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
      )}
      
      <div ref={messagesEndRef} />
    </div>
  );
};

export default ChatWindow;

