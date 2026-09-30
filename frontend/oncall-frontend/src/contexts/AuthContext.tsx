// frontend/oncall-frontend/src/contexts/AuthContext.tsx
import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

import { API_URL as API_BASE_URL } from '../config/api';

interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  organization_id: string;
  organization_name: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string, organizationName: string) => Promise<void>;
  logout: () => Promise<void>;
  setToken: (token: string | null) => void;
  setUser: (user: User | null) => void;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Token refresh lock to prevent race conditions
let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

const subscribeTokenRefresh = (cb: (token: string) => void) => {
  refreshSubscribers.push(cb);
};

const onTokenRefreshed = (token: string) => {
  refreshSubscribers.forEach(cb => cb(token));
  refreshSubscribers = [];
};

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setTokenState] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const isAuthenticated = !!token && !!user;

  // CRITICAL FIX: Only run on mount, don't refetch when user/token changes
  useEffect(() => {
    const initializeAuth = async () => {
      const browserSession = sessionStorage.getItem('browser_session');
      const storedToken = localStorage.getItem('access_token');
      const refreshToken = localStorage.getItem('refresh_token');

      // Clear tokens if no browser session (new browser window)
      if (storedToken && !browserSession) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user');
        setIsLoading(false);
        return;
      }

      sessionStorage.setItem('browser_session', 'active');

      if (storedToken) {
        // Validate token expiration
        try {
          const payload = JSON.parse(atob(storedToken.split('.')[1]));
          const currentTime = Math.floor(Date.now() / 1000);

          // Check if token is expired or expiring soon (within 5 minutes)
          if (payload.exp < (currentTime + 300)) {
            console.log('Token expired or expiring soon, attempting refresh...');

            // Try to refresh the token
            if (refreshToken) {
              const response = await fetch(`${API_BASE_URL}/auth/refresh-token`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh_token: refreshToken }),
              });

              if (response.ok) {
                const data = await response.json();
                const newToken = data.access_token;

                setTokenState(newToken);
                localStorage.setItem('access_token', newToken);
                if (data.refresh_token) {
                  localStorage.setItem('refresh_token', data.refresh_token);
                }

                // Fetch user profile with new token
                await fetchUserProfile(newToken);
                setIsLoading(false);
                return;
              } else {
                // Refresh failed, clear everything
                console.error('Token refresh failed on app load');
                localStorage.removeItem('access_token');
                localStorage.removeItem('refresh_token');
                localStorage.removeItem('user');
                setIsLoading(false);
                return;
              }
            } else {
              // No refresh token, clear everything
              localStorage.removeItem('access_token');
              localStorage.removeItem('user');
              setIsLoading(false);
              return;
            }
          }

          // Token is valid, proceed normally
          setTokenState(storedToken);

          // Verify token by fetching user profile
          if (!user) {
            const profileResponse = await fetch(`${API_BASE_URL}/users/me`, {
              headers: {
                'Authorization': `Bearer ${storedToken}`,
                'Content-Type': 'application/json',
              },
            });

            if (profileResponse.ok) {
              await fetchUserProfile(storedToken);
            } else {
              // Token invalid, try refresh
              if (refreshToken) {
                const refreshResponse = await fetch(`${API_BASE_URL}/auth/refresh-token`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ refresh_token: refreshToken }),
                });

                if (refreshResponse.ok) {
                  const data = await refreshResponse.json();
                  const newToken = data.access_token;

                  setTokenState(newToken);
                  localStorage.setItem('access_token', newToken);
                  if (data.refresh_token) {
                    localStorage.setItem('refresh_token', data.refresh_token);
                  }

                  await fetchUserProfile(newToken);
                } else {
                  // All attempts failed, clear state
                  localStorage.removeItem('access_token');
                  localStorage.removeItem('refresh_token');
                  localStorage.removeItem('user');
                  setTokenState(null);
                  setUser(null);
                }
              } else {
                // No refresh token, clear everything
                localStorage.removeItem('access_token');
                localStorage.removeItem('user');
                setTokenState(null);
                setUser(null);
              }
            }
          }
        } catch (error) {
          console.error('Token validation error on app load:', error);
          // Invalid token format, clear everything
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          localStorage.removeItem('user');
          setTokenState(null);
          setUser(null);
        }
      }

      setIsLoading(false);
    };

    initializeAuth();
  }, []); // Empty dependency array - only run once on mount

  // Cross-tab token synchronization
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'access_token') {
        if (e.newValue) {
          // Token was updated in another tab
          setTokenState(e.newValue);
          console.log('Token synced from another tab');
        } else {
          // Token was removed in another tab (logout)
          setTokenState(null);
          setUser(null);
        }
      }
      if (e.key === 'refresh_token' && !e.newValue) {
        // Refresh token removed - user logged out
        setTokenState(null);
        setUser(null);
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  // Inactivity timeout
  useEffect(() => {
    if (!isAuthenticated) return;

    let inactivityTimer: NodeJS.Timeout;

    const resetTimer = () => {
      clearTimeout(inactivityTimer);
      inactivityTimer = setTimeout(() => {
        logout();
      }, 15 * 60 * 1000);
    };

    const events = ['mousedown', 'keydown', 'scroll', 'touchstart', 'mousemove'];
    events.forEach(event => {
      window.addEventListener(event, resetTimer, { passive: true });
    });

    resetTimer();

    return () => {
      events.forEach(event => window.removeEventListener(event, resetTimer));
      clearTimeout(inactivityTimer);
    };
  }, [isAuthenticated]);

  // Token expiration check
  useEffect(() => {
    if (!token) return;

    const checkTokenExpiration = () => {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        const currentTime = Math.floor(Date.now() / 1000);
        const bufferTime = 5 * 60;
        
        if (payload.exp < (currentTime + bufferTime)) {
          console.log('Token expired or expiring soon');
          attemptTokenRefresh();
        }
      } catch (error) {
        console.error('Token validation error:', error);
        logout();
      }
    };

    checkTokenExpiration();
    const interval = setInterval(checkTokenExpiration, 60 * 1000);

    return () => clearInterval(interval);
  }, [token]);

  const attemptTokenRefresh = async (): Promise<string | null> => {
    // If already refreshing, wait for the result
    if (isRefreshing) {
      return new Promise((resolve) => {
        subscribeTokenRefresh((newToken: string) => {
          resolve(newToken);
        });
      });
    }

    const refreshTokenStr = localStorage.getItem('refresh_token');
    if (!refreshTokenStr) {
      logout();
      return null;
    }

    isRefreshing = true;

    try {
      const response = await fetch(`${API_BASE_URL}/auth/refresh-token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshTokenStr }),
      });

      if (response.ok) {
        const data = await response.json();
        const newAccessToken = data.access_token;

        setTokenState(newAccessToken);
        localStorage.setItem('access_token', newAccessToken);
        if (data.refresh_token) {
          localStorage.setItem('refresh_token', data.refresh_token);
        }

        // Notify all waiting requests
        onTokenRefreshed(newAccessToken);
        console.log('Token refreshed successfully');

        return newAccessToken;
      } else {
        console.error('Token refresh failed with status:', response.status);
        logout();
        return null;
      }
    } catch (error) {
      console.error('Token refresh failed:', error);
      logout();
      return null;
    } finally {
      isRefreshing = false;
    }
  };

  const fetchUserProfile = async (authToken: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/users/me`, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const userData = await response.json();
        setUser(userData);
      } else {
        localStorage.removeItem('access_token');
        setTokenState(null);
        setUser(null);
      }
    } catch (error) {
      console.error('Failed to fetch user profile:', error);
    }
  };

  const login = async (email: string, password: string): Promise<void> => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });

      let data;
      try {
        data = await response.json();
      } catch {
        throw new Error('Server error. Please try again later.');
      }

      if (!response.ok) {
        throw new Error(data.detail || 'Invalid email or password');
      }

      localStorage.setItem('access_token', data.access_token);
      if (data.refresh_token) {
        localStorage.setItem('refresh_token', data.refresh_token);
      }
      
      sessionStorage.setItem('browser_session', 'active');

      setTokenState(data.access_token);
      setUser(data.user);
      
      
    } catch (error) {
      let errorMessage = 'Login failed';
      if (error instanceof Error) {
        errorMessage = error.message === 'Failed to fetch'
          ? 'Unable to connect to server. Please try again.'
          : error.message;
      }
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (
    email: string, 
    password: string, 
    fullName: string, 
    organizationName: string
  ): Promise<void> => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          password,
          full_name: fullName,
          organization_name: organizationName,
        }),
      });

      let data;
      try {
        data = await response.json();
      } catch {
        throw new Error('Server error. Please try again later.');
      }

      if (!response.ok) {
        throw new Error(data.detail || 'Registration failed');
      }

      localStorage.setItem('access_token', data.access_token);
      if (data.refresh_token) {
        localStorage.setItem('refresh_token', data.refresh_token);
      }
      
      sessionStorage.setItem('browser_session', 'active');

      setTokenState(data.access_token);
      setUser(data.user);
      
      
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Registration failed';
      setError(errorMessage);
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async (): Promise<void> => {
    // Get tokens before clearing for backend invalidation
    const accessToken = localStorage.getItem('access_token');
    const refreshToken = localStorage.getItem('refresh_token');

    // Call backend logout to invalidate tokens (fire and forget)
    if (accessToken) {
      try {
        await fetch(`${API_BASE_URL}/auth/logout`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            access_token: accessToken,
            refresh_token: refreshToken,
          }),
        });
      } catch (error) {
        // Silently fail - local logout still proceeds
        console.error('Backend logout failed:', error);
      }
    }

    // Clear all authentication-related localStorage items
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');

    // Clear all plan selection flags
    const planKeys = Object.keys(localStorage).filter(key => key.startsWith('plan_selected_'));
    planKeys.forEach(key => localStorage.removeItem(key));

    // Clear session storage (including auth redirect)
    sessionStorage.removeItem('browser_session');
    sessionStorage.removeItem('auth_redirect_url');
    sessionStorage.clear();

    // Reset all state
    setTokenState(null);
    setUser(null);
    setError(null);

    // Redirect to landing page
    window.location.href = '/';
  };

  const handleSetToken = (newToken: string | null): void => {
    setTokenState(newToken);
    if (newToken) {
      localStorage.setItem('access_token', newToken);
      sessionStorage.setItem('browser_session', 'active');
    } else {
      localStorage.removeItem('access_token');
      sessionStorage.removeItem('browser_session');
    }
  };

  const handleSetUser = (newUser: User | null): void => {
    setUser(newUser);
  };

  const clearError = (): void => {
    setError(null);
  };

  const value: AuthContextType = {
    user,
    token,
    isAuthenticated,
    isLoading,
    error,
    loading: isLoading,
    login,
    register,
    logout,
    setToken: handleSetToken,
    setUser: handleSetUser,
    clearError,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};