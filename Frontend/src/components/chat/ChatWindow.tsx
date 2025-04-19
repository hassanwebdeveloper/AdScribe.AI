import React, { useEffect, useRef } from 'react';
import { useChat } from '@/contexts/ChatContext';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Bot, Loader2 } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import Markdown from 'react-markdown';
import ChatMessage from './ChatMessage';
import { Message } from '@/types';
import { useToast } from '@/components/ui/use-toast';

const ChatWindow: React.FC = () => {
  const { getCurrentSession, isLoading, sendMessage, setChatState, messagesWithErrors, editMessage } = useChat();
  const { user } = useAuth();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();
  
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

  // Find the last user message
  const lastUserMessageIndex = [...currentSession.messages]
    .reverse()
    .findIndex(msg => msg.role === 'user');
    
  const lastUserMessageId = lastUserMessageIndex !== -1 
    ? currentSession.messages[currentSession.messages.length - 1 - lastUserMessageIndex].id 
    : null;

  // Handle editing a message (just updates the message content without resending)
  const handleEditMessage = async (messageId: string, newContent: string) => {
    if (!currentSession) return;
    
    try {
      await editMessage(messageId, newContent);
      
      toast({
        title: "Success",
        description: "Message updated successfully",
      });
    } catch (error) {
      console.error('Error editing message:', error);
      toast({
        title: "Error",
        description: "Failed to edit message",
        variant: "destructive",
      });
    }
  };

  // Handle resending a message after editing
  const handleResendMessage = async (messageId: string) => {
    if (!currentSession) return;
    
    try {
      // Find the message
      const message = currentSession.messages.find(m => m.id === messageId);
      if (!message) return;
      
      // Find the message index
      const messageIndex = currentSession.messages.findIndex(m => m.id === messageId);
      
      // Remove all bot messages that came after this message
      const messagesToKeep = currentSession.messages.slice(0, messageIndex + 1);
      
      // Update the state
      setChatState(prev => ({
        ...prev,
        sessions: prev.sessions.map(s => 
          s.id === currentSession.id 
            ? { ...s, messages: messagesToKeep }
            : s
        )
      }));
      
      // Resend the message to get a new response
      await sendMessage(message.content);
      
      toast({
        title: "Success",
        description: "Message resent successfully",
      });
    } catch (error) {
      console.error('Error resending message:', error);
      toast({
        title: "Error",
        description: "Failed to resend message",
        variant: "destructive",
      });
    }
  };

  // Handle deleting a message
  const handleDeleteMessage = async (messageId: string) => {
    if (!currentSession) return;
    
    try {
      // Find the message index
      const messageIndex = currentSession.messages.findIndex(m => m.id === messageId);
      if (messageIndex === -1) return;
      
      // Remove this message and all messages that came after it
      const messagesToKeep = currentSession.messages.slice(0, messageIndex);
      
      // Update the state
      setChatState(prev => ({
        ...prev,
        sessions: prev.sessions.map(s => 
          s.id === currentSession.id 
            ? { ...s, messages: messagesToKeep }
            : s
        )
      }));
      
      toast({
        title: "Success",
        description: "Message deleted",
      });
    } catch (error) {
      console.error('Error deleting message:', error);
      toast({
        title: "Error",
        description: "Failed to delete message",
        variant: "destructive",
      });
    }
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="p-4">
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
          <div className="divide-y">
            {currentSession.messages.map((message) => (
              <ChatMessage
                key={message.id}
                message={message}
                isLastUserMessage={message.id === lastUserMessageId}
                hasError={messagesWithErrors.includes(message.id)}
                onResendMessage={handleResendMessage}
                onDeleteMessage={handleDeleteMessage}
              />
            ))}
            
            {isLoading && (
              <div className="p-4 bg-chat-bot-light">
                <div className="flex items-center">
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  <span>Thinking...</span>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatWindow;
