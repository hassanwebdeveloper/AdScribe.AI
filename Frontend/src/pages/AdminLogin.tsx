import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertCircle, Lock, Mail, Shield, Timer } from 'lucide-react';

interface OTPResponse {
  success: boolean;
  message: string;
}

interface AuthResponse {
  success: boolean;
  message: string;
  token?: string;
  expires_in?: number;
}

const AdminLogin: React.FC = () => {
  const [step, setStep] = useState<'email' | 'otp'>('email');
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [otpSent, setOtpSent] = useState(false);
  const [countdown, setCountdown] = useState(0);
  
  const navigate = useNavigate();

  // Use relative URL for API calls
  const API_BASE = '/api/v1/admin/auth';

  // Countdown timer for OTP expiration
  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [countdown]);

  // Check if user is already authenticated
  useEffect(() => {
    const token = localStorage.getItem('admin_token');
    if (token) {
      // Verify token is still valid
      verifyExistingSession(token);
    }
  }, []);

  const verifyExistingSession = async (token: string) => {
    try {
      const response = await fetch(`${API_BASE}/verify-session`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (response.ok) {
        // Token is valid, redirect to admin panel
        navigate('/admin/prompts');
      } else {
        // Token is invalid, remove it
        localStorage.removeItem('admin_token');
      }
    } catch (err) {
      // Error verifying token, remove it
      localStorage.removeItem('admin_token');
    }
  };

  const handleSendOTP = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const response = await fetch(`${API_BASE}/send-otp`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email }),
      });

      const data: OTPResponse = await response.json();

      if (data.success) {
        setSuccess(data.message);
        setOtpSent(true);
        setStep('otp');
        setCountdown(60); // 1 minute countdown
      } else {
        setError(data.message);
      }
    } catch (err) {
      setError('Failed to send OTP. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOTP = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/verify-otp`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, otp_code: otp }),
      });

      const data: AuthResponse = await response.json();

      if (data.success && data.token) {
        // Save token to localStorage
        localStorage.setItem('admin_token', data.token);
        
        // Redirect to admin panel
        navigate('/admin/prompts');
      } else {
        setError(data.message);
      }
    } catch (err) {
      setError('Failed to verify OTP. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleBackToEmail = () => {
    setStep('email');
    setOtp('');
    setError(null);
    setSuccess(null);
    setOtpSent(false);
    setCountdown(0);
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center mb-4">
            <Shield className="h-12 w-12 text-blue-600" />
          </div>
          <h1 className="text-3xl font-bold text-gray-900">Admin Access</h1>
          <p className="text-gray-600 mt-2">
            Secure access to AdScribe.AI admin panel
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-center flex items-center justify-center gap-2">
              {step === 'email' ? (
                <>
                  <Mail className="h-5 w-5" />
                  Enter Admin Email
                </>
              ) : (
                <>
                  <Lock className="h-5 w-5" />
                  Verify OTP
                </>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {/* Error Alert */}
            {error && (
              <Alert className="mb-4 border-red-200 bg-red-50">
                <AlertCircle className="h-4 w-4 text-red-600" />
                <AlertDescription className="text-red-700">{error}</AlertDescription>
              </Alert>
            )}

            {/* Success Alert */}
            {success && (
              <Alert className="mb-4 border-green-200 bg-green-50">
                <AlertCircle className="h-4 w-4 text-green-600" />
                <AlertDescription className="text-green-700">{success}</AlertDescription>
              </Alert>
            )}

            {step === 'email' ? (
              /* Email Step */
              <form onSubmit={handleSendOTP} className="space-y-4">
                <div>
                  <Label htmlFor="email">Admin Email Address</Label>
                  <Input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Enter your authorized admin email"
                    required
                    disabled={loading}
                  />
                  <p className="text-sm text-gray-500 mt-1">
                    Only authorized admin emails can access this panel
                  </p>
                </div>

                <Button 
                  type="submit" 
                  className="w-full" 
                  disabled={loading || !email}
                >
                  {loading ? 'Sending OTP...' : 'Send OTP'}
                </Button>
              </form>
            ) : (
              /* OTP Step */
              <div className="space-y-4">
                {/* OTP Timer */}
                {countdown > 0 && (
                  <div className="text-center">
                    <div className="flex items-center justify-center gap-2 text-sm text-gray-600">
                      <Timer className="h-4 w-4" />
                      OTP expires in: <span className="font-mono font-semibold">{formatTime(countdown)}</span>
                    </div>
                  </div>
                )}

                <form onSubmit={handleVerifyOTP} className="space-y-4">
                  <div>
                    <Label htmlFor="otp">Enter 6-digit OTP</Label>
                    <Input
                      id="otp"
                      type="text"
                      value={otp}
                      onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                      placeholder="000000"
                      required
                      disabled={loading}
                      className="text-center text-lg tracking-widest font-mono"
                      maxLength={6}
                    />
                    <p className="text-sm text-gray-500 mt-1">
                      OTP sent to: {email}
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Button 
                      type="submit" 
                      className="w-full" 
                      disabled={loading || otp.length !== 6}
                    >
                      {loading ? 'Verifying...' : 'Verify OTP'}
                    </Button>

                    <Button 
                      type="button" 
                      variant="outline" 
                      className="w-full" 
                      onClick={handleBackToEmail}
                      disabled={loading}
                    >
                      Use Different Email
                    </Button>
                  </div>
                </form>

                {/* Resend OTP (after countdown) */}
                {countdown === 0 && (
                  <div className="text-center">
                    <Button 
                      variant="link" 
                      onClick={() => {
                        setStep('email');
                        setOtp('');
                        setError(null);
                      }}
                      className="text-sm"
                    >
                      Resend OTP
                    </Button>
                  </div>
                )}
              </div>
            )}

            {/* Info */}
            <div className="mt-6 text-center">
              <p className="text-xs text-gray-500">
                This is a secure admin area. Access is logged and monitored.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default AdminLogin; 