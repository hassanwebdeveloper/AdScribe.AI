import React from 'react';
import RegisterForm from '@/components/auth/RegisterForm';
import { Navigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';

const Register: React.FC = () => {
  const { isAuthenticated } = useAuth();
  
  if (isAuthenticated) {
    return <Navigate to="/ai-scripter" replace />;
  }
  
  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4 bg-gradient-to-b from-white to-brand-50">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold mb-2">AdScribe AI</h1>
          <p className="text-muted-foreground">
            Create an account to get started
          </p>
        </div>
        <RegisterForm />
      </div>
    </div>
  );
};

export default Register;
