// frontend/src/services/authService.js
import { API_URL } from '../config/api';

class AuthService {
  constructor() {
    this.baseURL = API_URL;
    this.tokenRefreshPromise = null;
    this.setupInterceptors();
  }

  // Setup automatic token refresh interceptors
  setupInterceptors() {
    // Request interceptor - add token to all requests
    this.requestInterceptor = async (config) => {
      const token = this.getToken();
      if (token && !this.isTokenExpired(token)) {
        config.headers.Authorization = `Bearer ${token}`;
      } else if (token && this.isTokenExpired(token)) {
        // Token is expired, try to refresh
        const newToken = await this.refreshTokenIfNeeded();
        if (newToken) {
          config.headers.Authorization = `Bearer ${newToken}`;
        }
      }
      return config;
    };

    // Response interceptor - handle 401 errors
    this.responseInterceptor = async (error) => {
      if (error.response?.status === 401 && !error.config._retry) {
        error.config._retry = true;
        
        const newToken = await this.refreshTokenIfNeeded();
        if (newToken) {
          error.config.headers.Authorization = `Bearer ${newToken}`;
          return this.makeRequest(error.config);
        } else {
          // Refresh failed, redirect to login
          this.logout();
          window.location.href = '/login';
        }
      }
      throw error;
    };
  }

