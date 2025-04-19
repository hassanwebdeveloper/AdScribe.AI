import React, { useState } from 'react';
import { format } from 'date-fns';
import { cn } from '@/lib/utils';
import { Message } from '@/types';
import { Avatar } from '@/components/ui/avatar';
import { User, Bot, Edit, RotateCw, Trash } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { useChat } from '@/contexts/ChatContext';
import { Button } from '@/components/ui/button';

interface ChatMessageProps {
  message: Message;
  hasError?: boolean;
  isLastUserMessage?: boolean;
  onResendMessage?: (messageId: string) => void;
  onDeleteMessage?: (messageId: string) => void;
}

const ChatMessage: React.FC<ChatMessageProps> = ({
  message,
  hasError = false,
  isLastUserMessage = false,
  onResendMessage,
  onDeleteMessage,
}) => {
  const [isHovered, setIsHovered] = useState(false);
  const isUserMessage = message.role === 'user';
  const { setEditingMessageId } = useChat();
  
  // Controls visibility logic:
  // 1. Edit button: Only on the last user message
  // 2. Resend button: Only on messages with errors that aren't the last message
  // 3. Delete button: Only on messages with errors
  const shouldShowControls = isUserMessage && (
    (isHovered && isLastUserMessage) || // Show controls when hovering over last user message
    hasError // Always show controls for messages with errors
  );

  return (
    <div 
      className={cn(
        "relative py-3 px-4 my-2 rounded-lg",
        isUserMessage 
          ? "bg-blue-50 border border-blue-100 ml-auto" 
          : "bg-gray-50 border border-gray-100 mr-auto",
        message.role === 'user' ? 'max-w-[85%]' : 'max-w-[90%]',
        hasError && "border-red-300 bg-red-50"
      )}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div className="flex flex-col gap-1">
        <div className="text-sm font-medium">
          {message.role === 'user' ? 'You' : 'AI Assistant'}
        </div>
        <div className="text-gray-700 whitespace-pre-wrap">{message.content}</div>
        <div className="text-xs text-gray-400">
          {message.timestamp && format(new Date(message.timestamp), 'MMM d, h:mm a')}
        </div>
      </div>
      
      {shouldShowControls && (
        <div className="absolute top-2 right-2 flex gap-1">
          {isLastUserMessage && (
            <Button 
              variant="outline" 
              size="icon" 
              onClick={() => setEditingMessageId(message.id)} 
              title="Edit and resend message"
              className="h-6 w-6 p-0"
            >
              <Edit className="h-3 w-3" />
              <span className="sr-only">Edit</span>
            </Button>
          )}
          
          {hasError && !isLastUserMessage && (
            <Button 
              variant="outline" 
              size="icon" 
              onClick={() => onResendMessage?.(message.id)} 
              title="Resend message"
              className="h-6 w-6 p-0"
            >
              <RotateCw className="h-3 w-3" />
              <span className="sr-only">Resend</span>
            </Button>
          )}
          
          {hasError && (
            <Button 
              variant="outline" 
              size="icon" 
              onClick={() => onDeleteMessage?.(message.id)} 
              title="Delete message"
              className="h-6 w-6 p-0"
            >
              <Trash className="h-3 w-3" />
              <span className="sr-only">Delete</span>
            </Button>
          )}
        </div>
      )}
    </div>
  );
};

export default ChatMessage;
