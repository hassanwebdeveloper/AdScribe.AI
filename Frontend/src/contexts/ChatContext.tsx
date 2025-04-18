import React, { createContext, useContext, useState, useEffect } from 'react';
import { Message, ChatSession, ChatState, DateRange } from '@/types';
import { useToast } from '@/components/ui/use-toast';
import { useAuth } from './AuthContext';
import api from '@/utils/api';

// Backend API endpoint for chat messages
const BACKEND_CHAT_ENDPOINT = '/webhook/chat';

interface ChatContextType extends ChatState {
  sendMessage: (content: string) => Promise<void>;
  createNewSession: () => void;
  selectSession: (sessionId: string) => void;
  getCurrentSession: () => ChatSession | undefined;
  dateRange: DateRange;
  updateDateRange: (data: DateRange) => void;
  setChatState: React.Dispatch<React.SetStateAction<ChatState>>;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

export const ChatProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { toast } = useToast();
  const { user, isAuthenticated } = useAuth();
  const [dateRange, setDateRange] = useState<DateRange>({});
  
  const [chatState, setChatState] = useState<ChatState>({
    sessions: [],
    currentSessionId: null,
    isLoading: false,
    error: null,
  });

  // Initialize and check auth data on mount
  useEffect(() => {
    // Ensure we have user data available
    const initAuthData = () => {
      if (user && user._id) {
        console.log('Auth initialized with user:', user._id);
        
        // Try to read date range for this user
        try {
          const savedDateRange = localStorage.getItem(`dateRange_${user._id}`);
          if (savedDateRange) {
            try {
              const parsed = JSON.parse(savedDateRange);
              if (parsed) {
                console.log('Found saved date range for user:', parsed);
                setDateRange(parsed);
                
                // Also store in window global for emergency access
                (window as any).forcedDateRange = parsed;
              }
            } catch (e) {
              console.error('Error parsing date range from localStorage:', e);
            }
          } else {
            console.log('No saved date range found for user');
          }
        } catch (e) {
          console.error('Error accessing localStorage:', e);
        }
      } else {
        console.warn('No user data available');
      }
    };
    
    initAuthData();
  }, [user]);

  // Load chat sessions from local storage on component mount
  useEffect(() => {
    if (user && user._id) {
      const savedSessions = localStorage.getItem(`chatSessions_${user._id}`);
      
      if (savedSessions) {
        const sessions = JSON.parse(savedSessions);
        // Convert string dates back to Date objects
        sessions.forEach((session: ChatSession) => {
          session.createdAt = new Date(session.createdAt);
          session.updatedAt = new Date(session.updatedAt);
          session.messages.forEach((msg: Message) => {
            msg.timestamp = new Date(msg.timestamp);
          });
        });
        
        setChatState({
          ...chatState,
          sessions,
          currentSessionId: sessions.length > 0 ? sessions[0].id : null,
        });
      } else if (chatState.sessions.length === 0) {
        // Create a new session if there are no sessions
        createNewSession();
      }

      // Load date range from local storage
      const savedDateRange = localStorage.getItem(`dateRange_${user._id}`);
      if (savedDateRange) {
        try {
          const parsedDateRange = JSON.parse(savedDateRange);
          console.log('Loading date range from localStorage:', parsedDateRange);
          setDateRange(parsedDateRange);
        } catch (e) {
          console.error('Error parsing date range from localStorage:', e);
        }
      }
    }
  }, [user]);

  // Save chat sessions to local storage whenever they change
  useEffect(() => {
    if (user && user._id && chatState.sessions.length > 0) {
      localStorage.setItem(`chatSessions_${user._id}`, JSON.stringify(chatState.sessions));
    }
  }, [chatState.sessions, user]);

  // Save date range to local storage whenever it changes
  useEffect(() => {
    if (user && user._id) {
      console.log('useEffect: Saving date range to localStorage:', dateRange);
      localStorage.setItem(`dateRange_${user._id}`, JSON.stringify(dateRange));
    }
  }, [dateRange, user]);