  // Make HTTP request with auth handling
  async makeRequest(config) {
    try {
      config = await this.requestInterceptor(config);
      const response = await fetch(`${this.baseURL}${config.url}`, {
        method: config.method || 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...config.headers,
        },
        body: config.body ? JSON.stringify(config.body) : undefined,
      });

      if (!response.ok) {
        const error = new Error(`HTTP ${response.status}`);
        error.response = { status: response.status };
        error.config = config;
        throw error;
      }

      return await response.json();
    } catch (error) {
      return await this.responseInterceptor(error);
    }
  }

  // Check if token is expired or will expire soon (within 5 minutes)
  isTokenExpired(token) {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      const currentTime = Math.floor(Date.now() / 1000);
      const bufferTime = 5 * 60; // 5 minutes buffer
      return payload.exp < (currentTime + bufferTime);
    } catch {
      return true;
    }
  }

  // Get stored token
  getToken() {
    return localStorage.getItem('access_token');
  }

  // Store token with expiration info
  setToken(token) {
    localStorage.setItem('access_token', token);
    
    // Store expiration time for easy checking
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      localStorage.setItem('token_expires_at', payload.exp.toString());
    } catch (error) {
      console.error('Failed to parse token expiration:', error);
    }
  }

  // Remove token
  removeToken() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('token_expires_at');
    localStorage.removeItem('refresh_token');
  }

  // Auto-refresh token if needed (with deduplication)
  async refreshTokenIfNeeded() {
    const token = this.getToken();
    
    if (!token || !this.isTokenExpired(token)) {
      return token;
    }

    // Prevent multiple simultaneous refresh attempts
    if (this.tokenRefreshPromise) {
      return await this.tokenRefreshPromise;
    }

    this.tokenRefreshPromise = this.performTokenRefresh();
    
    try {
      const newToken = await this.tokenRefreshPromise;
      return newToken;
    } finally {
      this.tokenRefreshPromise = null;
    }
  }

  // Perform the actual token refresh using refresh token only
  async performTokenRefresh() {
    try {
      const refreshToken = localStorage.getItem('refresh_token');

      if (refreshToken) {
        const response = await fetch(`${this.baseURL}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });

        if (response.ok) {
          const data = await response.json();
          this.setToken(data.access_token);
          if (data.refresh_token) {
            localStorage.setItem('refresh_token', data.refresh_token);
          }
          return data.access_token;
        }
      }

      // Refresh token invalid or missing - user must re-authenticate
      this.logout();
      return null;

    } catch (error) {
      console.error('Token refresh failed:', error);
      this.logout();
      return null;
    }
  }

  // Login with secure token storage
  async login(email, password) {
    try {
      const response = await fetch(`${this.baseURL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Login failed');
      }

      const data = await response.json();

      // Store tokens securely
      this.setToken(data.access_token);
      if (data.refresh_token) {
        localStorage.setItem('refresh_token', data.refresh_token);
      }

      return data;
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    }
  }

  // Enhanced register
  async register(email, password, fullName, organizationName) {
    try {
      const response = await fetch(`${this.baseURL}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          password,
          full_name: fullName,
          organization_name: organizationName,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Registration failed');
      }

      const data = await response.json();
      
      // Store tokens
      this.setToken(data.access_token);
      if (data.refresh_token) {
        localStorage.setItem('refresh_token', data.refresh_token);
      }

      return data;
    } catch (error) {
      console.error('Registration failed:', error);
      throw error;
    }
  }

  // Logout and cleanup
  logout() {
    this.removeToken();
    // Close any WebSocket connections
    if (window.wsConnection) {
      window.wsConnection.close();
      window.wsConnection = null;
    }
  }

  // Check if user is authenticated
  isAuthenticated() {
    const token = this.getToken();
    return token && !this.isTokenExpired(token);
  }

  // Get current user info from token
  getCurrentUser() {
    const token = this.getToken();
    if (!token) return null;

    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      return {
        id: payload.sub,
        organization_id: payload.org_id,
        // Add other user info as needed
      };
    } catch {
      return null;
    }
  }

  // Request a one-time WebSocket ticket from the server
  async getWebSocketTicket() {
    try {
      const token = await this.refreshTokenIfNeeded();
      if (!token) return null;

      const response = await fetch(`${this.baseURL}/auth/ws-ticket`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        return data.ticket; // One-time use ticket, expires in 30 seconds
      }
      return null;
    } catch (error) {
      console.error('Failed to get WebSocket ticket:', error);
      return null;
    }
  }

  // SECURITY FIX: Use one-time ticket instead of JWT in WebSocket URL
  // This prevents token exposure in logs, browser history, and referrer headers
  createWebSocketConnection() {
    return new Promise(async (resolve, reject) => {
      try {
        // Get a one-time ticket instead of using the JWT directly
        // The ticket is short-lived (30s) and single-use
        let ticket = await this.getWebSocketTicket();

        // Fallback to token if ticket endpoint not available (backward compatibility)
        // TODO: Remove this fallback once backend ws-ticket endpoint is deployed
        if (!ticket) {
          const token = await this.refreshTokenIfNeeded();
          if (!token) {
            reject(new Error('No valid token available'));
            return;
          }
          ticket = token;
          console.warn('⚠️ Using JWT in WebSocket URL - upgrade backend for ws-ticket support');
        }

        // Derive WebSocket URL from API base URL
        const wsProtocol = this.baseURL.startsWith('https') ? 'wss' : 'ws';
        const wsHost = this.baseURL.replace(/^https?:\/\//, '').replace('/api/v1', '');
        const wsUrl = `${wsProtocol}://${wsHost}/api/v1/ws/notifications?ticket=${ticket}`;
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          window.wsConnection = ws;
          resolve(ws);
        };

        ws.onerror = (error) => {
          console.error('WebSocket connection failed:', error);
          reject(error);
        };

        ws.onclose = (event) => {
          console.log('🔌 WebSocket closed:', event.code, event.reason);
          
          // If closed due to auth error, try to reconnect with new token
          if (event.code === 1008 || event.code === 1011) {
            setTimeout(async () => {
              console.log('🔄 Attempting WebSocket reconnection...');
              try {
                await this.createWebSocketConnection();
              } catch (error) {
                console.error('WebSocket reconnection failed:', error);
              }
            }, 5000);
          }
        };

        // Set a timeout for connection
        setTimeout(() => {
          if (ws.readyState !== WebSocket.OPEN) {
            ws.close();
            reject(new Error('WebSocket connection timeout'));
          }
        }, 10000);

      } catch (error) {
        reject(error);
      }
    });
  }

  // Initialize auth service (call on app start)
  async initialize() {
    try {
      // Check if we have valid credentials
      const token = this.getToken();
      
      if (token && !this.isTokenExpired(token)) {
        // Token is valid, set up WebSocket
        await this.createWebSocketConnection();
        return true;
      } else if (token) {
        // Token exists but expired, try to refresh
        const newToken = await this.refreshTokenIfNeeded();
        if (newToken) {
          await this.createWebSocketConnection();
          return true;
        }
      }

      // No valid authentication
      return false;
    } catch (error) {
      console.error('Auth initialization failed:', error);
      return false;
    }
  }

  // Start token refresh timer (optional - runs every 5 minutes)
  startTokenRefreshTimer() {
    setInterval(async () => {
      const token = this.getToken();
      if (token && this.isTokenExpired(token)) {
        console.log('🔄 Auto-refreshing token...');
        await this.refreshTokenIfNeeded();
      }
    }, 5 * 60 * 1000); // 5 minutes
  }
}

// Create singleton instance
const authService = new AuthService();

export default authService;