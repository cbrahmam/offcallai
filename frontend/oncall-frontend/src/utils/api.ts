// frontend/oncall-frontend/src/utils/api.ts
// Authenticated API fetch wrapper with automatic token refresh on 401

import { API_URL as API_BASE_URL } from '../config/api';

interface FetchOptions extends RequestInit {
  skipAuth?: boolean;
}

let isRefreshing = false;
let refreshSubscribers: Array<(token: string) => void> = [];

const onTokenRefreshed = (newToken: string) => {
  refreshSubscribers.forEach(callback => callback(newToken));
  refreshSubscribers = [];
};

const addRefreshSubscriber = (callback: (token: string) => void) => {
  refreshSubscribers.push(callback);
};

/**
 * Attempt to refresh the access token using the refresh token
 * @returns The new access token or null if refresh failed
 */
const refreshAccessToken = async (): Promise<string | null> => {
  const refreshToken = localStorage.getItem('refresh_token');

  if (!refreshToken) {
    console.error('No refresh token available');
    return null;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/auth/refresh-token`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (response.ok) {
      const data = await response.json();
      const newAccessToken = data.access_token;

      // Store new tokens
      localStorage.setItem('access_token', newAccessToken);
      if (data.refresh_token) {
        localStorage.setItem('refresh_token', data.refresh_token);
      }

      console.log('Token refreshed successfully');
      return newAccessToken;
    } else {
      console.error('Token refresh failed with status:', response.status);
      return null;
    }
  } catch (error) {
    console.error('Token refresh error:', error);
    return null;
  }
};

/**
 * Clears all auth data and redirects to landing page
 */
const handleAuthFailure = () => {
  // Clear all auth data
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('user');
  sessionStorage.clear();

  // Redirect to landing
  window.location.href = '/';
};

/**
 * Authenticated fetch wrapper that handles token refresh on 401
 * @param url - The URL to fetch
 * @param options - Fetch options with optional skipAuth flag
 * @returns Promise<Response>
 */
export const authenticatedFetch = async (
  url: string,
  options: FetchOptions = {}
): Promise<Response> => {
  const { skipAuth = false, ...fetchOptions } = options;

  // Get current token
  let token = localStorage.getItem('access_token');

  // Add authorization header if not skipping auth
  if (!skipAuth && token) {
    fetchOptions.headers = {
      ...fetchOptions.headers,
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    };
  } else if (!skipAuth) {
    fetchOptions.headers = {
      ...fetchOptions.headers,
      'Content-Type': 'application/json',
    };
  }

  // Make the initial request
  let response = await fetch(url, fetchOptions);

  // Handle 401 Unauthorized
  if (response.status === 401 && !skipAuth) {
    console.log('Received 401, attempting token refresh...');

    // If already refreshing, wait for the refresh to complete
    if (isRefreshing) {
      return new Promise((resolve) => {
        addRefreshSubscriber((newToken: string) => {
          // Retry the request with the new token
          fetchOptions.headers = {
            ...fetchOptions.headers,
            'Authorization': `Bearer ${newToken}`,
          };
          resolve(fetch(url, fetchOptions));
        });
      });
    }

    // Start token refresh
    isRefreshing = true;
    const newToken = await refreshAccessToken();
    isRefreshing = false;

    if (newToken) {
      // Notify all subscribers
      onTokenRefreshed(newToken);

      // Retry the original request with new token
      fetchOptions.headers = {
        ...fetchOptions.headers,
        'Authorization': `Bearer ${newToken}`,
      };

      response = await fetch(url, fetchOptions);
    } else {
      // Refresh failed, logout user
      handleAuthFailure();
      throw new Error('Authentication failed. Please login again.');
    }
  }

  return response;
};

/**
 * Convenience method for GET requests
 */
export const get = async (url: string, options?: FetchOptions): Promise<Response> => {
  return authenticatedFetch(url, { ...options, method: 'GET' });
};

/**
 * Convenience method for POST requests
 */
export const post = async (
  url: string,
  data?: any,
  options?: FetchOptions
): Promise<Response> => {
  return authenticatedFetch(url, {
    ...options,
    method: 'POST',
    body: data ? JSON.stringify(data) : undefined,
  });
};

/**
 * Convenience method for PUT requests
 */
export const put = async (
  url: string,
  data?: any,
  options?: FetchOptions
): Promise<Response> => {
  return authenticatedFetch(url, {
    ...options,
    method: 'PUT',
    body: data ? JSON.stringify(data) : undefined,
  });
};

/**
 * Convenience method for DELETE requests
 */
export const del = async (url: string, options?: FetchOptions): Promise<Response> => {
  return authenticatedFetch(url, { ...options, method: 'DELETE' });
};

/**
 * Convenience method for PATCH requests
 */
export const patch = async (
  url: string,
  data?: any,
  options?: FetchOptions
): Promise<Response> => {
  return authenticatedFetch(url, {
    ...options,
    method: 'PATCH',
    body: data ? JSON.stringify(data) : undefined,
  });
};

export default {
  authenticatedFetch,
  get,
  post,
  put,
  delete: del,
  patch,
};