  const createNewSession = () => {
    const newSession: ChatSession = {
      id: `session_${Math.random().toString(36).substring(2, 11)}`,
      title: `New Chat ${chatState.sessions.length + 1}`,
      messages: [],
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    setChatState(prev => ({
      ...prev,
      sessions: [newSession, ...prev.sessions],
      currentSessionId: newSession.id,
    }));
  };

  const selectSession = (sessionId: string) => {
    setChatState(prev => ({
      ...prev,
      currentSessionId: sessionId,
    }));
  };

  const getCurrentSession = () => {
    return chatState.sessions.find(s => s.id === chatState.currentSessionId);
  };

  const updateDateRange = (data: DateRange) => {
    console.log('Updating date range with:', data);
    
    // Create a new object to ensure state update
    const newDateRange = { ...dateRange, ...data };
    console.log('New date range will be:', newDateRange);
    
    setDateRange(newDateRange);
    
    // Debug direct access to localStorage
    if (user && user._id && window.localStorage) {
      // Store directly to localStorage for immediate use
      localStorage.setItem(`dateRange_${user._id}`, JSON.stringify(newDateRange));
      console.log('Saved date range to localStorage:', newDateRange);
    }
  };

  // Helper function to send messages to webhook
  const sendMessageToWebhook = async (content: string, session: ChatSession) => {
    try {
      // Ensure we're authenticated
      if (!isAuthenticated || !user) {
        toast({
          title: "Error",
          description: "You must be logged in to send messages",
          variant: "destructive",
        });
        return false;
      }

      // Prepare context from previous messages (exclude the latest user message)
      const contextMessages = session.messages.slice(-5);
      
      console.log('Current date range state:', JSON.stringify(dateRange));
      
      // Try multiple sources for date range
      let effectiveDateRange = {
        startDate: null as string | null,
        endDate: null as string | null
      };
      
      // 1. Check React state
      if (dateRange.startDate && dateRange.endDate) {
        effectiveDateRange = {
          startDate: dateRange.startDate,
          endDate: dateRange.endDate
        };
        console.log('Using date range from React state:', effectiveDateRange);
      } 
      // 2. Check localStorage
      else {
        try {
          const savedDateRange = localStorage.getItem(`dateRange_${user._id}`);
          if (savedDateRange) {
            const parsed = JSON.parse(savedDateRange);
            if (parsed.startDate && parsed.endDate) {
              effectiveDateRange = {
                startDate: parsed.startDate,
                endDate: parsed.endDate
              };
              console.log('Using date range from localStorage:', effectiveDateRange);
            }
          }
        } catch (e) {
          console.error('Error reading from localStorage:', e);
        }
      }
      
      // 3. Check debug localStorage
      if (!effectiveDateRange.startDate || !effectiveDateRange.endDate) {
        try {
          const debugRange = localStorage.getItem('debug_dateRange');
          if (debugRange) {
            const parsed = JSON.parse(debugRange);
            if (parsed.startDate && parsed.endDate) {
              effectiveDateRange = {
                startDate: parsed.startDate,
                endDate: parsed.endDate
              };
              console.log('Using date range from debug localStorage:', effectiveDateRange);
            }
          }
        } catch (e) {
          console.error('Error reading from debug localStorage:', e);
        }
      }
      
      // 4. Check global window variable (set by force function)
      if (!effectiveDateRange.startDate || !effectiveDateRange.endDate) {
        if ((window as any).forcedDateRange?.startDate && (window as any).forcedDateRange?.endDate) {
          effectiveDateRange = {
            startDate: (window as any).forcedDateRange.startDate,
            endDate: (window as any).forcedDateRange.endDate
          };
          console.log('Using date range from window global:', effectiveDateRange);
        }
      }
      
      // 5. Extract from message content as last resort
      if ((!effectiveDateRange.startDate || !effectiveDateRange.endDate) && content.includes('date range:')) {
        try {
          const match = content.match(/date range: (\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})/);
          if (match && match[1] && match[2]) {
            effectiveDateRange = {
              startDate: match[1],
              endDate: match[2]
            };
            console.log('Extracted date range from message:', effectiveDateRange);
          }
        } catch (e) {
          console.error('Error extracting date from message:', e);
        }
      }
      
      console.log('Effective date range to use:', effectiveDateRange);
      
      // Calculate days if date range is set
      let daysToAnalyze = null;
      
      if (effectiveDateRange.startDate && effectiveDateRange.endDate) {
        // Parse date strings in format 'yyyy-MM-dd'
        const start = new Date(effectiveDateRange.startDate);
        const end = new Date(effectiveDateRange.endDate);
        daysToAnalyze = Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)).toString();
        
        console.log('Calculated days to analyze:', daysToAnalyze);
      } else {
        console.log('Date range not set or incomplete');
      }
      
