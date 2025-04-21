import React, { createContext, useContext, useState, useEffect } from 'react';
import { AuthState, User } from '@/types';
import { useToast } from '@/components/ui/use-toast';
import axios from 'axios';

// Create an axios instance with the base URL
const api = axios.create({
  baseURL: '/api/v1',
});

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  updateUserSettings: (settings: Partial<User>) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { toast } = useToast();
  const [authState, setAuthState] = useState<AuthState>({
    user: null,
    token: localStorage.getItem('token'),
    isAuthenticated: !!localStorage.getItem('token'),
    isLoading: false,
    error: null,
  });

  // Fetch current user when token changes
  useEffect(() => {
    const fetchCurrentUser = async () => {
      const token = localStorage.getItem('token');
      if (!token) return;
      
      try {
        const response = await api.get('/auth/me', {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        
        // Convert the response data to match our frontend model
        const userData = {
          ...response.data,
          fbGraphApiKey: response.data.fb_graph_api_key,
          fbAdAccountId: response.data.fb_ad_account_id,
        };
        
        setAuthState({
          user: userData,
          token,
          isAuthenticated: true,
          isLoading: false,
          error: null,
        });
      } catch (error) {
        // If authentication fails, clear the token
        localStorage.removeItem('token');
        setAuthState({
          user: null,
          token: null,
          isAuthenticated: false,
          isLoading: false,
          error: 'Session expired. Please log in again.',
        });
      }
    };
    
    fetchCurrentUser();
  }, []);

  // For demo purposes, we're using localStorage instead of a real backend
  // In a real app, you would connect to a backend service
  const login = async (email: string, password: string) => {
    setAuthState({ ...authState, isLoading: true, error: null });
    
    try {
      // Make API call to login endpoint
      const response = await api.post('/auth/login', {
        email,
        password
      });
      
      const { user, token } = response.data;
      
      // Convert the response data to match our frontend model
      const userData = {
        ...user,
        fbGraphApiKey: user.fb_graph_api_key,
        fbAdAccountId: user.fb_ad_account_id,
      };
      
      // Store token in localStorage
      localStorage.setItem('token', token);
      
      // Update auth state
      setAuthState({
        user: userData,
        token,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
      
      toast({
        title: "Success",
        description: "You have been logged in successfully",
        variant: "default",
      });
    } catch (error) {
      let errorMessage = 'Login failed';
      
      if (axios.isAxiosError(error) && error.response) {
        // Get the error message from the API response
        errorMessage = error.response.data.detail || 'Login failed';
      } else if (error instanceof Error) {
        errorMessage = error.message;
      }
      
      setAuthState({
        ...authState,
        isLoading: false,
        error: errorMessage,
      });
      
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
    }
  };
  
  const register = async (name: string, email: string, password: string) => {
    setAuthState({ ...authState, isLoading: true, error: null });
    
    try {
      // Make API call to register endpoint
      const response = await api.post('/auth/signup', {
        name,
        email,
        password,
      });
      
      const { user, token } = response.data;
      
      // Convert the response data to match our frontend model
      const userData = {
        ...user,
        fbGraphApiKey: user.fb_graph_api_key,
        fbAdAccountId: user.fb_ad_account_id,
      };
      
      // Store token in localStorage
      localStorage.setItem('token', token);
      
      // Update auth state
      setAuthState({
        user: userData,
        token,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
      
      toast({
        title: "Success",
        description: "Your account has been created successfully",
        variant: "default",
      });
    } catch (error) {
      let errorMessage = 'Registration failed';
      
      if (axios.isAxiosError(error) && error.response) {
        // Get the error message from the API response
        errorMessage = error.response.data.detail || 'Registration failed';
      } else if (error instanceof Error) {
        errorMessage = error.message;
      }
      
      setAuthState({
        ...authState,
        isLoading: false,
        error: errorMessage,
      });
      
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
    }
  };
  
  const logout = () => {
    localStorage.removeItem('token');
    
    setAuthState({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
    });
    
    toast({
      title: "Logged out",
      description: "You have been logged out successfully",
      variant: "default",
    });
  };
  
  const updateUserSettings = async (settings: Partial<User>) => {
    if (!authState.user) {
      toast({
        title: "Error",
        description: "You must be logged in to update your settings",
        variant: "destructive",
      });
      return;
    }
    
    setAuthState({ ...authState, isLoading: true, error: null });
    
    try {
      // Convert the settings keys to match the backend API
      const apiSettings: any = {};
      if (settings.fbGraphApiKey !== undefined) {
        apiSettings.fb_graph_api_key = settings.fbGraphApiKey;
      }
      if (settings.fbAdAccountId !== undefined) {
        apiSettings.fb_ad_account_id = settings.fbAdAccountId;
      }
      
      // Make API call to update user settings
      const response = await api.patch('/auth/settings', apiSettings, {
        headers: {
          Authorization: `Bearer ${authState.token}`,
        },
      });
      
      // Convert the response data to match our frontend model
      const updatedUser = {
        ...response.data,
        fbGraphApiKey: response.data.fb_graph_api_key,
        fbAdAccountId: response.data.fb_ad_account_id,
      };
      
      // Update auth state
      setAuthState({
        ...authState,
        user: updatedUser,
        isLoading: false,
      });
      
      toast({
        title: "Success",
        description: "Your settings have been updated successfully",
        variant: "default",
      });
    } catch (error) {
      let errorMessage = 'Failed to update settings';
      
      if (axios.isAxiosError(error) && error.response) {
        // Get the error message from the API response
        errorMessage = error.response.data.detail || 'Failed to update settings';
      } else if (error instanceof Error) {
        errorMessage = error.message;
      }
      
      setAuthState({
        ...authState,
        isLoading: false,
        error: errorMessage,
      });
      
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
    }
  };
  
  return (
    <AuthContext.Provider
      value={{
        ...authState,
        login,
        register,
        logout,
        updateUserSettings,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
