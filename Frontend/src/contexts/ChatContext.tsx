import React, { createContext, useContext, useState, useEffect } from 'react';
import { Message, ChatSession, ChatState, DateRange } from '@/types';
import { useToast } from '@/components/ui/use-toast';
import { useAuth } from './AuthContext';
import api from '@/utils/api';

// Backend API endpoints
const BACKEND_CHAT_ENDPOINT = '/webhook/chat';
const CHAT_API_ENDPOINT = '/chat';

interface ChatContextType extends ChatState {
  sendMessage: (content: string, productInfo?: { product?: string; product_type?: string }) => Promise<void>;
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
              // Convert start_date and end_date if they exist
              if (msg.start_date) {
                msg.start_date = new Date(msg.start_date);
              }
              if (msg.end_date) {
                msg.end_date = new Date(msg.end_date);
              }
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
      
      // Get the existing message to preserve fields like start_date and end_date
      const existingMessage = currentSession.messages[messageIndex];
      
      // Update the message, preserving all other fields
      const updatedMessage = {
        ...existingMessage,
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
          
          // Use the utility function to serialize messages
          const serializedMessages = serializeMessagesForAPI(updatedSession.messages);
          console.log('🔍 [DEBUG] Serialized messages for API call, count:', serializedMessages.length);
          
          await api.put(`${CHAT_API_ENDPOINT}/sessions/${backendSessionId}`, {
            messages: serializedMessages
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
  const sendMessageToWebhook = async (content: string, session: ChatSession, productInfo?: { product?: string; product_type?: string }) => {
    console.log('🔍 [DEBUG] sendMessageToWebhook called with content:', content.substring(0, 50) + '...');
    console.log('🔍 [DEBUG] Current session ID:', session.id);
    console.log('🔍 [DEBUG] Current session _id:', session._id);
    console.log('🔍 [DEBUG] Product info:', productInfo);
    
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
        productInfo: productInfo || null
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
      const responseData = extractOutputFromResponse(response.data);
      console.log('🔍 [DEBUG] Processed response content:', 
        typeof responseData.content === 'string' 
          ? responseData.content.substring(0, 200) + '...' 
          : responseData.content);
      
      // Process ad data if present
      let processedAd = undefined;
      if (responseData.ad) {
        console.log('🔍 [DEBUG] Found ad data in response');
        
        try {
          // Ensure ad is in the correct format
          if (typeof responseData.ad === 'string') {
            console.log('🔍 [DEBUG] Ad is a string:', responseData.ad.substring(0, 100));

            // Check if this is the specific malformed JSON format we're seeing
            // Example: {"title": Cash refund if not satisfied, "description":100% Pure White...}
            if (responseData.ad.startsWith('{') && responseData.ad.includes('"title":') && 
                !responseData.ad.includes(':"')) {
              console.log('🔍 [DEBUG] Found malformed JSON-like string, keeping as is');
              // Keep the string format for the AdCard component to handle
              processedAd = responseData.ad;
            } else {
              // Try to parse it as JSON if it's not the specific malformed format
              try {
                processedAd = JSON.parse(responseData.ad);
                console.log('🔍 [DEBUG] Successfully parsed ad JSON string');
              } catch (e) {
                console.error('🚫 [ERROR] Failed to parse ad JSON string:', e);
                console.log('🔍 [DEBUG] Using string ad data as is');
                processedAd = responseData.ad;
              }
            }
          } else {
            // It's already an object
            processedAd = responseData.ad;
            console.log('🔍 [DEBUG] Using ad object as is');
          }
        } catch (e) {
          console.error('🚫 [ERROR] Error processing ad data:', e);
          // Keep the original ad data
          processedAd = responseData.ad;
        }
      }
      
      // Add bot response from webhook
      const botMessage: Message = {
        id: `msg_${Math.random().toString(36).substring(2, 11)}`,
        content: responseData.content,
        role: 'bot',
        timestamp: new Date(),
        start_date: dateRange.startDate ? new Date(dateRange.startDate) : undefined,
        end_date: dateRange.endDate ? new Date(dateRange.endDate) : undefined,
        ad: processedAd
      };
      console.log('🔍 [DEBUG] Created bot message with ID:', botMessage.id);
      if (botMessage.ad) {
        console.log('🔍 [DEBUG] Message includes ad data of type:', typeof botMessage.ad);
      }
      
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
        
        // Save the session to the database
        try {
          console.log('🔍 [DEBUG] Saving updated session to database');
          const backendSessionId = session._id || session.id;
          
          // Use the utility function to serialize messages
          const serializedMessages = serializeMessagesForAPI(updatedSession.messages);
          console.log('🔍 [DEBUG] Serialized messages for API call, count:', serializedMessages.length);
          
          await api.put(`${CHAT_API_ENDPOINT}/sessions/${backendSessionId}`, {
            messages: serializedMessages,
            title: updatedSession.title !== session.title ? updatedSession.title : undefined
          });
          
          console.log('✅ [DEBUG] Session saved to database successfully');
        } catch (error) {
          console.error('🚫 [ERROR] Error saving session to database:', error);
          console.error('🚫 [ERROR] Error details:', error.response ? {
            status: error.response.status,
            data: error.response.data,
            headers: error.response.headers
          } : 'No response details available');
          
          toast({
            title: "Warning",
            description: "Response received but couldn't be saved to database",
            variant: "destructive",
          });
        }
        
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
  const extractOutputFromResponse = (response: any): { content: string; ad?: any } => {
    console.log('Extracting output from response:', response);
    
    // Initialize the result object
    let result = {
      content: '',
      ad: undefined
    };
    
    try {
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
              result.content = firstItem.output;
              
              // Check for ad property
              if (firstItem.ad) {
                console.log('Found ad data in array response:', firstItem.ad);
                try {
                  result.ad = typeof firstItem.ad === 'string' ? JSON.parse(firstItem.ad) : firstItem.ad;
                } catch (err) {
                  console.error('Error parsing ad data:', err);
                }
              }
              
              return result;
          }
        }
        
        // Handle object format 
        if (parsedResponse && parsedResponse.output) {
          console.log('Extracted output from parsed object:', parsedResponse.output);
            result.content = parsedResponse.output;
            
            // Check for ad property
            if (parsedResponse.ad) {
              console.log('Found ad data in object response:', parsedResponse.ad);
              try {
                result.ad = typeof parsedResponse.ad === 'string' ? JSON.parse(parsedResponse.ad) : parsedResponse.ad;
              } catch (err) {
                console.error('Error parsing ad data:', err);
              }
            }
            
            return result;
        }
        
        // If we got here, just stringify the parsed response
          result.content = JSON.stringify(parsedResponse);
          return result;
      } catch (e) {
        // Not valid JSON, return the string as is
        console.log('Response is a string but not valid JSON, returning as is');
          result.content = response;
          return result;
      }
    }
    
    // Handle array format directly
    if (Array.isArray(response) && response.length > 0) {
      const firstItem = response[0];
      
      // Check if the first item has an output property
      if (firstItem && firstItem.output) {
        console.log('Extracted output from array object:', firstItem.output);
          result.content = firstItem.output;
          
          // Check for ad property
          if (firstItem.ad) {
            console.log('Found ad data in array object response:', firstItem.ad);
            try {
              result.ad = typeof firstItem.ad === 'string' ? JSON.parse(firstItem.ad) : firstItem.ad;
            } catch (err) {
              console.error('Error parsing ad data:', err);
            }
          }
          
          return result;
      }
    }
    
    // Handle object formats
    if (response && response.output) {
      console.log('Extracted output from object:', response.output);
        result.content = response.output;
        
        // Check for ad property
        if (response.ad) {
          console.log('Found ad data in response:', response.ad);
          try {
            // Handle different ad data formats
            if (typeof response.ad === 'string') {
              // Try to parse as JSON if it's a string
              console.log('Ad is a string, trying to parse as JSON');
              try {
                // First try to parse as is
                result.ad = JSON.parse(response.ad);
              } catch (innerErr) {
                console.error('Error parsing ad string as JSON:', innerErr);
                
                // If direct parsing fails, try to clean the string and parse again
                const cleanedAd = response.ad.trim().replace(/^["']|["']$/g, '');
                if (cleanedAd.startsWith('{') && cleanedAd.endsWith('}')) {
                  try {
                    console.log('Trying to parse cleaned JSON:', cleanedAd.substring(0, 100));
                    result.ad = JSON.parse(cleanedAd);
                  } catch (cleanErr) {
                    console.error('Error parsing cleaned ad string:', cleanErr);
                    // Just use the string as is
                    result.ad = response.ad;
                  }
                } else {
                  // Not JSON, use as is
                  result.ad = response.ad;
                }
              }
            } else {
              // Object, already parsed
              result.ad = response.ad;
            }
            
            // Validate the ad object has all required fields
            if (result.ad && typeof result.ad === 'object') {
              console.log('Ad parsed successfully:', result.ad);
              const requiredFields = ['title', 'description', 'video_url', 'is_active', 'purchases'];
              const hasAllFields = requiredFields.every(field => Object.prototype.hasOwnProperty.call(result.ad, field));
              
              if (!hasAllFields) {
                console.warn('Ad missing required fields, adding defaults', result.ad);
                // Add missing fields with defaults
                const adObj = result.ad as any;
                result.ad = {
                  title: adObj.title || 'Ad',
                  description: adObj.description || 'Ad content',
                  video_url: adObj.video_url || '',
                  is_active: adObj.is_active !== undefined ? adObj.is_active : true,
                  purchases: adObj.purchases !== undefined ? adObj.purchases : 0
                };
              }
            }
          } catch (err) {
            console.error('Error processing ad data:', err);
          }
        }
        
        return result;
    }
    
    if (response && response.result) {
      console.log('Extracted result from object:', response.result);
        result.content = response.result;
        
        // Check for ad property
        if (response.ad) {
          console.log('Found ad data in result response:', response.ad);
          try {
            result.ad = typeof response.ad === 'string' ? JSON.parse(response.ad) : response.ad;
          } catch (err) {
            console.error('Error parsing ad data:', err);
          }
        }
        
        return result;
    }
    
    if (response && response.message) {
      console.log('Extracted message from object:', response.message);
        result.content = response.message;
        
        // Check for ad property
        if (response.ad) {
          console.log('Found ad data in message response:', response.ad);
          try {
            result.ad = typeof response.ad === 'string' ? JSON.parse(response.ad) : response.ad;
          } catch (err) {
            console.error('Error parsing ad data:', err);
          }
        }
        
        return result;
    }
    
    // Fallback
    console.log('No structured output found, returning stringified response');
      result.content = typeof response === 'string' ? response : JSON.stringify(response);
    } catch (error) {
      console.error('Error in extractOutputFromResponse:', error);
      result.content = typeof response === 'string' ? response : JSON.stringify(response);
    }
    
    return result;
  };

  const sendMessage = async (content: string, productInfo?: { product?: string; product_type?: string }) => {
    console.log('🔍 [DEBUG] sendMessage called with content:', content.substring(0, 50) + '...');
    
    if (!user || !user._id) {
      toast({
        title: "Error",
        description: "You must be logged in to send messages",
        variant: "destructive",
      });
      return;
    }
    
    if (!content.trim()) {
      toast({
        title: "Error",
        description: "Message cannot be empty",
        variant: "destructive",
      });
      return;
    }
    
    try {
      // Get current session or create one if none exists
      let session: ChatSession;
      if (!chatState.currentSessionId || !chatState.sessions.find(s => s.id === chatState.currentSessionId)) {
        console.log('🔍 [DEBUG] No current session, creating new one');
        
        setChatState(prev => ({
          ...prev,
          isLoading: true
        }));
        
        // Create a new session
        const response = await api.post(`${CHAT_API_ENDPOINT}/sessions`, {
          title: `New Chat ${chatState.sessions.length + 1}`
        });
        
        session = response.data;
        // MongoDB returns _id, but our frontend uses id
        if (session._id && !session.id) {
          session.id = session._id;
        }
        
        // Convert date strings to Date objects
        session.createdAt = new Date(session.created_at || session.createdAt);
        session.updatedAt = new Date(session.updated_at || session.updatedAt);
        session.messages = session.messages || [];
        
        console.log('✅ [DEBUG] New session created:', session.id);
        
        // Update the sessions list and select the new session
        setChatState(prev => ({
          ...prev,
          sessions: [session, ...prev.sessions],
          currentSessionId: session.id,
          isLoading: false
        }));
      } else {
        session = chatState.sessions.find(s => s.id === chatState.currentSessionId)!;
        console.log('🔍 [DEBUG] Using existing session:', session.id);
      }
      
      // Generate a new message ID
      const messageId = `msg_${Date.now()}`;
      
      // Get the current date range
      const currentStartDate = dateRange.startDate ? new Date(dateRange.startDate) : null;
      const currentEndDate = dateRange.endDate ? new Date(dateRange.endDate) : null;
      
      // Create the new user message
      const userMessage: Message = {
        id: messageId,
        content,
        role: 'user',
        timestamp: new Date(),
        start_date: currentStartDate || undefined,
        end_date: currentEndDate || undefined
      };
      
      // Add user message to session
      const updatedMessages = [...session.messages, userMessage];
      const updatedSession = {
        ...session,
        messages: updatedMessages,
        updatedAt: new Date(),
      };
      
      // Update the session in state immediately to show user message
      setChatState(prev => ({
        ...prev,
        sessions: prev.sessions.map(s => 
          s.id === updatedSession.id ? updatedSession : s
        ),
        isLoading: true
      }));
      
      // Scroll to bottom for the new message
      setTimeout(() => {
        const chatContainer = document.getElementById('chat-messages-container');
        if (chatContainer) {
          chatContainer.scrollTop = chatContainer.scrollHeight;
        }
      }, 100);
      
      // Call the webhook endpoint with the message content
      console.log('🔍 [DEBUG] Calling sendMessageToWebhook');
      
      const result = await sendMessageToWebhook(content, updatedSession, productInfo);
      
      // Update the session with the final messages (including API response)
      setChatState(prev => ({
        ...prev,
        sessions: prev.sessions.map(s => 
          s.id === updatedSession.id ? 
            result.success && result.session ? 
              result.session : 
              {
                ...s,
                messages: updatedMessages,
                updatedAt: new Date()
              }
          : s
        ),
        isLoading: false
      }));
      
      // If webhook call wasn't successful, we need to save the user message to the database
      if (!result.success) {
        try {
          console.log('🔍 [DEBUG] Webhook call failed, saving just the user message to database');
          const backendSessionId = session._id || session.id;
          
          // Use the utility function to serialize messages
          const serializedMessages = serializeMessagesForAPI(updatedMessages);
          console.log('🔍 [DEBUG] Serialized messages for API call, count:', serializedMessages.length);
          
          await api.put(`${CHAT_API_ENDPOINT}/sessions/${backendSessionId}`, {
            messages: serializedMessages
          });
          
          console.log('✅ [DEBUG] User message saved to database successfully');
        } catch (error) {
          console.error('🚫 [ERROR] Error saving user message to database:', error);
          toast({
            title: "Warning",
            description: "Your message was sent but couldn't be saved to database",
            variant: "destructive",
          });
        }
      }
      
    } catch (error: any) {
      console.error('Error sending message:', error);
      
      // Add the message ID to the errors list
      const errorMessageId = `msg_${Date.now()}`;
      setMessagesWithErrors(prev => [...prev, errorMessageId]);
      
      setChatState(prev => ({
        ...prev,
        isLoading: false,
        error: error.message || 'Failed to send message'
      }));
      
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to send message",
        variant: "destructive",
      });
    }
  };