      // Create payload for backend API
      const payload = {
        userMessage: content,
        previousMessages: contextMessages.map(msg => ({
          role: msg.role,
          content: msg.content,
        })),
        dateRange: {
          startDate: effectiveDateRange.startDate,
          endDate: effectiveDateRange.endDate,
          daysToAnalyze
        },
        // Don't include API keys in payload - backend will add them
      };
      
      console.log('Sending to backend API:', payload);
      
      // Send request to backend (not directly to n8n) with auth
      const response = await api.post(BACKEND_CHAT_ENDPOINT, payload);
      console.log('Backend API response:', response.data);
      
      // Add bot response from webhook
      const botMessage: Message = {
        id: `msg_${Math.random().toString(36).substring(2, 11)}`,
        content: extractOutputFromResponse(response.data),
        role: 'bot',
        timestamp: new Date(),
      };
      
      setChatState(prev => ({
        ...prev,
        sessions: prev.sessions.map(s => 
          s.id === session.id 
            ? { 
                ...s, 
                messages: [...s.messages, botMessage],
                updatedAt: new Date(),
                // Update title based on first user message if it's still the default
                title: s.title === `New Chat ${prev.sessions.indexOf(s) + 1}` 
                  ? content.slice(0, 30) + (content.length > 30 ? '...' : '') 
                  : s.title
              } 
            : s
        ),
        isLoading: false,
      }));
      
      return true;
    } catch (error) {
      console.error('Error calling backend API:', error);
      
      setChatState(prev => ({
        ...prev,
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to get response',
      }));
      
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : 'Failed to get response',
        variant: "destructive",
      });
      
      return false;
    }
  };

  // Helper function to extract output from response
  const extractOutputFromResponse = (responseData: any): string => {
    try {
      // If it's an array with objects containing output property
      if (Array.isArray(responseData) && responseData.length > 0 && responseData[0]?.output) {
        return responseData[0].output;
      }
      
      // Check if the response is a string that needs to be parsed
      if (typeof responseData === 'string') {
        try {
          const parsedData = JSON.parse(responseData);
          
          // Check again if it's an array after parsing
          if (Array.isArray(parsedData) && parsedData.length > 0 && parsedData[0]?.output) {
            return parsedData[0].output;
          }
          
          // Check if it's an object with output property
          if (parsedData && typeof parsedData === 'object' && 'output' in parsedData) {
            return parsedData.output;
          }
          
          // Fallback to message property
          if (parsedData && typeof parsedData === 'object' && 'message' in parsedData) {
            return parsedData.message;
          }
          
          // Return the parsed data as string if we couldn't extract output
          return typeof parsedData === 'string' ? parsedData : JSON.stringify(parsedData);
        } catch (e) {
          // If parsing fails, return the original string
          return responseData;
        }
      }
      
      // If it's an object with output or message property
      if (responseData && typeof responseData === 'object') {
        if ('output' in responseData) return responseData.output;
        if ('message' in responseData) return responseData.message;
      }
      
      // Fallback to original response
      return typeof responseData === 'string' ? responseData : JSON.stringify(responseData);
    } catch (e) {
      console.error('Error extracting output from backend API response:', e);
      return typeof responseData === 'string' ? responseData : JSON.stringify(responseData);
    }
  };

  const sendMessage = async (content: string) => {
    if (!content.trim()) return;
    
    setChatState(prev => ({
      ...prev,
      isLoading: true,
      error: null,
    }));
    
    const currentSession = getCurrentSession();
    
    if (!currentSession) {
      toast({
        title: "Error",
        description: "No active chat session",
        variant: "destructive",
      });
      return;
    }
    
    // Add user message
    const userMessage: Message = {
      id: `msg_${Math.random().toString(36).substring(2, 11)}`,
      content,
      role: 'user',
      timestamp: new Date(),
    };
    
    setChatState(prev => ({
      ...prev,
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
    
    // Use the helper function to send message to webhook
    await sendMessageToWebhook(content, currentSession);
  };

  return (
    <ChatContext.Provider
      value={{
        ...chatState,
        sendMessage,
        createNewSession,
        selectSession,
        getCurrentSession,
        dateRange,
        updateDateRange,
        setChatState,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
};

export const useChat = () => {
  const context = useContext(ChatContext);
  if (context === undefined) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
};
