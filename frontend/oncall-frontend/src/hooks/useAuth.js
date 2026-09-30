// frontend/src/hooks/useAuth.js
import { useState, useEffect, useContext, createContext } from 'react';
import authService from '../services/authService';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    initializeAuth();
  }, []);

  const initializeAuth = async () => {
    try {
      setIsLoading(true);
      
      // Try to initialize with existing token
      const initialized = await authService.initialize();
      
      if (initialized) {
        // Get user info
        const userInfo = await authService.getCurrentUserInfo();
        setUser(userInfo);
        setIsAuthenticated(true);
        
        // Start automatic token refresh
        authService.startTokenRefreshTimer();
      } else {
        // No valid authentication
        setUser(null);
        setIsAuthenticated(false);
      }
    } catch (error) {
      console.error('Auth initialization failed:', error);
      setUser(null);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  };

  const login = async (email, password, rememberMe = false) => {
    try {
      const response = await authService.login(email, password, rememberMe);
      
      setUser(response.user);
      setIsAuthenticated(true);
      
      // Set up WebSocket connection
      await authService.createWebSocketConnection();
      
      return response;
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    }
  };

  const register = async (email, password, fullName, organizationName) => {
    try {
      const response = await authService.register(email, password, fullName, organizationName);
      
      setUser(response.user);
      setIsAuthenticated(true);
      
      // Set up WebSocket connection
      await authService.createWebSocketConnection();
      
      return response;
    } catch (error) {
      console.error('Registration failed:', error);
      throw error;
    }
  };

  const logout = () => {
    authService.logout();
    setUser(null);
    setIsAuthenticated(false);
  };

  const value = {
    user,
    isLoading,
    isAuthenticated,
    login,
    register,
    logout,
    refreshAuth: initializeAuth,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

// Enhanced auth service methods
authService.getCurrentUserInfo = async function() {
  try {
    return await this.makeRequest({
      url: '/auth/me',
      method: 'GET',
    });
  } catch (error) {
    console.error('Failed to get user info:', error);
    throw error;
  }
};

export default useAuth;