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
    console.log('🔍 [DEBUG] sendMessageToWebhook called with content:', content.substring(0, 50) + '...');
    console.log('🔍 [DEBUG] Current session ID:', session.id);
    console.log('🔍 [DEBUG] Current session _id:', session._id);
    
    try {
      // Ensure we're authenticated
      if (!isAuthenticated || !user) {
        console.error('🚫 [ERROR] User not authenticated - cannot send message');
        toast({
          title: "Error",
          description: "You must be logged in to send messages",
          variant: "destructive",
        });
        return { success: false, session: null };
      }

      // Find the last user message
      const lastUserMessage = session.messages.filter(msg => msg.role === 'user').pop();
      if (!lastUserMessage) {
        console.error('🚫 [ERROR] No user message found to respond to');
        return { success: false, session: null };
      }

      // Prepare context from previous messages (exclude the latest user message)
      const contextMessages = session.messages
        .filter(msg => msg.id !== lastUserMessage.id)
        .slice(-5);
      
      console.log('🔍 [DEBUG] Current date range state:', JSON.stringify(dateRange));
      console.log('🔍 [DEBUG] Context messages count:', contextMessages.length);
      
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
        console.log('🔍 [DEBUG] Calculated days to analyze:', daysToAnalyze);
      } else {
        console.log('🔍 [DEBUG] Date range not set or incomplete');
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
      
      console.log('🔍 [DEBUG] Sending to backend API:', payload);
      console.log('🔍 [DEBUG] Webhook endpoint:', BACKEND_CHAT_ENDPOINT);
      
      // Send request to backend (not directly to n8n) with auth
      console.log('🔍 [DEBUG] Making API POST request to backend');
      const response = await api.post(BACKEND_CHAT_ENDPOINT, payload);
      console.log('🔍 [DEBUG] Backend API response status:', response.status);
      console.log('🔍 [DEBUG] Backend API response headers:', response.headers);
      console.log('🔍 [DEBUG] Backend API response data type:', typeof response.data);
      console.log('🔍 [DEBUG] Backend API response data:', 
        typeof response.data === 'string' ? response.data.substring(0, 200) + '...' : response.data);
      
      // Process the response to extract the output
      const responseContent = extractOutputFromResponse(response.data);
      console.log('🔍 [DEBUG] Processed response content:', 
        typeof responseContent === 'string' ? responseContent.substring(0, 200) + '...' : responseContent);
      
      // Add bot response from webhook
      const botMessage: Message = {
        id: `msg_${Math.random().toString(36).substring(2, 11)}`,
        content: responseContent,
        role: 'bot',
        timestamp: new Date(),
      };
      console.log('🔍 [DEBUG] Created bot message with ID:', botMessage.id);
      
      // Get the current session with updated messages - IMPORTANT: include both user message and bot response
      const updatedMessages = [...session.messages, botMessage];
      const updatedSession = {
        ...session,
        messages: updatedMessages,
        updatedAt: new Date(),
      };
      console.log('🔍 [DEBUG] Updated session message count:', updatedSession.messages.length);
      
      // If it's still using the default title, update it based on the first message
      if (updatedSession.title.startsWith('New Chat')) {
        updatedSession.title = content.slice(0, 30) + (content.length > 30 ? '...' : '');
        console.log('🔍 [DEBUG] Updated session title:', updatedSession.title);
      }
      
      // Update the state with the new session
      const currentSessions = [...chatState.sessions];
      const sessionIndex = currentSessions.findIndex(s => s.id === session.id);
      
      if (sessionIndex !== -1) {
        console.log('🔍 [DEBUG] Found session at index:', sessionIndex);
        // Update the session in the array
        currentSessions[sessionIndex] = updatedSession;
        
        // Update the state with the new array
        setChatState(prev => ({
          ...prev,
          sessions: currentSessions,
          isLoading: false,
        }));
        console.log('🔍 [DEBUG] Updated chat state with new message');
        
        // Clear any errors for the last user message
        clearMessageError(lastUserMessage.id);
        
        console.log('✅ [DEBUG] Webhook call succeeded, returning true');
        return { success: true, session: updatedSession };
      }
      
      console.error('🚫 [ERROR] Session not found in current sessions array');
      return { success: false, session: null };
    } catch (error) {
      console.error('🚫 [ERROR] Error calling backend API:', error);
      console.error('🚫 [ERROR] Error details:', error.response ? {
        status: error.response.status,
        data: error.response.data,
        headers: error.response.headers
      } : 'No response details available');
      
      // Find the last user message to mark as having an error
      const lastUserMessage = session.messages.filter(msg => msg.role === 'user').pop();
      if (lastUserMessage) {
        setMessagesWithErrors(prev => [...prev, lastUserMessage.id]);
        console.log('🔍 [DEBUG] Marked message as having error:', lastUserMessage.id);
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
      
      console.log('❌ [DEBUG] Webhook call failed, returning false');
      return { success: false, session: null };
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
    console.log('🔍 [DEBUG] sendMessage called with content:', content.substring(0, 50) + '...');
    
    if (!content.trim()) {
      console.log('🔍 [DEBUG] Empty content, returning early');
      return;
    }
    
    setChatState(prev => ({
      ...prev,
      isLoading: true,
      error: null,
    }));
    console.log('🔍 [DEBUG] Set loading state to true');
    
    const currentSession = getCurrentSession();
    
    if (!currentSession) {
      console.error('🚫 [ERROR] No active chat session');
      toast({
        title: "Error",
        description: "No active chat session",
        variant: "destructive",
      });
      return;
    }
    
    console.log('🔍 [DEBUG] Current session ID:', currentSession.id);
    console.log('🔍 [DEBUG] Current session _id:', currentSession._id);
    console.log('🔍 [DEBUG] Current session message count:', currentSession.messages.length);
    
    // Add user message
    const userMessage: Message = {
      id: `msg_${Math.random().toString(36).substring(2, 11)}`,
      content,
      role: 'user',
      timestamp: new Date(),
    };
    console.log('🔍 [DEBUG] Created user message with ID:', userMessage.id);
    
    // Get the current sessions array
    const currentSessions = [...chatState.sessions];
    const sessionIndex = currentSessions.findIndex(s => s.id === currentSession.id);
    
    if (sessionIndex !== -1) {
      console.log('🔍 [DEBUG] Found session at index:', sessionIndex);
      // Create a new session object with the updated messages
      const updatedSession = {
        ...currentSessions[sessionIndex],
        messages: [...currentSessions[sessionIndex].messages, userMessage],
        updatedAt: new Date(),
      };
      console.log('🔍 [DEBUG] Updated session message count:', updatedSession.messages.length);
      
      // Update the session in the array
      currentSessions[sessionIndex] = updatedSession;
      
      // Update the state with the new array
      setChatState(prev => ({
        ...prev,
        sessions: currentSessions,
      }));
      console.log('🔍 [DEBUG] Updated chat state with user message');
      
      // Try to get a response from the webhook
      let webhookSuccess = false;
      let updatedSessionAfterWebhook = null;
      try {
        console.log('🔍 [DEBUG] Calling sendMessageToWebhook');
        // Use the helper function to send message to webhook
        const result = await sendMessageToWebhook(content, updatedSession);
        webhookSuccess = result.success;
        updatedSessionAfterWebhook = result.session;
        console.log('🔍 [DEBUG] Webhook success:', webhookSuccess);
      } catch (error) {
        console.error('🚫 [ERROR] Error sending message to webhook:', error);
        webhookSuccess = false;
      }
      
      // Only update the session in the API if the webhook call was successful
      if (webhookSuccess && updatedSessionAfterWebhook) {
        try {
          console.log('🔍 [DEBUG] Webhook successful, saving to database');
          // Use the correct session ID format for the backend
          const backendSessionId = currentSession._id || currentSession.id;
          console.log('🔍 [DEBUG] Using backend session ID:', backendSessionId);
          
          console.log('🔍 [DEBUG] Messages to save count:', updatedSessionAfterWebhook.messages.length);
          
          // Log a sample of message format being sent
          if (updatedSessionAfterWebhook.messages.length > 0) {
            console.log('🔍 [DEBUG] First message format sample:', JSON.stringify(updatedSessionAfterWebhook.messages[0]));
          }
          
          // Make the API call
          console.log(`🔍 [DEBUG] Sending PUT request to: ${CHAT_API_ENDPOINT}/sessions/${backendSessionId}`);
          const response = await api.put(`${CHAT_API_ENDPOINT}/sessions/${backendSessionId}`, {
            messages: updatedSessionAfterWebhook.messages
          });
          
          console.log('✅ [DEBUG] Database save response:', response.status, response.statusText);
          console.log('✅ [DEBUG] Messages saved successfully to database');
        } catch (error) {
          console.error('🚫 [ERROR] Error updating session in API:', error);
          console.error('🚫 [ERROR] Error details:', error.response ? {
            status: error.response.status,
            data: error.response.data,
            headers: error.response.headers
          } : 'No response details available');
        }
      } else {
        // Add the message to the errors list
        setMessagesWithErrors(prev => [...prev, userMessage.id]);
        console.log('❌ [DEBUG] Webhook call failed, not saving to database, marked message with error:', userMessage.id);
      }
    } else {
      console.error('🚫 [ERROR] Session not found in current sessions array');
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
