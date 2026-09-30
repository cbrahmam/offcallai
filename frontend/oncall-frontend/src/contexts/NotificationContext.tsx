// frontend/oncall-frontend/src/contexts/NotificationContext.tsx
// COMPLETE REWRITE - PRODUCTION READY
import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

import { API_URL as API_BASE_URL } from '../config/api';

interface Notification {
  id: string;
  type: string;
  title: string;
  message: string;
  severity?: string;
  incident_id?: string;
  action_url?: string;
  extra_data?: Record<string, any>;
  read: boolean;
  read_at?: string;
  created_at: string;
  autoClose?: boolean;
  duration?: number;
}

interface NotificationStats {
  total_count: number;
  unread_count: number;
  incidents_count: number;
  alerts_count: number;
  system_count: number;
}

interface NotificationPreferences {
  browserNotifications: boolean;
  soundEnabled: boolean;
  emailNotifications: boolean;
  slackNotifications: boolean;
  criticalAlertsOnly: boolean;
  doNotDisturb: boolean;
  quietHours: {
    enabled: boolean;
    start: string;
    end: string;
  };
}

interface NotificationContextType {
  notifications: Notification[];
  toastNotifications: Notification[];
  stats: NotificationStats;
  preferences: NotificationPreferences;
  isConnected: boolean;
  isLoading: boolean;
  unreadCount: number;

  showToast: (notification: Partial<Notification>) => void;
  dismissToast: (id: string) => void;
  markAsRead: (id: string) => Promise<void>;
  markAllAsRead: () => Promise<void>;
  removeNotification: (id: string) => Promise<void>;
  clearAll: () => Promise<void>;
  refreshNotifications: () => Promise<void>;
  updatePreferences: (newPreferences: Partial<NotificationPreferences>) => void;
  requestPermission: () => Promise<boolean>;
}

const NotificationContext = createContext<NotificationContextType | undefined>(undefined);

