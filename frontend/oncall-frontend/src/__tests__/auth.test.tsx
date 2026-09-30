// frontend/src/__tests__/auth.test.tsx
/**
 * Authentication tests for OffCall AI frontend
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import authService from '../services/authService';

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };
})();

Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// Mock fetch
global.fetch = vi.fn();

describe('AuthService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorageMock.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Token Management', () => {
    it('should store token correctly', () => {
      const mockToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwiZXhwIjoxOTk5OTk5OTk5fQ.mock';

      authService.setToken(mockToken);

      expect(localStorageMock.setItem).toHaveBeenCalledWith('access_token', mockToken);
    });

    it('should retrieve stored token', () => {
      const mockToken = 'test-token';
      localStorageMock.getItem.mockReturnValue(mockToken);

      const token = authService.getToken();

      expect(token).toBe(mockToken);
    });

    it('should remove token on logout', () => {
      authService.logout();

      expect(localStorageMock.removeItem).toHaveBeenCalledWith('access_token');
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('refresh_token');
    });

    it('should detect expired token', () => {
      // Create a token that expired 1 hour ago
      const expiredPayload = {
        sub: '123',
        exp: Math.floor(Date.now() / 1000) - 3600,
      };
      const expiredToken = `header.${btoa(JSON.stringify(expiredPayload))}.signature`;

      const isExpired = authService.isTokenExpired(expiredToken);

      expect(isExpired).toBe(true);
    });

    it('should detect valid token', () => {
      // Create a token that expires in 1 hour
      const validPayload = {
        sub: '123',
        exp: Math.floor(Date.now() / 1000) + 3600,
      };
      const validToken = `header.${btoa(JSON.stringify(validPayload))}.signature`;

      const isExpired = authService.isTokenExpired(validToken);

      expect(isExpired).toBe(false);
    });
  });

  describe('Login', () => {
    it('should handle successful login', async () => {
      const mockResponse = {
        access_token: 'mock-access-token',
        refresh_token: 'mock-refresh-token',
        user: { id: '123', email: 'test@example.com' },
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await authService.login('test@example.com', 'password123');

      expect(result).toEqual(mockResponse);
      expect(localStorageMock.setItem).toHaveBeenCalledWith('access_token', 'mock-access-token');
    });

    it('should handle login failure', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ detail: 'Invalid credentials' }),
      });

      await expect(authService.login('test@example.com', 'wrong')).rejects.toThrow();
    });
  });

  describe('Registration', () => {
    it('should handle successful registration', async () => {
      const mockResponse = {
        access_token: 'mock-access-token',
        refresh_token: 'mock-refresh-token',
        user: { id: '123', email: 'new@example.com' },
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await authService.register(
        'new@example.com',
        'SecureP@ss123',
        'New User',
        'New Org'
      );

      expect(result).toEqual(mockResponse);
    });
  });

  describe('Token Refresh', () => {
    it('should refresh token when expired', async () => {
      const oldToken = 'old-token';
      const newToken = 'new-token';

      localStorageMock.getItem.mockImplementation((key) => {
        if (key === 'refresh_token') return 'refresh-token';
        return null;
      });

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ access_token: newToken }),
      });

      const result = await authService.performTokenRefresh();

      expect(result).toBe(newToken);
    });

    it('should logout when refresh fails', async () => {
      localStorageMock.getItem.mockReturnValue('refresh-token');

      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
      });

      const result = await authService.performTokenRefresh();

      expect(result).toBeNull();
      expect(localStorageMock.removeItem).toHaveBeenCalled();
    });
  });

  describe('Authentication Check', () => {
    it('should return true for valid token', () => {
      const validPayload = {
        sub: '123',
        exp: Math.floor(Date.now() / 1000) + 3600,
      };
      const validToken = `header.${btoa(JSON.stringify(validPayload))}.signature`;

      localStorageMock.getItem.mockReturnValue(validToken);

      expect(authService.isAuthenticated()).toBe(true);
    });

    it('should return false for no token', () => {
      localStorageMock.getItem.mockReturnValue(null);

      expect(authService.isAuthenticated()).toBe(false);
    });

    it('should return false for expired token', () => {
      const expiredPayload = {
        sub: '123',
        exp: Math.floor(Date.now() / 1000) - 3600,
      };
      const expiredToken = `header.${btoa(JSON.stringify(expiredPayload))}.signature`;

      localStorageMock.getItem.mockReturnValue(expiredToken);

      expect(authService.isAuthenticated()).toBe(false);
    });
  });

  describe('Current User', () => {
    it('should extract user info from token', () => {
      const payload = {
        sub: 'user-123',
        org_id: 'org-456',
        exp: Math.floor(Date.now() / 1000) + 3600,
      };
      const token = `header.${btoa(JSON.stringify(payload))}.signature`;

      localStorageMock.getItem.mockReturnValue(token);

      const user = authService.getCurrentUser();

      expect(user).toEqual({
        id: 'user-123',
        organization_id: 'org-456',
      });
    });

    it('should return null for no token', () => {
      localStorageMock.getItem.mockReturnValue(null);

      expect(authService.getCurrentUser()).toBeNull();
    });
  });
});
