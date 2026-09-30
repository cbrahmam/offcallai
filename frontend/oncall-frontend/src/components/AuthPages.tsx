import React, { useState, useEffect } from 'react';
import {
  AlertTriangle,
  ArrowLeft,
  Building2,
  Eye,
  EyeOff,
  Lock,
  Mail,
  User
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useNotifications } from '../contexts/NotificationContext';
import { API_URL } from '../config/api';
import { Input } from './ui/input';
import { Label } from './ui/label';

interface AuthPagesProps {
  onLoginSuccess: () => void;
  defaultMode?: 'login' | 'register';
}

const AuthPages: React.FC<AuthPagesProps> = ({
  onLoginSuccess,
  defaultMode = 'login',
}) => {
  const [currentMode, setCurrentMode] = useState<'login' | 'register'>(defaultMode);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const { login, register, error: loginError, clearError } = useAuth();
  const { showToast } = useNotifications();

  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    full_name: '',
    organization_name: '',
  });

  useEffect(() => {
    const path = window.location.pathname;
    if (path.includes('/login')) {
      setCurrentMode('login');
    } else if (path.includes('/register')) {
      setCurrentMode('register');
    } else {
      setCurrentMode(defaultMode);
    }
  }, [defaultMode]);

  const switchMode = (mode: 'login' | 'register') => {
    setCurrentMode(mode);
    setErrors({});
    clearError();
    const url = mode === 'login' ? '/auth/login' : '/auth/register';
    window.history.pushState(null, '', url);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    clearError();
    if (errors[name]) {
      setErrors((prev) => ({ ...prev, [name]: '' }));
    }
  };

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.email) {
      newErrors.email = 'Email is required';
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = 'Please enter a valid email';
    }

    if (!formData.password) {
      newErrors.password = 'Password is required';
    } else if (formData.password.length < 8) {
      newErrors.password = 'Password must be at least 8 characters';
    }

    if (currentMode === 'register') {
      if (!formData.full_name) {
        newErrors.full_name = 'Full name is required';
      }
      if (!formData.organization_name) {
        newErrors.organization_name = 'Organization name is required';
      }
      if (!formData.confirmPassword) {
        newErrors.confirmPassword = 'Please confirm your password';
      } else if (formData.password !== formData.confirmPassword) {
        newErrors.confirmPassword = 'Passwords do not match';
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    setIsLoading(true);
    try {
      if (currentMode === 'login') {
        await login(formData.email, formData.password);
        showToast({
          type: 'success',
          title: 'Welcome back!',
          message: 'Successfully signed in to OffCall AI',
          autoClose: true,
        });
      } else {
        await register(formData.email, formData.password, formData.full_name, formData.organization_name);
        showToast({
          type: 'success',
          title: 'Account Created!',
          message: 'Welcome to OffCall AI. You can now start managing incidents.',
          autoClose: true,
        });
      }
      onLoginSuccess();
    } catch (error: any) {
      console.error('Authentication error:', error);
      // Error is already set in AuthContext by login/register — just show toast
      showToast({
        type: 'error',
        title: currentMode === 'login' ? 'Sign In Failed' : 'Registration Failed',
        message: error.message || 'Please check your credentials and try again.',
        autoClose: true,
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-muted-foreground flex items-center justify-center px-4 sm:px-6 lg:px-8 relative overflow-hidden">

      <div className="relative max-w-md w-full">
        {/* Header */}
        <div className="text-center mb-8">
          <img src="/logo-full.png?v=4" alt="OffCall AI" className="h-16 w-auto mx-auto mb-6" />
          <h2 className="text-3xl font-bold text-foreground mb-2">
            {currentMode === 'login' ? 'Welcome back' : 'Get started'}
          </h2>
          <p className="text-muted-foreground">
            {currentMode === 'login'
              ? 'Sign in to your OffCall AI account'
              : 'Create your OffCall AI account'}
          </p>
        </div>

        {/* Auth Card */}
        <div className="p-8 border border-border rounded-xl bg-transparent">
          {/* Email Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {currentMode === 'register' && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="full_name" className="text-muted-foreground text-sm">
                    Full Name
                  </Label>
                  <div className="relative">
                    <User className="absolute left-3 top-3 w-4 h-4 text-muted-foreground/50" />
                    <Input
                      type="text"
                      id="full_name"
                      name="full_name"
                      value={formData.full_name}
                      onChange={handleInputChange}
                      className={`pl-10 bg-transparent border-border text-foreground placeholder:text-muted-foreground focus:border-white/20 focus:ring-white/10 ${
                        errors.full_name ? 'border-red-500/50' : ''
                      }`}
                      placeholder="Enter your full name"
                    />
                  </div>
                  {errors.full_name && <p className="text-red-400 text-xs">{errors.full_name}</p>}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="organization_name" className="text-muted-foreground text-sm">
                    Organization Name
                  </Label>
                  <div className="relative">
                    <Building2 className="absolute left-3 top-3 w-4 h-4 text-muted-foreground/50" />
                    <Input
                      type="text"
                      id="organization_name"
                      name="organization_name"
                      value={formData.organization_name}
                      onChange={handleInputChange}
                      className={`pl-10 bg-transparent border-border text-foreground placeholder:text-muted-foreground focus:border-white/20 focus:ring-white/10 ${
                        errors.organization_name ? 'border-red-500/50' : ''
                      }`}
                      placeholder="Enter your organization name"
                    />
                  </div>
                  {errors.organization_name && (
                    <p className="text-red-400 text-xs">{errors.organization_name}</p>
                  )}
                </div>
              </>
            )}

            <div className="space-y-2">
              <Label htmlFor="email" className="text-muted-foreground text-sm">
                Email
              </Label>
              <div className="relative">
                <Mail className="absolute left-3 top-3 w-4 h-4 text-muted-foreground/50" />
                <Input
                  type="email"
                  id="email"
                  name="email"
                  value={formData.email}
                  onChange={handleInputChange}
                  className={`pl-10 bg-transparent border-border text-foreground placeholder:text-muted-foreground focus:border-white/20 focus:ring-white/10 ${
                    errors.email ? 'border-red-500/50' : ''
                  }`}
                  placeholder="Enter your email"
                />
              </div>
              {errors.email && <p className="text-red-400 text-xs">{errors.email}</p>}
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="password" className="text-muted-foreground text-sm">
                  Password
                </Label>
                {currentMode === 'login' && (
                  <button
                    type="button"
                    onClick={() => {
                      window.history.pushState(null, '', '/forgot-password');
                      window.location.reload();
                    }}
                    className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                  >
                    Forgot password?
                  </button>
                )}
              </div>
              <div className="relative">
                <Lock className="absolute left-3 top-3 w-4 h-4 text-muted-foreground/50" />
                <Input
                  type={showPassword ? 'text' : 'password'}
                  id="password"
                  name="password"
                  value={formData.password}
                  onChange={handleInputChange}
                  className={`pl-10 pr-12 bg-transparent border-border text-foreground placeholder:text-muted-foreground focus:border-white/20 focus:ring-white/10 ${
                    errors.password ? 'border-red-500/50' : ''
                  }`}
                  placeholder="Enter your password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-3 text-muted-foreground hover:text-muted-foreground transition-colors"
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
              {errors.password && <p className="text-red-400 text-xs">{errors.password}</p>}
            </div>

            {currentMode === 'register' && (
              <div className="space-y-2">
                <Label htmlFor="confirmPassword" className="text-muted-foreground text-sm">
                  Confirm Password
                </Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-3 w-4 h-4 text-muted-foreground/50" />
                  <Input
                    type={showConfirmPassword ? 'text' : 'password'}
                    id="confirmPassword"
                    name="confirmPassword"
                    value={formData.confirmPassword}
                    onChange={handleInputChange}
                    className={`pl-10 pr-12 bg-transparent border-border text-foreground placeholder:text-muted-foreground focus:border-white/20 focus:ring-white/10 ${
                      errors.confirmPassword ? 'border-red-500/50' : ''
                    }`}
                    placeholder="Confirm your password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-3 top-3 text-muted-foreground hover:text-muted-foreground transition-colors"
                  >
                    {showConfirmPassword ? (
                      <EyeOff className="w-4 h-4" />
                    ) : (
                      <Eye className="w-4 h-4" />
                    )}
                  </button>
                </div>
                {errors.confirmPassword && (
                  <p className="text-red-400 text-xs">{errors.confirmPassword}</p>
                )}
              </div>
            )}

            {loginError && (
              <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
                <p className="text-sm text-red-400">{loginError}</p>
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full mt-2 bg-primary text-primary-foreground hover:bg-white/90 transition-colors py-2.5 rounded-lg text-sm font-medium disabled:opacity-50"
            >
              {isLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <div className="w-4 h-4 border-2 border-black/30 border-t-black rounded-full animate-spin" />
                  {currentMode === 'login' ? 'Signing in...' : 'Creating account...'}
                </span>
              ) : (
                <span>{currentMode === 'login' ? 'Sign In' : 'Create Account'}</span>
              )}
            </button>
          </form>

          {/* Switch Mode */}
          <div className="mt-6 text-center">
            <p className="text-muted-foreground text-sm">
              {currentMode === 'login' ? "Don't have an account? " : 'Already have an account? '}
              <button
                onClick={() => switchMode(currentMode === 'login' ? 'register' : 'login')}
                className="text-foreground hover:text-foreground font-medium transition-colors"
              >
                {currentMode === 'login' ? 'Sign up' : 'Sign in'}
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AuthPages;