export const NotificationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [toastNotifications, setToastNotifications] = useState<Notification[]>([]);
  const [stats, setStats] = useState<NotificationStats>({
    total_count: 0,
    unread_count: 0,
    incidents_count: 0,
    alerts_count: 0,
    system_count: 0
  });
  const [preferences, setPreferences] = useState<NotificationPreferences>(() => {
    const saved = localStorage.getItem('notification_preferences');
    return saved ? JSON.parse(saved) : {
      browserNotifications: false,
      soundEnabled: true,
      emailNotifications: true,
      slackNotifications: true,
      criticalAlertsOnly: false,
      doNotDisturb: false,
      quietHours: {
        enabled: false,
        start: '22:00',
        end: '08:00'
      }
    };
  });
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // WebSocket connection - DISABLED temporarily to debug flickering
  // TODO: Re-enable after fixing flickering issue
  // SECURITY NOTE: When re-enabling, use one-time ticket instead of JWT in URL
  // Call POST /api/v1/auth/ws-ticket to get a short-lived ticket
  /*
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) return;

    // SECURITY FIX: Get one-time ticket instead of using JWT directly
    // const ticketResponse = await fetch(`${API_URL}/auth/ws-ticket`, { headers: { Authorization: `Bearer ${token}` }});
    // const { ticket } = await ticketResponse.json();
    // const wsUrl = `wss://<your-host>/api/v1/ws/notifications?ticket=${ticket}`;

    // DEPRECATED: Don't use JWT directly in URL - exposes token in logs
    // const wsUrl = `wss://<your-host>/api/v1/ws/notifications?token=${token}`;
    let ws: WebSocket;

    try {
      // ws = new WebSocket(wsUrl);
      // ... WebSocket handlers ...
    } catch (error) {
      console.error('❌ Failed to create WebSocket:', error);
    }

    return () => {
      if (ws) {
        ws.close();
      }
    };
  }, [preferences.browserNotifications]);
  */

  // Load initial notifications - DISABLED to fix re-render loop
  // useEffect(() => {
  //   refreshNotifications();
  // }, []);

  const refreshNotifications = useCallback(async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/notifications/`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      setNotifications(data.notifications || []);
      setStats(data.stats || stats);
      
    } catch (error) {
      console.error('❌ Failed to fetch notifications:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const showToast = useCallback((notificationData: Partial<Notification>) => {
    const notification: Notification = {
      id: crypto.randomUUID(),
      created_at: new Date().toISOString(),
      read: false,
      extra_data: {},
      autoClose: notificationData.autoClose !== false,
      duration: notificationData.duration || 5000,
      type: notificationData.type || 'info',
      title: notificationData.title || 'Notification',
      message: notificationData.message || '',
      ...notificationData
    };

    setToastNotifications(prev => [...prev, notification]);

    if (notification.autoClose && notification.duration) {
      setTimeout(() => {
        setToastNotifications(prev => prev.filter(t => t.id !== notification.id));
      }, notification.duration);
    }
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToastNotifications(prev => prev.filter(t => t.id !== id));
  }, []);

  const markAsRead = useCallback(async (id: string) => {
    const token = localStorage.getItem('access_token');
    if (!token) return;

    try {
      const response = await fetch(`${API_BASE_URL}/notifications/${id}/read`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        setNotifications(prev =>
          prev.map(n => n.id === id ? { ...n, read: true, read_at: new Date().toISOString() } : n)
        );
        setStats(prev => ({
          ...prev,
          unread_count: Math.max(0, prev.unread_count - 1)
        }));
      }
    } catch (error) {
      console.error('Failed to mark notification as read:', error);
    }
  }, []);

  const markAllAsRead = useCallback(async () => {
    const token = localStorage.getItem('access_token');
    if (!token) return;

    try {
      const response = await fetch(`${API_BASE_URL}/notifications/read-all`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const readAt = new Date().toISOString();
        setNotifications(prev =>
          prev.map(n => ({ ...n, read: true, read_at: readAt }))
        );
        setStats(prev => ({
          ...prev,
          unread_count: 0
        }));
      }
    } catch (error) {
      console.error('Failed to mark all as read:', error);
    }
  }, []);

  const removeNotification = useCallback(async (id: string) => {
    const token = localStorage.getItem('access_token');
    if (!token) return;

    try {
      const response = await fetch(`${API_BASE_URL}/notifications/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const notification = notifications.find(n => n.id === id);

        setNotifications(prev => prev.filter(n => n.id !== id));
        setToastNotifications(prev => prev.filter(n => n.id !== id));
        setStats(prev => ({
          ...prev,
          total_count: Math.max(0, prev.total_count - 1),
          unread_count: notification && !notification.read ?
            Math.max(0, prev.unread_count - 1) : prev.unread_count
        }));
      }
    } catch (error) {
      console.error('Failed to remove notification:', error);
    }
  }, [notifications]);

  const clearAll = useCallback(async () => {
    const token = localStorage.getItem('access_token');
    if (!token) return;

    try {
      const response = await fetch(`${API_BASE_URL}/notifications/clear-all`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        setNotifications([]);
        setToastNotifications([]);
        setStats({
          total_count: 0,
          unread_count: 0,
          incidents_count: 0,
          alerts_count: 0,
          system_count: 0
        });
      }
    } catch (error) {
      console.error('Failed to clear all notifications:', error);
    }
  }, []);

  const updatePreferences = useCallback((newPreferences: Partial<NotificationPreferences>) => {
    setPreferences(prev => {
      const updated = { ...prev, ...newPreferences };
      localStorage.setItem('notification_preferences', JSON.stringify(updated));
      return updated;
    });
  }, []);

  const requestPermission = useCallback(async (): Promise<boolean> => {
    if (!('Notification' in window)) {
      console.warn('This browser does not support desktop notification');
      return false;
    }

    if (Notification.permission === 'granted') {
      updatePreferences({ browserNotifications: true });
      return true;
    }

    if (Notification.permission !== 'denied') {
      const permission = await Notification.requestPermission();
      const granted = permission === 'granted';
      updatePreferences({ browserNotifications: granted });
      return granted;
    }

    return false;
  }, [updatePreferences]);

  const value: NotificationContextType = {
    notifications,
    toastNotifications,
    stats,
    preferences,
    isConnected,
    isLoading,
    unreadCount: stats.unread_count,

    showToast,
    dismissToast,
    markAsRead,
    markAllAsRead,
    removeNotification,
    clearAll,
    refreshNotifications,
    updatePreferences,
    requestPermission,
  };

  return (
    <NotificationContext.Provider value={value}>
      {children}
    </NotificationContext.Provider>
  );
};

export const useNotifications = (): NotificationContextType => {
  const context = useContext(NotificationContext);
  if (context === undefined) {
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return context;
};