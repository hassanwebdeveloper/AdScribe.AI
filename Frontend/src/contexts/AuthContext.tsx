
import React, { createContext, useContext, useState } from 'react';
import { AuthState, User } from '@/types';
import { useToast } from '@/components/ui/use-toast';

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

  // For demo purposes, we're using localStorage instead of a real backend
  // In a real app, you would connect to a backend service
  const login = async (email: string, password: string) => {
    setAuthState({ ...authState, isLoading: true, error: null });
    
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Check if there's a user in localStorage with this email
      const users = JSON.parse(localStorage.getItem('users') || '[]');
      const user = users.find((u: any) => u.email === email);
      
      if (!user || user.password !== password) {
        throw new Error('Invalid email or password');
      }
      
      // Remove password before storing in state
      const { password: _, ...userWithoutPassword } = user;
      
      // Create a fake token
      const token = `token_${Math.random().toString(36).substring(2, 15)}`;
      
      localStorage.setItem('token', token);
      
      setAuthState({
        user: userWithoutPassword,
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
      setAuthState({
        ...authState,
        isLoading: false,
        error: error instanceof Error ? error.message : 'Login failed',
      });
      
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : 'Login failed',
        variant: "destructive",
      });
    }
  };
  
  const register = async (name: string, email: string, password: string) => {
    setAuthState({ ...authState, isLoading: true, error: null });
    
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Check if user already exists
      const users = JSON.parse(localStorage.getItem('users') || '[]');
      
      if (users.some((u: any) => u.email === email)) {
        throw new Error('User with this email already exists');
      }
      
      // Create new user
      const newUser = {
        id: `user_${Math.random().toString(36).substring(2, 11)}`,
        name,
        email,
        password, // In a real app, this would be hashed
        fbGraphApiKey: '',
        fbAdAccountId: '',
      };
      
      // Save user to localStorage
      localStorage.setItem('users', JSON.stringify([...users, newUser]));
      
      // Remove password before storing in state
      const { password: _, ...userWithoutPassword } = newUser;
      
      // Create a fake token
      const token = `token_${Math.random().toString(36).substring(2, 15)}`;
      localStorage.setItem('token', token);
      
      setAuthState({
        user: userWithoutPassword,
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
      setAuthState({
        ...authState,
        isLoading: false,
        error: error instanceof Error ? error.message : 'Registration failed',
      });
      
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : 'Registration failed',
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
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Update user in localStorage
      const users = JSON.parse(localStorage.getItem('users') || '[]');
      const userIndex = users.findIndex((u: any) => u.id === authState.user?.id);
      
      if (userIndex === -1) {
        throw new Error('User not found');
      }
      
      const updatedUser = { ...users[userIndex], ...settings };
      users[userIndex] = updatedUser;
      
      localStorage.setItem('users', JSON.stringify(users));
      
      // Update user in state without password
      const { password: _, ...userWithoutPassword } = updatedUser;
      
      setAuthState({
        ...authState,
        user: userWithoutPassword,
        isLoading: false,
      });
      
      toast({
        title: "Success",
        description: "Your settings have been updated successfully",
        variant: "default",
      });
    } catch (error) {
      setAuthState({
        ...authState,
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to update settings',
      });
      
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : 'Failed to update settings',
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
