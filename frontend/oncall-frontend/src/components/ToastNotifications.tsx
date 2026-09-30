// frontend/oncall-frontend/src/components/ToastNotifications.tsx
// COMPLETE REWRITE - PRODUCTION READY WITH THEME SUPPORT
import React from 'react';
import {
  AlertCircle,
  AlertTriangle,
  Bell,
  CheckCircle,
  Flame,
  Info,
  X
} from 'lucide-react';
import { useNotifications } from '../contexts/NotificationContext';

const ToastNotifications: React.FC = () => {
  const { toastNotifications, dismissToast, markAsRead } = useNotifications();

  const getIcon = (type: string, severity?: string) => {
    const iconClass = "w-5 h-5";

    if (severity === 'critical') return <Flame className={`${iconClass} text-red-500`} />;
    if (severity === 'high') return <AlertTriangle className={`${iconClass} text-orange-500`} />;
    if (severity === 'medium') return <AlertCircle className={`${iconClass} text-yellow-500`} />;
    if (severity === 'low') return <Info className={`${iconClass} text-blue-500`} />;

    if (type === 'success') return <CheckCircle className={`${iconClass} text-green-500`} />;
    if (type === 'error') return <AlertCircle className={`${iconClass} text-red-500`} />;
    if (type === 'warning') return <AlertTriangle className={`${iconClass} text-yellow-500`} />;

    return <Bell className={`${iconClass} text-blue-500`} />;
  };

  const getToastStyle = (type: string, severity?: string) => {
    // Base styles with theme-aware colors
    const baseStyle = "bg-popover border border-border";

    // Colored left border based on type/severity
    if (severity === 'critical') return `${baseStyle} border-l-4 border-l-red-500`;
    if (severity === 'high') return `${baseStyle} border-l-4 border-l-orange-500`;
    if (severity === 'medium') return `${baseStyle} border-l-4 border-l-yellow-500`;
    if (severity === 'low') return `${baseStyle} border-l-4 border-l-blue-500`;

    if (type === 'success') return `${baseStyle} border-l-4 border-l-green-500`;
    if (type === 'error') return `${baseStyle} border-l-4 border-l-red-500`;
    if (type === 'warning') return `${baseStyle} border-l-4 border-l-yellow-500`;
    if (type === 'info') return `${baseStyle} border-l-4 border-l-blue-500`;

    return `${baseStyle} border-l-4 border-l-white/20`;
  };

  const getIconBackground = (type: string, severity?: string) => {
    if (severity === 'critical') return "bg-red-500/20";
    if (severity === 'high') return "bg-orange-500/20";
    if (severity === 'medium') return "bg-yellow-500/20";
    if (severity === 'low') return "bg-blue-500/20";

    if (type === 'success') return "bg-emerald-500/20";
    if (type === 'error') return "bg-red-500/20";
    if (type === 'warning') return "bg-yellow-500/20";

    return "bg-blue-500/20";
  };

  const handleToastClick = async (notification: any) => {
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

  const handleDismiss = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    dismissToast(id);
  };

  if (toastNotifications.length === 0) {
    return null;
  }

  // Show max 5 toasts
  const visibleToasts = toastNotifications.slice(0, 5);

  return (
    <div className="fixed top-20 right-4 z-50 space-y-3 max-w-sm w-full pointer-events-none">
      <div className="space-y-3 pointer-events-auto">
        {visibleToasts.map((notification) => (
          <div
            key={notification.id}
            className={`${getToastStyle(notification.type, notification.severity)} p-4 rounded-xl cursor-pointer transform transition-all duration-300 ease-out animate-slide-in-right hover:scale-[1.02]`}
            onClick={() => handleToastClick(notification)}
          >
            <div className="flex items-start gap-3">
              {/* Icon with background */}
              <div className={`flex-shrink-0 p-2 rounded-lg ${getIconBackground(notification.type, notification.severity)}`}>
                {getIcon(notification.type, notification.severity)}
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-foreground truncate">
                      {notification.title}
                    </p>
                    <p className="mt-1 text-sm text-muted-foreground line-clamp-2">
                      {notification.message}
                    </p>

                    {/* Timestamp */}
                    <p className="mt-2 text-xs text-muted-foreground">
                      {new Date(notification.created_at).toLocaleTimeString()}
                    </p>
                  </div>

                  {/* Close button */}
                  <button
                    onClick={(e) => handleDismiss(notification.id, e)}
                    className="flex-shrink-0 text-muted-foreground hover:text-foreground transition-colors duration-200 p-1.5 rounded-lg hover:bg-accent"
                    aria-label="Close notification"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                {/* Progress bar for auto-dismiss */}
                {notification.autoClose && notification.duration && (
                  <div className="mt-3 w-full bg-secondary rounded-full h-1 overflow-hidden">
                    <div
                      className="h-full bg-white/40 rounded-full"
                      style={{
                        animation: `shrink ${notification.duration}ms linear`,
                      }}
                    ></div>
                  </div>
                )}

                {/* Action buttons for critical incidents */}
                {notification.severity === 'critical' && (notification.type === 'incident' || notification.type === 'incident_created') && (
                  <div className="mt-3 flex gap-2">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        if (notification.incident_id) {
                          window.location.href = `/incidents/${notification.incident_id}`;
                        }
                      }}
                      className="px-3 py-1.5 bg-yellow-500/20 text-yellow-400 rounded-lg text-xs font-medium hover:bg-yellow-500/30 transition-colors"
                    >
                      Acknowledge
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        const url = notification.action_url || (notification.incident_id ? `/incidents/${notification.incident_id}` : null);
                        if (url) {
                          window.location.href = url;
                        }
                      }}
                      className="px-3 py-1.5 bg-blue-500/20 text-blue-400 rounded-lg text-xs font-medium hover:bg-blue-500/30 transition-colors"
                    >
                      View Details
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}

        {/* Show indicator if there are more notifications */}
        {toastNotifications.length > 5 && (
          <div className="bg-popover border border-border p-3 rounded-xl text-center">
            <p className="text-sm text-muted-foreground">
              +{toastNotifications.length - 5} more notifications
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default ToastNotifications;