  // Toggle the analysis panel
  const toggleAnalysisPanel = () => {
    setIsAnalysisPanelOpen(!isAnalysisPanelOpen);
  };

  // Utility function to serialize messages for API calls
  const serializeMessagesForAPI = (messages: Message[]) => {
    const serializedMessages = messages.map(msg => {
      // Create a deep copy of the message object
      const msgCopy: any = { ...msg };
      
      // Convert Date objects to ISO strings
      if (msgCopy.timestamp instanceof Date) {
        msgCopy.timestamp = msgCopy.timestamp.toISOString();
      }
      
      if (msgCopy.start_date instanceof Date) {
        msgCopy.start_date = msgCopy.start_date.toISOString();
      } else if (msgCopy.start_date) {
        console.log('🔍 [DEBUG] start_date is not a Date object:', msgCopy.start_date, typeof msgCopy.start_date);
      }
      
      if (msgCopy.end_date instanceof Date) {
        msgCopy.end_date = msgCopy.end_date.toISOString();
      } else if (msgCopy.end_date) {
        console.log('🔍 [DEBUG] end_date is not a Date object:', msgCopy.end_date, typeof msgCopy.end_date);
      }
      
      return msgCopy;
    });
    
    // Log a sample message to debug date fields
    if (serializedMessages.length > 0) {
      const sampleMsg = serializedMessages[serializedMessages.length - 1];
      console.log('🔍 [DEBUG] Sample serialized message:');
      console.log('    - ID:', sampleMsg.id);
      console.log('    - Role:', sampleMsg.role);
      console.log('    - timestamp:', sampleMsg.timestamp);
      console.log('    - start_date:', sampleMsg.start_date);
      console.log('    - end_date:', sampleMsg.end_date);
    }
    
    return serializedMessages;
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
