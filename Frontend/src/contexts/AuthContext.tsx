import React, { createContext, useContext, useState, useEffect } from 'react';
import { AuthState, User, FacebookAdAccount } from '@/types';
import { useToast } from '@/components/ui/use-toast';
import axios from 'axios';
import { useNavigate, useLocation } from 'react-router-dom';

// Create an axios instance with the base URL
const api = axios.create({
  baseURL: '/api/v1',
});

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  updateUserSettings: (settings: Partial<User>) => Promise<void>;
  handleFacebookLogin: () => void;
  handleFacebookCallback: (code: string) => Promise<void>;
  getFacebookAdAccounts: () => Promise<FacebookAdAccount[]>;
  setFacebookAdAccount: (accountId: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { toast } = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const [authState, setAuthState] = useState<AuthState>({
    user: null,
    token: localStorage.getItem('token'),
    isAuthenticated: !!localStorage.getItem('token'),
    isLoading: false,
    error: null,
  });

  // Check for Facebook callback on mount
  useEffect(() => {
    const checkFacebookCallback = async () => {
      // Check if we're on the Facebook callback route
      if (location.pathname === '/auth/facebook/success' && location.search) {
        const params = new URLSearchParams(location.search);
        const token = params.get('token');
        
        if (token) {
          // Store token and fetch user
          localStorage.setItem('token', token);
          
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
            
            // Check if the user has selected an ad account
            if (userData.facebook_credentials?.account_id) {
              navigate('/chat');
            } else {
              // Redirect to ad account selection page
              navigate('/select-ad-account');
            }
            
            toast({
              title: "Success",
              description: "You have been logged in with Facebook successfully",
              variant: "default",
            });
          } catch (error) {
            let errorMessage = 'Failed to fetch user data';
            
            if (axios.isAxiosError(error) && error.response) {
              errorMessage = error.response.data.detail || errorMessage;
            } else if (error instanceof Error) {
              errorMessage = error.message;
            }
            
            toast({
              title: "Error",
              description: errorMessage,
              variant: "destructive",
            });
            
            // Clear token and navigate to login
            localStorage.removeItem('token');
            navigate('/login');
          }
        }
      } else if (location.pathname === '/auth/facebook/error' && location.search) {
        const params = new URLSearchParams(location.search);
        const error = params.get('error');
        
        if (error) {
          toast({
            title: "Error",
            description: decodeURIComponent(error),
            variant: "destructive",
          });
          
          // Navigate to login
          navigate('/login');
        }
      }
    };
    
    checkFacebookCallback();
  }, [location, navigate, toast]);

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

  // Regular login with email and password
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
  
  // Handle Facebook login
  const handleFacebookLogin = () => {
    window.location.href = '/api/v1/auth/facebook/login';
  };
  
  // Handle Facebook callback
  const handleFacebookCallback = async (code: string) => {
    // This is handled in the useEffect above
  };
  
  // Get Facebook ad accounts
  const getFacebookAdAccounts = async (): Promise<FacebookAdAccount[]> => {
    if (!authState.token) {
      toast({
        title: "Error",
        description: "You must be logged in to get ad accounts",
        variant: "destructive",
      });
      return [];
    }
    
    try {
      const response = await api.get('/auth/facebook/ad-accounts', {
        headers: {
          Authorization: `Bearer ${authState.token}`,
        },
      });
      
      return response.data.data || [];
    } catch (error) {
      let errorMessage = 'Failed to fetch ad accounts';
      
      if (axios.isAxiosError(error) && error.response) {
        errorMessage = error.response.data.detail || errorMessage;
      } else if (error instanceof Error) {
        errorMessage = error.message;
      }
      
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
      
      return [];
    }
  };
  
  // Set Facebook ad account
  const setFacebookAdAccount = async (accountId: string) => {
    if (!authState.token) {
      toast({
        title: "Error",
        description: "You must be logged in to set an ad account",
        variant: "destructive",
      });
      return;
    }
    
    try {
      const response = await api.post('/auth/facebook/ad-account', 
        { account_id: accountId },
        {
          headers: {
            Authorization: `Bearer ${authState.token}`,
          },
        }
      );
      
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
      });
      
      toast({
        title: "Success",
        description: "Ad account has been set successfully",
        variant: "default",
      });
      
      // Redirect to dashboard
      navigate('/chat');
    } catch (error) {
      let errorMessage = 'Failed to set ad account';
      
      if (axios.isAxiosError(error) && error.response) {
        errorMessage = error.response.data.detail || errorMessage;
      } else if (error instanceof Error) {
        errorMessage = error.message;
      }
      
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
    
    // Redirect to login page
    navigate('/login');
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
    <AuthContext.Provider value={{
      ...authState,
      login,
      register,
      logout,
      updateUserSettings,
      handleFacebookLogin,
      handleFacebookCallback,
      getFacebookAdAccounts,
      setFacebookAdAccount,
    }}>
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
