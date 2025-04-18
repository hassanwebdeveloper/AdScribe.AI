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
import axios from 'axios';
import { AlertCircle } from 'lucide-react';

// The webhook URL (copied from ChatContext)
const WEBHOOK_URL = 'https://n8n.srv764032.hstgr.cloud/webhook-test/6dcbdc6c-9bcd-4e9a-a4b1-60faa0219e72';

const ChatInput: React.FC = () => {
  const [message, setMessage] = useState('');
  const [showSettingsAlert, setShowSettingsAlert] = useState(false);
  const { sendMessage, isLoading, getCurrentSession, dateRange } = useChat();
  const { user } = useAuth();
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
        const userId = JSON.parse(localStorage.getItem('auth') || '{}')?.user?._id;
        if (userId) {
          const userData = localStorage.getItem(`dateRange_${userId}`);
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
  }, [dateRange]);

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
      // Get auth data
      const authData = localStorage.getItem('auth');
      if (!authData) {
        console.error('No auth data found!');
        // Fall back to regular send
        sendMessage(content);
        return;
      }
      
      const parsedAuth = JSON.parse(authData);
      const user = parsedAuth?.user;
      
      if (!user) {
        console.error('Invalid auth data!');
        // Fall back to regular send
        sendMessage(content);
        return;
      }
      
      // Add user message to UI (this will show in the chat)
      sendMessage(content);
      
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
      
      const currentSession = getCurrentSession();
      if (!currentSession) {
        console.error('No active chat session!');
        return;
      }
      
      // Get previous messages for context
      const contextMessages = currentSession.messages.slice(-5).map(msg => ({
        role: msg.role,
        content: msg.content
      }));
      
      // Create the payload with date range explicitly included
      const payload = {
        userMessage: content,
        previousMessages: contextMessages,
        dateRange: {
          startDate: finalDateRange.startDate,
          endDate: finalDateRange.endDate,
          daysToAnalyze
        },
        userInfo: {
          fbGraphApiKey: user?.fbGraphApiKey || user?.fb_graph_api_key || '',
          fbAdAccountId: user?.fbAdAccountId || user?.fb_ad_account_id || ''
        }
      };
      
      console.log('Sending direct payload to webhook:', payload);
      
      // Make the direct API call
      const response = await axios.post(WEBHOOK_URL, payload);
      console.log('Webhook direct response (raw):', response.data);

      // Log the exact response structure to debug
      console.log('Response is array?', Array.isArray(response.data));
      if (Array.isArray(response.data) && response.data.length > 0) {
        console.log('First element:', response.data[0]);
        console.log('Has output property?', 'output' in response.data[0]);
        if ('output' in response.data[0]) {
          console.log('Output content preview:', response.data[0].output.substring(0, 50) + '...');
        }
      }

      // Extract the output from the response
      const extractedOutput = extractOutputFromResponse(response.data);
      console.log('Extracted output (first 50 chars):', extractedOutput.substring(0, 50) + '...');
      
      // Add the bot response to the UI
      if (extractedOutput) {
        sendMessage(extractedOutput);
      } else {
        sendMessage("Sorry, I couldn't process the response correctly. Please try again.");
      }
      
      // Log the successful API call
      console.log('Successfully added response from webhook with date range:', finalDateRange);
      
    } catch (error) {
      console.error('Error sending direct message to webhook:', error);
      // Show error message
      const errorMsg = error instanceof Error ? error.message : 'Failed to send message';
      console.error('Webhook error:', errorMsg);
      
      // Add error message to chat
      sendMessage(`Error: ${errorMsg}`);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!isSettingsComplete) {
      setShowSettingsAlert(true);
      return;
    }

    if (!message.trim() || isLoading) return;
    
    // Use the direct send function instead
    sendDirectMessage(message);
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