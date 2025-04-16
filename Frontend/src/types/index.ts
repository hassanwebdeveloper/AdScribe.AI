
export interface User {
  id: string;
  name: string;
  email: string;
  fbGraphApiKey: string;
  fbAdAccountId: string;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

export interface Message {
  id: string;
  content: string;
  role: 'user' | 'bot';
  timestamp: Date;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
}

export interface ChatState {
  sessions: ChatSession[];
  currentSessionId: string | null;
  isLoading: boolean;
  error: string | null;
}

export interface InitialQuestionnaire {
  adObjective?: string;
  targetAudience?: string;
  adBudget?: string;
  productFeatures?: string;
  competitorInfo?: string;
}
