
import React, { createContext, useContext, useState, useEffect } from 'react';
import { Message, ChatSession, ChatState, InitialQuestionnaire } from '@/types';
import { useToast } from '@/components/ui/use-toast';
import { useAuth } from './AuthContext';

interface ChatContextType extends ChatState {
  sendMessage: (content: string) => Promise<void>;
  createNewSession: () => void;
  selectSession: (sessionId: string) => void;
  getCurrentSession: () => ChatSession | undefined;
  isFirstPrompt: boolean;
  questionnaire: InitialQuestionnaire;
  updateQuestionnaire: (data: Partial<InitialQuestionnaire>) => void;
  submitQuestionnaire: () => Promise<void>;
  processingQuestionnaire: boolean;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

export const ChatProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { toast } = useToast();
  const { user } = useAuth();
  const [isFirstPrompt, setIsFirstPrompt] = useState(true);
  const [questionnaire, setQuestionnaire] = useState<InitialQuestionnaire>({});
  const [processingQuestionnaire, setProcessingQuestionnaire] = useState(false);
  
  const [chatState, setChatState] = useState<ChatState>({
    sessions: [],
    currentSessionId: null,
    isLoading: false,
    error: null,
  });

  // Load chat sessions from local storage on component mount
  useEffect(() => {
    if (user) {
      const savedSessions = localStorage.getItem(`chatSessions_${user.id}`);
      
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
    }
  }, [user]);

  // Save chat sessions to local storage whenever they change
  useEffect(() => {
    if (user && chatState.sessions.length > 0) {
      localStorage.setItem(`chatSessions_${user.id}`, JSON.stringify(chatState.sessions));
    }
  }, [chatState.sessions, user]);

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
    
    setIsFirstPrompt(true);
    setQuestionnaire({});
  };

  const selectSession = (sessionId: string) => {
    setChatState(prev => ({
      ...prev,
      currentSessionId: sessionId,
    }));
    
    // Check if the selected session has any messages
    const session = chatState.sessions.find(s => s.id === sessionId);
    setIsFirstPrompt(session?.messages.length === 0);
  };

  const getCurrentSession = () => {
    return chatState.sessions.find(s => s.id === chatState.currentSessionId);
  };

  const updateQuestionnaire = (data: Partial<InitialQuestionnaire>) => {
    setQuestionnaire(prev => ({ ...prev, ...data }));
  };

  const submitQuestionnaire = async () => {
    setProcessingQuestionnaire(true);
    
    try {
      // Simulate API call to n8n workflow
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      const response = {
        success: true,
        message: "Based on your inputs, I've analyzed your requirements for Facebook ads. Here's a suggested ad script tailored to your target audience:\n\n**Headline**: Unleash Your Brand's Potential\n\n**Primary Text**: Looking to boost engagement? Our AI-powered platform helps you create compelling Facebook ads that convert. With smart targeting and proven copy techniques, you'll see results fast.\n\nOur clients typically see a 30% increase in CTR within the first month. Ready to elevate your Facebook ad strategy?\n\n**Call to Action**: Get Started Today"
      };
      
      if (!response.success) {
        throw new Error('Failed to process questionnaire');
      }
      
      // Add bot response
      const currentSession = getCurrentSession();
      if (currentSession) {
        const updatedMessages = [
          ...currentSession.messages,
          {
            id: `msg_${Math.random().toString(36).substring(2, 11)}`,
            content: response.message,
            role: 'bot' as const,
            timestamp: new Date(),
          },
        ];
        
        // Update session
        setChatState(prev => ({
          ...prev,
          sessions: prev.sessions.map(s => 
            s.id === currentSession.id 
              ? { 
                  ...s, 
                  messages: updatedMessages,
                  updatedAt: new Date(),
                  // Update title based on first user message
                  title: s.title === `New Chat ${prev.sessions.indexOf(s) + 1}` && updatedMessages.length > 1 
                    ? updatedMessages[0].content.slice(0, 30) + (updatedMessages[0].content.length > 30 ? '...' : '') 
                    : s.title
                } 
              : s
          ),
          isLoading: false,
        }));
        
        setIsFirstPrompt(false);
      }
    } catch (error) {
      setChatState(prev => ({
        ...prev,
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to process questionnaire',
      }));
      
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : 'Failed to process questionnaire',
        variant: "destructive",
      });
    } finally {
      setProcessingQuestionnaire(false);
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
    
    // For first prompt, we don't add a bot response yet - we'll wait for the questionnaire
    if (isFirstPrompt) {
      setChatState(prev => ({
        ...prev,
        isLoading: false,
      }));
      return;
    }
    
    try {
      // Simulate API call to n8n workflow
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      // Prepare context from previous messages (exclude the latest user message)
      const contextMessages = currentSession.messages.slice(-4);
      
      // Create payload for n8n
      const payload = {
        userMessage: content,
        context: contextMessages.map(msg => ({
          role: msg.role,
          content: msg.content,
        })),
        questionnaire: questionnaire,
      };
      
      console.log('Sending to n8n:', payload);
      
      // Simulate n8n response
      const responseText = "I've analyzed your request and here's my suggestion for improving your ad:\n\n**Updated Headline**: \"Transform Your Facebook Ad Performance\"\n\n**Primary Text**: \"Looking to stand out in crowded feeds? Our data-driven approach combines AI insights with proven copywriting techniques tailored specifically for your target audience demographics.\n\nClients using our ad scripts have reported up to 42% higher engagement rates and 25% lower cost-per-click compared to their previous campaigns.\n\nWhat specific metrics would you like to focus on improving next?\"";
      
      // Add bot response
      const botMessage: Message = {
        id: `msg_${Math.random().toString(36).substring(2, 11)}`,
        content: responseText,
        role: 'bot',
        timestamp: new Date(),
      };
      
      setChatState(prev => ({
        ...prev,
        sessions: prev.sessions.map(s => 
          s.id === currentSession.id 
            ? { 
                ...s, 
                messages: [...s.messages, botMessage],
                updatedAt: new Date(),
                // Update title based on first user message
                title: s.title === `New Chat ${prev.sessions.indexOf(s) + 1}` 
                  ? userMessage.content.slice(0, 30) + (userMessage.content.length > 30 ? '...' : '') 
                  : s.title
              } 
            : s
        ),
        isLoading: false,
      }));
    } catch (error) {
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
    }
  };

  return (
    <ChatContext.Provider
      value={{
        ...chatState,
        sendMessage,
        createNewSession,
        selectSession,
        getCurrentSession,
        isFirstPrompt,
        questionnaire,
        updateQuestionnaire,
        submitQuestionnaire,
        processingQuestionnaire,
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
