import React, { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Send } from 'lucide-react';
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
import { AlertCircle } from 'lucide-react';
import api from '@/utils/api';
import { Message } from '@/types';

// Backend API endpoint for chat messages
const BACKEND_CHAT_ENDPOINT = '/webhook/chat';

const ChatInput: React.FC = () => {
  const [message, setMessage] = useState('');
  const [showSettingsAlert, setShowSettingsAlert] = useState(false);
  const { sendMessage, isLoading, getCurrentSession, dateRange, setChatState } = useChat();
  const { user, isAuthenticated } = useAuth();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  
  // Check for global date range values
  const [effectiveDateRange, setEffectiveDateRange] = useState<{
    startDate: string | null,
    endDate: string | null
  }>({
    startDate: null,
    endDate: null
  });

  const isSettingsComplete = user?.fbGraphApiKey && user?.fbAdAccountId;
  const currentSession = getCurrentSession();
  const isFirstPrompt = currentSession?.messages.length === 1;
  const showQuestionnaireInChat = isFirstPrompt && currentSession?.messages.length === 1;

  // Function to gather date range from all possible sources
  const updateEffectiveDateRange = () => {
    let result = {
      startDate: dateRange?.startDate || null,
      endDate: dateRange?.endDate || null
    };
    
    // Check window global (set by panel)
    if ((window as any).CURRENT_DATE_RANGE?.startDate && (window as any).CURRENT_DATE_RANGE?.endDate) {
      result = {
        startDate: (window as any).CURRENT_DATE_RANGE.startDate,
        endDate: (window as any).CURRENT_DATE_RANGE.endDate
      };
    }
    
    // Check localStorage as fallback
    if (!result.startDate || !result.endDate) {
      try {
        // Try debug storage
        const debugData = localStorage.getItem('debug_dateRange');
        if (debugData) {
          const parsed = JSON.parse(debugData);
          if (parsed.startDate && parsed.endDate) {
            result = {
              startDate: parsed.startDate,
              endDate: parsed.endDate
            };
          }
        }
        
        // Try user-specific storage
        if (user?._id) {
          const userData = localStorage.getItem(`dateRange_${user._id}`);
          if (userData) {
            const parsed = JSON.parse(userData);
            if (parsed.startDate && parsed.endDate) {
              result = {
                startDate: parsed.startDate,
                endDate: parsed.endDate
              };
            }
          }
        }
      } catch (e) {
        console.error('Error reading date range from localStorage:', e);
      }
    }
    
    return result;
  };
  
  // Update effective date range whenever component mounts or dateRange changes
  useEffect(() => {
    const newRange = updateEffectiveDateRange();
    setEffectiveDateRange(newRange);
    console.log('ChatInput - Effective date range:', newRange);
  }, [dateRange, user]);

  // Extract output from webhook response
  const extractOutputFromResponse = (responseData: any): string => {
    try {
      console.log('Response format:', typeof responseData, Array.isArray(responseData));
      
      // Handle the specific format shown in the console: array with object that has 'output' property
      if (Array.isArray(responseData) && responseData.length > 0 && responseData[0]?.output) {
        console.log('Found array with output property, returning that directly');
        return responseData[0].output;
      }
      
      // Check if the response is a string that needs to be parsed
      let data = responseData;
      if (typeof responseData === 'string') {
        try {
          data = JSON.parse(responseData);
          console.log('Parsed string data:', typeof data, Array.isArray(data));
          
          // After parsing, check again for the array format
          if (Array.isArray(data) && data.length > 0 && data[0]?.output) {
            console.log('Found output in parsed array');
            return data[0].output;
          }
        } catch (e) {
          // If it's not valid JSON, just return the string
          return responseData;
        }
      }
      
      // Check for object with output property directly
      if (data && typeof data === 'object' && !Array.isArray(data) && 'output' in data) {
        console.log('Found output property directly in object');
        return data.output;
      }
      
      // Check for message property as fallback
      if (data && typeof data === 'object' && !Array.isArray(data) && 'message' in data) {
        console.log('Found message property in object');
        return data.message;
      }
      
      // Handle case where response might be a JSON string inside a JSON string
      if (typeof data === 'string') {
        try {
          const nestedData = JSON.parse(data);
          console.log('Parsed nested string data:', typeof nestedData);
          
          if (Array.isArray(nestedData) && nestedData.length > 0 && nestedData[0]?.output) {
            return nestedData[0].output;
          }
          
          if (nestedData && typeof nestedData === 'object') {
            if ('output' in nestedData) return nestedData.output;
            if ('message' in nestedData) return nestedData.message;
          }
        } catch (e) {
          // If nested parsing fails, continue with the original string
        }
      }
      
      // If we got here, we couldn't extract the output properly
      console.log('Could not extract output value, using fallback');
      
      // Fallback to the original response or a readable version
      return typeof responseData === 'string' 
        ? responseData 
        : JSON.stringify(responseData, null, 2);
    } catch (e) {
      console.error('Error parsing webhook response:', e);
      return typeof responseData === 'string' 
        ? responseData 
        : JSON.stringify(responseData, null, 2);
    }
  };

  // Direct API call with date range info
  const sendDirectMessage = async (content: string) => {
    try {
      console.debug('Starting direct message send for:', content);
      
      // Ensure we're authenticated
      if (!isAuthenticated || !user) {
        console.error('Not authenticated!');
        return;
      }
      
      // Add user message to UI ONLY - do not use sendMessage as it will trigger another API call
      // Instead, manually create the user message in the UI
      const userMessage: Message = {
        id: `msg_${Math.random().toString(36).substring(2, 11)}`,
        content,
        role: 'user',
        timestamp: new Date(),
      };
      
      // Update chat state with the user message
      const currentSession = getCurrentSession();
      if (!currentSession) {
        console.error('No active chat session!');
        return;
      }
      
      console.debug('Adding user message to UI:', userMessage.id);
      
      // Start loading state
      setChatState?.(prev => ({
        ...prev,
        isLoading: true,
        error: null,
        sessions: prev.sessions.map(s => 
          s.id === currentSession.id 
            ? { 
                ...s, 
                messages: [...s.messages, userMessage],
                updatedAt: new Date(),
              } 
            : s
        ),
      }));
      
      // Now gather all date range sources again
      const finalDateRange = updateEffectiveDateRange();
      console.log('Final date range for API call:', finalDateRange);
      
      // Calculate days to analyze if we have start and end dates
      let daysToAnalyze = null;
      if (finalDateRange.startDate && finalDateRange.endDate) {
        const start = new Date(finalDateRange.startDate);
        const end = new Date(finalDateRange.endDate);
        daysToAnalyze = Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)).toString();
      }
      
      // Important: We need to get the context messages BEFORE we added our new message
      // to avoid including the message we just sent in the context
      const contextMessages = currentSession.messages
        .filter(msg => msg.id !== userMessage.id)  // Ensure our new message isn't included
        .slice(-5)
        .map(msg => ({
          role: msg.role,
          content: msg.content
        }));
      
      console.debug('Context messages count:', contextMessages.length);
      
      // Create the payload for the backend API
      const payload = {
        userMessage: content,
        previousMessages: contextMessages,
        dateRange: {
          startDate: finalDateRange.startDate,
          endDate: finalDateRange.endDate,
          daysToAnalyze
        }
        // Don't include API keys - these will be retrieved on the backend
      };
      
      console.log('Sending direct payload to backend API:', payload);
      
      // Make the direct API call to our backend (which will forward to n8n)
      const response = await api.post(BACKEND_CHAT_ENDPOINT, payload);
      console.log('Backend API response:', response.data);
      
      // Extract the output from the response
      const extractedOutput = extractOutputFromResponse(response.data);
      console.log('Extracted output:', extractedOutput);
      
      // Add the bot response directly to the UI
      const botMessage: Message = {
        id: `msg_${Math.random().toString(36).substring(2, 11)}`,
        content: extractedOutput,
        role: 'bot',
        timestamp: new Date(),
      };
      
      console.debug('Adding bot response to UI:', botMessage.id);
      
      // Get current session again in case it changed
      const updatedSession = getCurrentSession();
      if (!updatedSession) {
        console.error('Session lost during API call');
        return;
      }
      
      // Update chat state with bot message and stop loading
      setChatState?.(prev => ({
        ...prev,
        isLoading: false,
        error: null,
        sessions: prev.sessions.map(s => 
          s.id === updatedSession.id 
            ? { 
                ...s, 
                messages: [...s.messages, botMessage],
                updatedAt: new Date(),
              } 
            : s
        ),
      }));
      
      // Log the successful API call
      console.log('Successfully added response from backend with date range:', finalDateRange);
      
    } catch (error) {
      console.error('Error sending direct message to backend:', error);
      // Show error message
      const errorMsg = error instanceof Error ? error.message : 'Failed to send message';
      console.error('Backend error:', errorMsg);
      
      // Add error message as bot response
      const errorBotMessage: Message = {
        id: `msg_${Math.random().toString(36).substring(2, 11)}`,
        content: `Error: ${errorMsg}`,
        role: 'bot',
        timestamp: new Date(),
      };
      
      const currentSession = getCurrentSession();
      if (currentSession) {
        setChatState?.(prev => ({
          ...prev,
          isLoading: false,
          error: errorMsg,
          sessions: prev.sessions.map(s => 
            s.id === currentSession.id 
              ? { 
                  ...s, 
                  messages: [...s.messages, errorBotMessage],
                  updatedAt: new Date(),
                } 
              : s
          ),
        }));
      }
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!isSettingsComplete) {
      setShowSettingsAlert(true);
      return;
    }

    // Don't process empty messages or when already loading
    if (!message.trim() || isLoading) return;
    
    // Use the direct send function only - don't call sendMessage which would create duplicate calls
    sendDirectMessage(message);
    
    // Clear the input field
    setMessage('');
    
    // Restore focus to the textarea
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

  const handleTextareaKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
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
            onKeyDown={handleTextareaKeyDown}
            placeholder="Message AdScribe AI..."
            className="min-h-12 max-h-36 pr-14 py-3 resize-none"
            disabled={!isSettingsComplete || isLoading || showQuestionnaireInChat}
          />
          <Button
            type="submit"
            size="icon"
            className="absolute right-2"
            disabled={!message.trim() || !isSettingsComplete || isLoading || showQuestionnaireInChat}
            variant="ghost"
          >
            <Send className="h-5 w-5" />
            <span className="sr-only">Send message</span>
          </Button>
        </div>
        <div className="text-xs text-muted-foreground mt-2 text-center">
          {!isSettingsComplete 
            ? "Please complete your API settings before starting a chat." 
            : showQuestionnaireInChat
              ? "Please answer the questions to generate better ad recommendations."
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