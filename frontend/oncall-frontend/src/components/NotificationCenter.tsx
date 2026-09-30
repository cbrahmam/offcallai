// frontend/oncall-frontend/src/components/NotificationCenter.tsx
import React, { useState, useEffect } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  Bell,
  Check,
  CheckCircle,
  Flame,
  Info,
  Trash2,
  X
} from 'lucide-react';
import { useNotifications } from '../contexts/NotificationContext';

type NotificationFilter = 'all' | 'unread' | 'incidents' | 'alerts';

interface NotificationCenterProps {
  isOpen: boolean;
  onClose: () => void;
}

const NotificationCenter: React.FC<NotificationCenterProps> = ({ isOpen, onClose }) => {
  const {
    notifications,
    stats,
    isConnected,
    markAsRead,
    markAllAsRead,
    removeNotification,
    clearAll
  } = useNotifications();

  const [filter, setFilter] = useState<NotificationFilter>('all');

  if (!isOpen) return null;

  const filteredNotifications = notifications.filter(notification => {
    switch (filter) {
      case 'unread':
        return !notification.read;
      case 'incidents':
        return notification.type === 'incident' || notification.type === 'incident_created';
      case 'alerts':
        return notification.type === 'alert';
      default:
        return true;
    }
  });

  const getIcon = (type: string, severity?: string) => {
    if (type.includes('incident') || type === 'alert') {
      switch (severity) {
        case 'critical':
          return <Flame className="w-5 h-5 text-red-400" />;
        case 'high':
          return <AlertTriangle className="w-5 h-5 text-orange-400" />;
        case 'medium':
          return <AlertCircle className="w-5 h-5 text-yellow-400" />;
        case 'low':
          return <Info className="w-5 h-5 text-blue-400" />;
        default:
          return <Bell className="w-5 h-5 text-blue-400" />;
      }
    }

    switch (type) {
      case 'success':
        return <CheckCircle className="w-5 h-5 text-green-400" />;
      case 'warning':
        return <AlertTriangle className="w-5 h-5 text-yellow-400" />;
      case 'error':
        return <AlertCircle className="w-5 h-5 text-red-400" />;
      default:
        return <Info className="w-5 h-5 text-blue-400" />;
    }
  };

  const formatTimestamp = (timestamp: string | Date) => {
    const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp;
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) return `${days}d ago`;
    if (hours > 0) return `${hours}h ago`;
    if (minutes > 0) return `${minutes}m ago`;
    return 'Just now';
  };

  const handleNotificationClick = async (notification: any) => {
    // Mark as read
    if (!notification.read) {
      await markAsRead(notification.id);
    }

    // Navigate
    if (notification.action_url) {
      window.location.href = notification.action_url;
    } else if (notification.incident_id) {
      window.location.href = `/incidents/${notification.incident_id}`;
    }
  };

  const handleClearAll = async () => {
    await clearAll();
  };

  const handleMarkAllRead = async () => {
    await markAllAsRead();
  };

  const getSeverityBadgeVariant = (severity: string): 'error' | 'warning' | 'info' | 'default' => {
    switch (severity) {
      case 'critical': return 'error';
      case 'high': return 'warning';
      case 'medium': return 'warning';
      default: return 'info';
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed right-0 top-0 h-full w-96 bg-background border-l border-border z-50 flex flex-col">
        {/* Header */}
        <div className="relative overflow-hidden p-6 border-b border-border">
          <div className="absolute inset-0 bg-transparent" />
          <div className="relative flex items-center justify-between mb-4">
            <div className="flex items-center space-x-3">
              <div className="p-2 rounded-xl bg-secondary">
                <Bell className="w-5 h-5 text-foreground" />
              </div>
              <span className="text-base font-medium text-foreground">Notifications</span>
              {stats.unread_count > 0 && (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-red-500/10 text-red-400 border-red-500/20">
                  {stats.unread_count}
                </span>
              )}
            </div>
            <div className="flex items-center space-x-2">
              {/* Connection status */}
              <span className={`h-2.5 w-2.5 rounded-full inline-block ${isConnected ? 'bg-emerald-500' : 'bg-red-500'}`} />
              <button
                onClick={onClose}
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
          </div>

          {/* Filter buttons */}
          <div className="relative flex space-x-2">
            {[
              { key: 'all', label: 'All' },
              { key: 'unread', label: 'Unread' },
              { key: 'incidents', label: 'Incidents' },
              { key: 'alerts', label: 'Alerts' }
            ].map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setFilter(key as NotificationFilter)}
                className={`px-3 py-1 rounded-lg text-sm font-medium transition-all ${
                  filter === key
                    ? 'text-foreground bg-secondary'
                    : 'text-muted-foreground hover:text-foreground hover:bg-accent'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Action buttons */}
          {notifications.length > 0 && (
            <div className="relative mt-4 flex space-x-2">
              {stats.unread_count > 0 && (
                <button
                  onClick={handleMarkAllRead}
                  className="!bg-green-500/10 text-green-400 border border-green-500/20 hover:!bg-green-500/20 rounded-md px-3 py-1.5 text-sm font-medium inline-flex items-center gap-1.5"
                >
                  <Check className="w-4 h-4" />
                  <span>Mark all read</span>
                </button>
              )}
              <button
                onClick={handleClearAll}
                className="!bg-red-500/10 text-red-400 border border-red-500/20 hover:!bg-red-500/20 rounded-md px-3 py-1.5 text-sm font-medium inline-flex items-center gap-1.5"
              >
                <Trash2 className="w-4 h-4" />
                <span>Clear all</span>
              </button>
            </div>
          )}
        </div>

        {/* Notifications list */}
        <div className="flex-1 overflow-y-auto">
          {filteredNotifications.length === 0 ? (
            <div className="p-8 text-center">
              <div className="p-4 rounded-2xl bg-accent inline-block mb-4">
                <Bell className="w-12 h-12 text-muted-foreground mx-auto" />
              </div>
              <h3 className="text-base font-medium text-muted-foreground mb-2">No notifications</h3>
              <p className="text-muted-foreground text-sm">
                {filter === 'unread'
                  ? "You're all caught up!"
                  : "Notifications will appear here when events occur."
                }
              </p>
            </div>
          ) : (
            <div className="divide-y divide-border">
              {filteredNotifications.map((notification) => (
                <div
                  key={notification.id}
                  className={`p-4 hover:bg-accent transition-colors cursor-pointer ${
                    !notification.read ? 'bg-blue-500/5 border-l-4 border-l-blue-500' : ''
                  }`}
                  onClick={() => handleNotificationClick(notification)}
                >
                  <div className="flex items-start space-x-3">
                    {/* Icon */}
                    <div className="flex-shrink-0 mt-1 p-1.5 rounded-lg bg-accent">
                      {getIcon(notification.type, notification.severity)}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <p className={`text-sm font-medium ${!notification.read ? 'text-foreground' : 'text-foreground'}`}>
                            {notification.title}
                          </p>
                          <p className="text-sm text-muted-foreground mt-1">
                            {notification.message}
                          </p>
                          {notification.severity && (
                            <span
                              className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border mt-2 ${
                                getSeverityBadgeVariant(notification.severity) === 'error' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                                getSeverityBadgeVariant(notification.severity) === 'warning' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                                'bg-blue-500/10 text-blue-400 border-blue-500/20'
                              }`}
                            >
                              {notification.severity.toUpperCase()}
                            </span>
                          )}
                        </div>
                        <button
                          onClick={async (e) => {
                            e.stopPropagation();
                            await removeNotification(notification.id);
                          }}
                          className="text-muted-foreground hover:text-red-400 transition-colors ml-2"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                      <p className="text-xs text-muted-foreground mt-2">
                        {formatTimestamp(notification.created_at)}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
};

export default NotificationCenter;
