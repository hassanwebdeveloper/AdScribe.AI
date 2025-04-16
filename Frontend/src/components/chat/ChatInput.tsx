
import React, { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Send, AlertCircle } from 'lucide-react';
import { useChat } from '@/contexts/ChatContext';
import { useAuth } from '@/contexts/AuthContext';
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogDescription, 
  DialogFooter 
} from '@/components/ui/dialog';
import { Link } from 'react-router-dom';

const ChatInput: React.FC = () => {
  const [message, setMessage] = useState('');
  const [showSettingsAlert, setShowSettingsAlert] = useState(false);
  const { sendMessage, isLoading } = useChat();
  const { user } = useAuth();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const isSettingsComplete = user?.fbGraphApiKey && user?.fbAdAccountId;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!isSettingsComplete) {
      setShowSettingsAlert(true);
      return;
    }

    if (!message.trim() || isLoading) return;
    
    await sendMessage(message);
    setMessage('');
    
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  };

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [message]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <>
      <form onSubmit={handleSubmit} className="relative flex flex-col mx-auto max-w-3xl">
        <div className="relative flex items-center">
          <Textarea
            ref={textareaRef}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message AdScribe AI..."
            className="min-h-12 max-h-36 pr-14 py-3 resize-none"
            disabled={!isSettingsComplete || isLoading}
          />
          <Button
            type="submit"
            size="icon"
            className="absolute right-2"
            disabled={!message.trim() || !isSettingsComplete || isLoading}
            variant="ghost"
          >
            <Send className="h-5 w-5" />
            <span className="sr-only">Send message</span>
          </Button>
        </div>
        <div className="text-xs text-muted-foreground mt-2 text-center">
          {!isSettingsComplete 
            ? "Please complete your API settings before starting a chat." 
            : "AdScribe AI helps you analyze and generate Facebook ads."}
        </div>
      </form>

      {showSettingsAlert && (
        <Dialog open={showSettingsAlert} onOpenChange={setShowSettingsAlert}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <AlertCircle className="h-6 w-6 text-yellow-500" />
                Complete API Settings
              </DialogTitle>
              <DialogDescription>
                You need to set up your Facebook Graph API key and Ad Account ID before you can start chatting.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Link to="/settings">
                <Button>Go to Settings</Button>
              </Link>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </>
  );
};

export default ChatInput;

