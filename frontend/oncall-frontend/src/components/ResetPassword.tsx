import React, { useState, useEffect } from 'react';
import { API_URL } from '../config/api';
import {
  AlertTriangle,
  CheckCircle,
  Eye,
  EyeOff,
  Lock
} from 'lucide-react';
import { Input } from './ui/input';
import { Label } from './ui/label';

interface ResetPasswordProps {
  onNavigateToLogin: () => void;
}

const ResetPassword: React.FC<ResetPasswordProps> = ({
  onNavigateToLogin,
}) => {
  const [token, setToken] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [error, setError] = useState('');
  const [tokenError, setTokenError] = useState(false);

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const tokenParam = urlParams.get('token');
    if (tokenParam) {
      setToken(tokenParam);
    } else {
      setTokenError(true);
    }
  }, []);

  const validatePassword = (password: string): string | null => {
    if (password.length < 8) return 'Password must be at least 8 characters';
    if (!/[A-Z]/.test(password)) return 'Password must contain at least one uppercase letter';
    if (!/[a-z]/.test(password)) return 'Password must contain at least one lowercase letter';
    if (!/[0-9]/.test(password)) return 'Password must contain at least one number';
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    const passwordError = validatePassword(password);
    if (passwordError) {
      setError(passwordError);
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setIsLoading(true);

    try {
      const baseUrl = API_URL;
      const response = await fetch(`${baseUrl}/auth/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: password }),
      });

      const data = await response.json();

      if (response.ok) {
        setIsSuccess(true);
      } else {
        setError(data.detail || 'Failed to reset password. The link may have expired.');
        if (data.detail?.includes('expired') || data.detail?.includes('invalid')) {
          setTokenError(true);
        }
      }
    } catch (error) {
      console.error('Reset password error:', error);
      setError('An error occurred. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // Token error state
  if (tokenError && !token) {
    return (
      <div className="min-h-screen bg-background text-muted-foreground flex items-center justify-center px-4 sm:px-6 lg:px-8 relative overflow-hidden">
        
        <div className="relative max-w-md w-full">
          <div className="text-center mb-8">
            <div className="w-16 h-16 bg-red-500/10 border border-border rounded-xl flex items-center justify-center mx-auto mb-4">
              <AlertTriangle className="w-8 h-8 text-red-400" />
            </div>
            <h2 className="text-3xl font-bold text-foreground">Invalid Link</h2>
            <p className="text-muted-foreground mt-2">This password reset link is invalid or has expired.</p>
          </div>

          <div className="p-8 border border-border rounded-xl bg-transparent">
            <div className="space-y-4 text-center">
              <p className="text-muted-foreground text-sm">Please request a new password reset link.</p>
              <button
                onClick={() => { window.history.pushState(null, '', '/forgot-password'); window.location.reload(); }}
                className="w-full bg-primary text-primary-foreground hover:bg-white/90 transition-colors py-2.5 rounded-lg text-sm font-medium"
              >
                Request New Link
              </button>
              <button
                onClick={onNavigateToLogin}
                className="w-full py-3 rounded-lg font-medium text-foreground border border-border bg-transparent hover:bg-accent transition-all text-sm"
              >
                Back to Sign In
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Success state
  if (isSuccess) {
    return (
      <div className="min-h-screen bg-background text-muted-foreground flex items-center justify-center px-4 sm:px-6 lg:px-8 relative overflow-hidden">
        
        <div className="relative max-w-md w-full">
          <div className="text-center mb-8">
            <div className="w-16 h-16 bg-emerald-500/10 border border-border rounded-xl flex items-center justify-center mx-auto mb-4">
              <CheckCircle className="w-8 h-8 text-emerald-400" />
            </div>
            <h2 className="text-3xl font-bold text-foreground">Password Reset!</h2>
            <p className="text-muted-foreground mt-2">Your password has been successfully reset.</p>
          </div>

          <div className="p-8 border border-border rounded-xl bg-transparent">
            <div className="space-y-4 text-center">
              <p className="text-muted-foreground text-sm">You can now sign in with your new password.</p>
              <button onClick={onNavigateToLogin} className="w-full bg-primary text-primary-foreground hover:bg-white/90 transition-colors py-2.5 rounded-lg text-sm font-medium">
                Sign In
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-muted-foreground flex items-center justify-center px-4 sm:px-6 lg:px-8 relative overflow-hidden">
      
      <div className="relative max-w-md w-full">
        <div className="text-center mb-8">
          <img src="/logo-full.png?v=4" alt="OffCall AI" className="h-16 w-auto mx-auto mb-6" />
          <h2 className="text-3xl font-bold text-foreground">Reset password</h2>
          <p className="text-muted-foreground mt-2">Enter your new password below.</p>
        </div>

        <div className="p-8 border border-border rounded-xl bg-transparent">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Password Requirements */}
            <div className="p-4 rounded-lg border border-border bg-transparent">
              <p className="text-sm text-muted-foreground mb-2 font-medium">Password must contain:</p>
              <ul className="text-sm space-y-1">
                {[
                  { check: password.length >= 8, label: 'At least 8 characters' },
                  { check: /[A-Z]/.test(password), label: 'One uppercase letter' },
                  { check: /[a-z]/.test(password), label: 'One lowercase letter' },
                  { check: /[0-9]/.test(password), label: 'One number' },
                ].map((req, i) => (
                  <li key={i} className={req.check ? 'text-emerald-400' : 'text-muted-foreground'}>
                    {req.check ? '\u2713' : '\u25CB'} {req.label}
                  </li>
                ))}
              </ul>
            </div>

            {/* New Password */}
            <div className="space-y-2">
              <Label htmlFor="password" className="text-muted-foreground text-sm">New Password</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
                <Input
                  type={showPassword ? 'text' : 'password'}
                  id="password"
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); setError(''); }}
                  className="pl-10 pr-12 bg-transparent border-border text-foreground placeholder:text-muted-foreground focus:border-white/20 focus:ring-white/10"
                  placeholder="Enter new password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-3 text-muted-foreground hover:text-muted-foreground transition-colors"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Confirm Password */}
            <div className="space-y-2">
              <Label htmlFor="confirmPassword" className="text-muted-foreground text-sm">Confirm Password</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
                <Input
                  type={showConfirmPassword ? 'text' : 'password'}
                  id="confirmPassword"
                  value={confirmPassword}
                  onChange={(e) => { setConfirmPassword(e.target.value); setError(''); }}
                  className="pl-10 pr-12 bg-transparent border-border text-foreground placeholder:text-muted-foreground focus:border-white/20 focus:ring-white/10"
                  placeholder="Confirm new password"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute right-3 top-3 text-muted-foreground hover:text-muted-foreground transition-colors"
                >
                  {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="p-3 rounded-lg border border-red-500/20 bg-red-500/[0.05]">
                <p className="text-red-400 text-sm">{error}</p>
              </div>
            )}

            <button type="submit" disabled={isLoading} className="w-full bg-primary text-primary-foreground hover:bg-white/90 transition-colors py-2.5 rounded-lg text-sm font-medium disabled:opacity-50">
              {isLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <div className="w-4 h-4 border-2 border-black/30 border-t-black rounded-full animate-spin" />
                  Resetting...
                </span>
              ) : (
                <span>Reset Password</span>
              )}
            </button>
          </form>

          <div className="mt-6 text-center space-y-3">
            <button
              onClick={onNavigateToLogin}
              className="text-muted-foreground hover:text-foreground transition-colors text-sm"
            >
              Back to Sign In
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ResetPassword;
