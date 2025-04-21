import React, { useState } from 'react';
import { format } from 'date-fns';
import { cn } from '@/lib/utils';
import { Message } from '@/types';
import { Avatar } from '@/components/ui/avatar';
import { User, Bot, Edit, RotateCw, Trash } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { useChat } from '@/contexts/ChatContext';
import { Button } from '@/components/ui/button';
import AdCard from '@/components/ads/AdCard';

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
  
  // Replace backtick code blocks with proper markdown code blocks
  const processedContent = message.content
    // Replace triple backtick code blocks with proper markdown code blocks if they aren't already
    .replace(/```([a-z]*)\n([\s\S]*?)```/g, (match, lang, code) => {
      return `\`\`\`${lang || ''}\n${code}\n\`\`\``;
    });
  
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
        <div className="text-gray-700 prose prose-sm max-w-none">
          <ReactMarkdown
            components={{
              h1: ({ node, ...props }) => <h1 className="text-xl font-bold mt-4 mb-2" {...props} />,
              h2: ({ node, ...props }) => <h2 className="text-lg font-bold mt-3 mb-2" {...props} />,
              h3: ({ node, ...props }) => <h3 className="text-base font-bold mt-3 mb-1" {...props} />,
              strong: ({ node, ...props }) => <strong className="font-bold" {...props} />,
              em: ({ node, ...props }) => <em className="italic" {...props} />,
              p: ({ node, ...props }) => <p className="mb-2" {...props} />,
              ul: ({ node, ...props }) => <ul className="list-disc pl-5 mb-2" {...props} />,
              ol: ({ node, ...props }) => <ol className="list-decimal pl-5 mb-2" {...props} />,
              li: ({ node, ...props }) => <li className="mb-1" {...props} />,
              code: ({ node, className, children, ...props }: any) => {
                const match = /language-(\w+)/.exec(className || '');
                const isInline = !className || !match;
                return isInline ? (
                  <code className="bg-gray-200 px-1 py-0.5 rounded text-sm font-mono text-gray-800" {...props}>
                    {children}
                  </code>
                ) : (
                  <code className="block bg-gray-800 p-2 rounded text-sm font-mono text-gray-100 overflow-x-auto my-2" {...props}>
                    {children}
                  </code>
                );
              },
              pre: ({ node, children, ...props }) => (
                <pre className="bg-gray-800 p-3 rounded-md overflow-x-auto my-3 text-gray-100" {...props}>
                  {children}
                </pre>
              ),
              blockquote: ({ node, ...props }) => <blockquote className="border-l-4 border-gray-300 pl-4 italic my-2" {...props} />,
            }}
          >
            {processedContent}
          </ReactMarkdown>
        </div>
        
        {message.ad && (
          <AdCard 
            ad={message.ad}
            start_date={message.start_date}
            end_date={message.end_date}
          />
        )}
        
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
