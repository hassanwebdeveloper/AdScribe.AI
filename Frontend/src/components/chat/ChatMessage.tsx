
import React from 'react';
import { Message } from '@/types';
import { Avatar } from '@/components/ui/avatar';
import { User, Bot } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

interface ChatMessageProps {
  message: Message;
}

const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const isUser = message.role === 'user';
  
  return (
    <div
      className={`flex items-start gap-4 py-4 px-4 ${
        isUser ? 'bg-white' : 'bg-chat-bot-light'
      }`}
    >
      <Avatar className={`h-8 w-8 ${isUser ? 'bg-gray-300' : 'bg-chat-bot'}`}>
        {isUser ? (
          <User className="h-5 w-5 text-white" />
        ) : (
          <Bot className="h-5 w-5 text-white" />
        )}
      </Avatar>
      <div className="flex-1 space-y-2">
        <div className="text-sm font-medium">
          {isUser ? 'You' : 'AdScribe AI'}
        </div>
        <div className="prose prose-sm max-w-none">
          <ReactMarkdown>{message.content}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
};

export default ChatMessage;
