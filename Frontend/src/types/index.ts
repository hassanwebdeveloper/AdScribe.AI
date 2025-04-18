export interface User {
  _id: string;
  name: string;
  email: string;
  fb_graph_api_key?: string;
  fb_ad_account_id?: string;
  created_at: string;
  updated_at: string;
  fbGraphApiKey?: string;
  fbAdAccountId?: string;
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
  role: 'user' | 'bot' | 'system';
  timestamp: Date;
}

export interface ChatSession {
  id: string;
  _id?: string;
  user_id?: string;
  title: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
  created_at?: string;
  updated_at?: string;
}

export interface ChatState {
  sessions: ChatSession[];
  currentSessionId: string | null;
  isLoading: boolean;
  error: string | null;
  messagesWithErrors?: string[];
}

export interface DateRange {
  startDate?: string;
  endDate?: string;
}
