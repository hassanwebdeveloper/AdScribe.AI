import React, { createContext, useContext, useState, useEffect } from 'react';
import { Message, ChatSession, ChatState, DateRange } from '@/types';
import { useToast } from '@/components/ui/use-toast';
import { useAuth } from './AuthContext';
import api from '@/utils/api';

// Backend API endpoints
const BACKEND_CHAT_ENDPOINT = '/webhook/chat';
const CHAT_API_ENDPOINT = '/chat';

interface ChatContextType extends ChatState {
  sendMessage: (content: string) => Promise<void>;
  createNewSession: () => void;
  selectSession: (sessionId: string) => void;
  deleteSession: (sessionId: string) => void;
  getCurrentSession: () => ChatSession | undefined;
  dateRange: DateRange;
  updateDateRange: (data: DateRange) => void;
  setChatState: React.Dispatch<React.SetStateAction<ChatState>>;
  messagesWithErrors: string[]; // Array of message IDs with errors
  clearMessageError: (messageId: string) => void;
  editMessage: (messageId: string, newContent: string) => Promise<void>;
  editingMessageId: string | null;
  setEditingMessageId: (messageId: string | null) => void;
  setMessagesWithErrors: React.Dispatch<React.SetStateAction<string[]>>;
  toggleAnalysisPanel: () => void;
  isAnalysisPanelOpen: boolean;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

export const ChatProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { toast } = useToast();
  const { user, isAuthenticated } = useAuth();
  const [dateRange, setDateRange] = useState<DateRange>({});
  const [messagesWithErrors, setMessagesWithErrors] = useState<string[]>([]);
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [isAnalysisPanelOpen, setIsAnalysisPanelOpen] = useState<boolean>(false);
  
  const [chatState, setChatState] = useState<ChatState>({
    sessions: [],
    currentSessionId: null,
    isLoading: false,
    error: null,
  });

  // Initialize and check auth data on mount
  useEffect(() => {
    // Ensure we have user data available
    const initAuthData = async () => {
      if (user && user._id) {
        console.log('Auth initialized with user:', user._id);
        
        // Fetch analysis settings from the API
        try {
          const response = await api.get(`${CHAT_API_ENDPOINT}/settings`);
          if (response.data && response.data.date_range) {
            const apiDateRange = {
              startDate: response.data.date_range.start_date,
              endDate: response.data.date_range.end_date
            };
            console.log('Found saved date range for user:', apiDateRange);
            setDateRange(apiDateRange);
          } else {
            console.log('No saved date range found for user');
          }
        } catch (e) {
          console.error('Error fetching analysis settings:', e);
        }
      } else {
        console.warn('No user data available');
      }
    };
    
    initAuthData();
  }, [user]);

  // Load chat sessions from API on component mount
  useEffect(() => {
    const fetchSessions = async () => {
      if (user && user._id) {
        try {
          setChatState(prev => ({
            ...prev,
            isLoading: true
          }));
          
          const response = await api.get(`${CHAT_API_ENDPOINT}/sessions`);
          const sessions = response.data;
          
          // Convert string dates to Date objects and ensure id field
          sessions.forEach((session: ChatSession) => {
            // MongoDB returns _id, but our frontend uses id, so map it if needed
            if (session._id && !session.id) {
              session.id = session._id;
            }
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
            isLoading: false
          });
        } catch (error) {
          console.error('Error fetching chat sessions:', error);
          setChatState({
            ...chatState,
            isLoading: false,
            error: 'Failed to load chat sessions'
          });
        }
      }
    };
    
    fetchSessions();
  }, [user]);

