import React, { useState } from 'react';
import { API_URL } from '../config/api';
import {
  ArrowLeft,
  CheckCircle,
  Mail
} from 'lucide-react';
import { Input } from './ui/input';
import { Label } from './ui/label';

interface ForgotPasswordProps {
  onNavigateToLogin: () => void;
}

const ForgotPassword: React.FC<ForgotPasswordProps> = ({
  onNavigateToLogin,
}) => {
  const [email, setEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [error, setError] = useState('');

  const validateEmail = (email: string) => {
    return /\S+@\S+\.\S+/.test(email);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!email) {
      setError('Email is required');
      return;
    }

    if (!validateEmail(email)) {
      setError('Please enter a valid email address');
      return;
    }

    setIsLoading(true);

    try {
      const baseUrl = API_URL;
      const response = await fetch(`${baseUrl}/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });

      if (response.ok) {
        setIsSubmitted(true);
      } else {
        setIsSubmitted(true);
      }
    } catch (error) {
      console.error('Forgot password error:', error);
      setIsSubmitted(true);
    } finally {
      setIsLoading(false);
    }
  };

  if (isSubmitted) {
    return (
      <div className="min-h-screen bg-background text-muted-foreground flex items-center justify-center px-4 sm:px-6 lg:px-8 relative overflow-hidden">
        <div className="relative max-w-md w-full">
          <div className="text-center mb-8">
            <div className="w-16 h-16 bg-emerald-500/10 border border-border rounded-xl flex items-center justify-center mx-auto mb-4">
              <CheckCircle className="w-8 h-8 text-emerald-400" />
            </div>
            <h2 className="text-3xl font-bold text-foreground">Check your email</h2>
            <p className="text-muted-foreground mt-2">We've sent a password reset link to</p>
            <p className="text-foreground font-medium mt-1">{email}</p>
          </div>

          <div className="p-8 border border-border rounded-xl bg-transparent">
            <div className="space-y-4 text-center">
              <p className="text-muted-foreground text-sm">
                Click the link in the email to reset your password. The link will expire in 1 hour.
              </p>
              <p className="text-muted-foreground text-xs">
                Didn't receive the email? Check your spam folder or try again.
              </p>
              <div className="pt-4 space-y-3">
                <button
                  onClick={() => { setIsSubmitted(false); setEmail(''); }}
                  className="w-full py-3 rounded-lg font-medium text-foreground border border-border bg-transparent hover:bg-accent transition-all text-sm"
                >
                  Try a different email
                </button>
                <button onClick={onNavigateToLogin} className="w-full bg-primary text-primary-foreground hover:bg-white/90 transition-colors py-3 rounded-lg text-sm font-medium">
                  Back to Sign In
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-muted-foreground flex items-center justify-center px-4 sm:px-6 lg:px-8 relative overflow-hidden">
      <div className="relative max-w-md w-full">
        <button
          onClick={onNavigateToLogin}
          className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors text-sm mb-8 group"
        >
          <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
          Back to Sign In
        </button>

        <div className="text-center mb-8">
          <img src="/logo-full.png?v=4" alt="OffCall AI" className="h-16 w-auto mx-auto mb-6" />
          <h2 className="text-3xl font-bold text-foreground">Forgot password?</h2>
          <p className="text-muted-foreground mt-2">No worries, we'll send you reset instructions.</p>
        </div>

        <div className="p-8 border border-border rounded-xl bg-transparent">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="email" className="text-muted-foreground text-sm">Email</Label>
              <div className="relative">
                <Mail className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
                <Input
                  type="email"
                  id="email"
                  value={email}
                  onChange={(e) => { setEmail(e.target.value); setError(''); }}
                  className={`pl-10 bg-transparent border-border text-foreground placeholder:text-muted-foreground focus:border-white/20 focus:ring-white/10 ${error ? 'border-red-500/50' : ''}`}
                  placeholder="Enter your email"
                />
              </div>
              {error && <p className="text-red-400 text-xs">{error}</p>}
            </div>

            <button type="submit" disabled={isLoading} className="w-full bg-primary text-primary-foreground hover:bg-white/90 transition-colors py-2.5 rounded-lg text-sm font-medium disabled:opacity-50">
              {isLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <div className="w-4 h-4 border-2 border-black/30 border-t-black rounded-full animate-spin" />
                  Sending...
                </span>
              ) : (
                <span>Send Reset Link</span>
              )}
            </button>
          </form>

        </div>
      </div>
    </div>
  );
};

export default ForgotPassword;