  const createNewSession = async () => {
    if (!user || !user._id) {
      toast({
        title: "Error",
        description: "You must be logged in to create a new chat",
        variant: "destructive",
      });
      return;
    }
    
    try {
      setChatState(prev => ({
        ...prev,
        isLoading: true
      }));
      
      console.log('Creating new chat session, API endpoint:', `${CHAT_API_ENDPOINT}/sessions`);
      
      const response = await api.post(`${CHAT_API_ENDPOINT}/sessions`, {
        title: `New Chat ${chatState.sessions.length + 1}`
      });
      
      console.log('Chat session created, response:', response.data);
      
      const newSession = response.data;
      // MongoDB returns _id, but our frontend uses id
      if (newSession._id && !newSession.id) {
        newSession.id = newSession._id;
      }
      // Handle date format conversion
      if (newSession.created_at && !newSession.createdAt) {
        newSession.createdAt = new Date(newSession.created_at);
      } else if (newSession.createdAt && typeof newSession.createdAt === 'string') {
        newSession.createdAt = new Date(newSession.createdAt);
      } else {
        newSession.createdAt = new Date(newSession.createdAt || new Date());
      }
      
      if (newSession.updated_at && !newSession.updatedAt) {
        newSession.updatedAt = new Date(newSession.updated_at);
      } else if (newSession.updatedAt && typeof newSession.updatedAt === 'string') {
        newSession.updatedAt = new Date(newSession.updatedAt);
      } else {
        newSession.updatedAt = new Date(newSession.updatedAt || new Date());
      }
      
      setChatState(prev => ({
        ...prev,
        sessions: [newSession, ...prev.sessions],
        currentSessionId: newSession.id,
        isLoading: false
      }));
    } catch (error: any) {
      console.error('Error creating new chat session:', error);
      // Log details about the error for debugging
      if (error.response) {
        console.error('Response data:', error.response.data);
        console.error('Response status:', error.response.status);
      }
      
      setChatState(prev => ({
        ...prev,
        isLoading: false,
        error: 'Failed to create new chat session'
      }));
      
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to create new chat session",
        variant: "destructive",
      });
    }
  };

  const selectSession = (sessionId: string) => {
    setChatState(prev => ({
      ...prev,
      currentSessionId: sessionId,
    }));
  };
  
  const deleteSession = async (sessionId: string) => {
    if (!user || !user._id) {
      toast({
        title: "Error",
        description: "You must be logged in to delete a chat",
        variant: "destructive",
      });
      return;
    }
    
    try {
      setChatState(prev => ({
        ...prev,
        isLoading: true
      }));
      
      // Use the correct session ID format for the backend
      const session = chatState.sessions.find(s => s.id === sessionId);
      if (!session) {
        throw new Error("Session not found");
      }

      // We should use the _id field if available, otherwise use the id field
      const backendSessionId = session._id || session.id;
      
      console.log('Deleting chat session, API endpoint:', `${CHAT_API_ENDPOINT}/sessions/${backendSessionId}`);
      
      await api.delete(`${CHAT_API_ENDPOINT}/sessions/${backendSessionId}`);
      
      console.log('Chat session deleted successfully');
      
      // Check if we're deleting the current session
      const isCurrentSession = sessionId === chatState.currentSessionId;
      
      // Filter out the deleted session
      const updatedSessions = chatState.sessions.filter(s => s.id !== sessionId);
      
      setChatState(prev => ({
        ...prev,
        sessions: updatedSessions,
        // If we deleted the current session, select the first available one or null
        currentSessionId: isCurrentSession 
          ? (updatedSessions.length > 0 ? updatedSessions[0].id : null) 
          : prev.currentSessionId,
        isLoading: false
      }));
      
      toast({
        title: "Success",
        description: "Chat deleted successfully",
        variant: "default",
      });
    } catch (error: any) {
      console.error('Error deleting chat session:', error);
      
      // Log details about the error for debugging
      if (error.response) {
        console.error('Response data:', error.response.data);
        console.error('Response status:', error.response.status);
      }
      
      setChatState(prev => ({
        ...prev,
        isLoading: false,
        error: 'Failed to delete chat session'
      }));
      
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to delete chat session",
        variant: "destructive",
      });
    }
  };

  const getCurrentSession = () => {
    return chatState.sessions.find(s => s.id === chatState.currentSessionId);
  };

  const updateDateRange = async (data: DateRange) => {
    console.log('Updating date range with:', data);
    
    if (!user || !user._id) {
      console.error('Cannot update date range: user not logged in');
      return;
    }
    
    // Create a new object to ensure state update
    const newDateRange = { ...dateRange, ...data };
    console.log('New date range will be:', newDateRange);
    
    // Update local state
    setDateRange(newDateRange);
    
    try {
      // Update in API
      await api.put(`${CHAT_API_ENDPOINT}/settings`, {
        start_date: newDateRange.startDate,
        end_date: newDateRange.endDate
      });
      
      console.log('Saved date range to API:', newDateRange);
    } catch (error) {
      console.error('Error updating date range:', error);
      toast({
        title: "Error",
        description: "Failed to save analysis settings",
        variant: "destructive",
      });
    }
  };

  // Clear a message error
  const clearMessageError = (messageId: string) => {
    setMessagesWithErrors(prev => prev.filter(id => id !== messageId));
  };

  // Edit a message without sending it
  const editMessage = async (messageId: string, newContent: string) => {
    const currentSession = getCurrentSession();
    if (!currentSession) return;
    
    try {
      // Find the message index
      const messageIndex = currentSession.messages.findIndex(m => m.id === messageId);
      if (messageIndex === -1) return;
      
      // Update the message
      const updatedMessage = {
        ...currentSession.messages[messageIndex],
        content: newContent
      };
      
      // Create a new array with the updated message
      const updatedMessages = [...currentSession.messages];
      updatedMessages[messageIndex] = updatedMessage;
      
      // Update the state
      const currentSessions = [...chatState.sessions];
      const sessionIndex = currentSessions.findIndex(s => s.id === currentSession.id);
      
      if (sessionIndex !== -1) {
        // Create a new session object with the updated messages
        const updatedSession = {
          ...currentSessions[sessionIndex],
          messages: updatedMessages,
          updatedAt: new Date(),
        };
        
        // Update the session in the array
        currentSessions[sessionIndex] = updatedSession;
        
        // Update the state with the new array
        setChatState(prev => ({
          ...prev,
          sessions: currentSessions,
        }));
        
        // Update the session in the API
        try {
          const backendSessionId = updatedSession._id || updatedSession.id;
          
          await api.put(`${CHAT_API_ENDPOINT}/sessions/${backendSessionId}`, {
            messages: updatedSession.messages
          });
        } catch (error) {
          console.error('Error updating session in API:', error);
          throw error;
        }
      }
    } catch (error) {
      console.error('Error editing message:', error);
      throw error;
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

      // Find the last user message
      const lastUserMessage = session.messages.filter(msg => msg.role === 'user').pop();
      if (!lastUserMessage) {
        console.error('No user message found to respond to');
        return false;
      }

      // Prepare context from previous messages (exclude the latest user message)
      const contextMessages = session.messages
        .filter(msg => msg.id !== lastUserMessage.id)
        .slice(-5);
      
      console.log('Current date range state:', JSON.stringify(dateRange));
      
      // Get date range from React state
      let effectiveDateRange = {
        startDate: dateRange.startDate || null,
        endDate: dateRange.endDate || null
      };
      
      // Calculate days to analyze
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
      
      // Create payload for backend API - don't modify the original user message
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
      };
      
      console.log('Sending to backend API:', payload);
      
      // Send request to backend (not directly to n8n) with auth
      const response = await api.post(BACKEND_CHAT_ENDPOINT, payload);
      console.log('Backend API response:', response.data);
      
      // Process the response to extract the output
      const responseContent = extractOutputFromResponse(response.data);
      console.log('Processed response content:', responseContent);
      
      // Add bot response from webhook
      const botMessage: Message = {
        id: `msg_${Math.random().toString(36).substring(2, 11)}`,
        content: responseContent,
        role: 'bot',
        timestamp: new Date(),
      };
      
      // Get the current session with updated messages
      const currentSessions = [...chatState.sessions];
      const sessionIndex = currentSessions.findIndex(s => s.id === session.id);
      
      if (sessionIndex !== -1) {
        // Create a new session object with the updated messages
        const updatedSession = {
          ...currentSessions[sessionIndex],
          messages: [...session.messages, botMessage],
          updatedAt: new Date(),
        };
        
        // If it's still using the default title, update it based on the first message
        if (updatedSession.title.startsWith('New Chat')) {
          updatedSession.title = content.slice(0, 30) + (content.length > 30 ? '...' : '');
        }
        
        // Update the session in the array
        currentSessions[sessionIndex] = updatedSession;
        
        // Update the state with the new array
        setChatState(prev => ({
          ...prev,
          sessions: currentSessions,
          isLoading: false,
        }));
        
        // Clear any errors for the last user message
        clearMessageError(lastUserMessage.id);
        
        return true; // Explicitly return true for success
      }
      
      return false; // Return false if session was not found
    } catch (error) {
      console.error('Error calling backend API:', error);
      
      // Find the last user message to mark as having an error
      const lastUserMessage = session.messages.filter(msg => msg.role === 'user').pop();
      if (lastUserMessage) {
        setMessagesWithErrors(prev => [...prev, lastUserMessage.id]);
      }
      
      setChatState(prev => ({
        ...prev,
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to get response',
      }));
      
      toast({
        title: "Error",
        description: "Failed to get a response. You can edit, resend, or delete your message.",
        variant: "destructive",
      });
      
      return false; // Explicitly return false for error
    }
  };

  // Helper function to extract output from webhook response
  const extractOutputFromResponse = (response: any): string => {
    console.log('Extracting output from response:', response);
    
    // Check for different response formats
    if (typeof response === 'string') {
      try {
        // Try to parse the string as JSON
        const parsedResponse = JSON.parse(response);
        
        // Handle array format
        if (Array.isArray(parsedResponse) && parsedResponse.length > 0) {
          const firstItem = parsedResponse[0];
          
          // Check if the first item has an output property
          if (firstItem && firstItem.output) {
            console.log('Extracted output from array:', firstItem.output);
            return firstItem.output;
          }
        }
        
        // Handle object format 
        if (parsedResponse && parsedResponse.output) {
          console.log('Extracted output from parsed object:', parsedResponse.output);
          return parsedResponse.output;
        }
        
        // If we got here, just stringify the parsed response
        return JSON.stringify(parsedResponse);
      } catch (e) {
        // Not valid JSON, return the string as is
        console.log('Response is a string but not valid JSON, returning as is');
        return response;
      }
    }
    
    // Handle array format directly
    if (Array.isArray(response) && response.length > 0) {
      const firstItem = response[0];
      
      // Check if the first item has an output property
      if (firstItem && firstItem.output) {
        console.log('Extracted output from array object:', firstItem.output);
        return firstItem.output;
      }
    }
    
    // Handle object formats
    if (response && response.output) {
      console.log('Extracted output from object:', response.output);
      return response.output;
    }
    
    if (response && response.result) {
      console.log('Extracted result from object:', response.result);
      return response.result;
    }
    
    if (response && response.message) {
      console.log('Extracted message from object:', response.message);
      return response.message;
    }
    
    // Fallback
    console.log('No structured output found, returning stringified response');
    return JSON.stringify(response);
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
    
    // Get the current sessions array
    const currentSessions = [...chatState.sessions];
    const sessionIndex = currentSessions.findIndex(s => s.id === currentSession.id);
    
    if (sessionIndex !== -1) {
      // Create a new session object with the updated messages
      const updatedSession = {
        ...currentSessions[sessionIndex],
        messages: [...currentSessions[sessionIndex].messages, userMessage],
        updatedAt: new Date(),
      };
      
      // Update the session in the array
      currentSessions[sessionIndex] = updatedSession;
      
      // Update the state with the new array
      setChatState(prev => ({
        ...prev,
        sessions: currentSessions,
      }));
      
      // Try to get a response from the webhook
      let webhookSuccess = false;
      try {
        // Use the helper function to send message to webhook
        webhookSuccess = await sendMessageToWebhook(content, updatedSession);
      } catch (error) {
        console.error('Error sending message to webhook:', error);
        webhookSuccess = false;
      }
      
      // Only update the session in the API if the webhook call was successful
      if (webhookSuccess) {
        try {
          // Use the correct session ID format for the backend
          const backendSessionId = currentSession._id || currentSession.id;
          
          // Get the current state of the session after webhook response was added
          const currentSessionAfterWebhook = chatState.sessions.find(s => s.id === currentSession.id);
          if (currentSessionAfterWebhook) {
            await api.put(`${CHAT_API_ENDPOINT}/sessions/${backendSessionId}`, {
              messages: currentSessionAfterWebhook.messages
            });
          }
        } catch (error) {
          console.error('Error updating session in API:', error);
        }
      } else {
        // Add the message to the errors list
        setMessagesWithErrors(prev => [...prev, userMessage.id]);
        console.log('Webhook call failed, not saving to database');
      }
    }
  };

  // Toggle the analysis panel
  const toggleAnalysisPanel = () => {
    setIsAnalysisPanelOpen(!isAnalysisPanelOpen);
  };

  return (
    <ChatContext.Provider
      value={{
        ...chatState,
        sendMessage,
        createNewSession,
        selectSession,
        deleteSession,
        getCurrentSession,
        dateRange,
        updateDateRange,
        setChatState,
        messagesWithErrors,
        clearMessageError,
        editMessage,
        editingMessageId,
        setEditingMessageId,
        setMessagesWithErrors,
        toggleAnalysisPanel,
        isAnalysisPanelOpen,
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
