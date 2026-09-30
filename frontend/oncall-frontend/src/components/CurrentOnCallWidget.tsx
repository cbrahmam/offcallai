// CurrentOnCallWidget.tsx - Widget showing who is currently on-call
import React, { useState, useEffect, useCallback } from 'react';
import {
  CalendarDays,
  Clock,
  Phone,
  UserCircle
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

import { API_URL as API_BASE_URL } from '../config/api';

interface CurrentOnCallUser {
  user_id: string;
  user_email: string;
  user_full_name: string | null;
  schedule_id: string;
  schedule_name: string;
  shift_start: string;
  shift_end: string;
  notify_channels: string[];
}

interface OnCallUsersResponse {
  users: CurrentOnCallUser[];
  total: number;
}

interface CurrentOnCallWidgetProps {
  onManageSchedules?: () => void;
}

const CurrentOnCallWidget: React.FC<CurrentOnCallWidgetProps> = ({ onManageSchedules }) => {
  const { token } = useAuth();
  const [onCallUsers, setOnCallUsers] = useState<CurrentOnCallUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const hasFetchedRef = React.useRef(false);

  const loadOnCallUsers = useCallback(async () => {
    const currentToken = localStorage.getItem('access_token');
    if (!currentToken) return;

    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${API_BASE_URL}/on-call-schedules/on-call/all`, {
        headers: {
          'Authorization': `Bearer ${currentToken}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error('Failed to fetch on-call users');
      }

      const data: OnCallUsersResponse = await response.json();
      setOnCallUsers(data.users);
    } catch (err: any) {
      console.error('Error loading on-call users:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Only fetch once on mount
    if (hasFetchedRef.current) return;
    hasFetchedRef.current = true;

    loadOnCallUsers();
    // Refresh every 5 minutes
    const interval = setInterval(loadOnCallUsers, 5 * 60 * 1000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Format time remaining
  const getTimeRemaining = (endTime: string) => {
    const end = new Date(endTime);
    const now = new Date();
    const diff = end.getTime() - now.getTime();

    if (diff <= 0) return 'Shift ended';

    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

    if (hours > 0) {
      return `${hours}h ${minutes}m remaining`;
    }
    return `${minutes}m remaining`;
  };

  // Get initials
  const getInitials = (name: string | null, email: string) => {
    if (name) {
      return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
    }
    return email[0].toUpperCase();
  };

  if (loading) {
    return (
      <div className="bg-transparent border border-border rounded-xl p-4">
        <div className="flex items-center gap-2 mb-4">
          <div className="p-2 rounded-xl bg-secondary">
            <Phone className="h-4 w-4 text-foreground" />
          </div>
          <h3 className="text-base font-medium text-foreground">Currently On-Call</h3>
          <span className="w-2 h-2 rounded-full bg-emerald-400 ml-auto"></span>
        </div>
        <div className="flex items-center justify-center py-4">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-zinc-400"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-transparent border border-border rounded-xl p-4">
        <div className="flex items-center gap-2 mb-4">
          <div className="p-2 rounded-xl bg-secondary">
            <Phone className="h-4 w-4 text-foreground" />
          </div>
          <h3 className="text-base font-medium text-foreground">Currently On-Call</h3>
        </div>
        <p className="text-muted-foreground text-sm text-center py-4">Unable to load on-call status</p>
      </div>
    );
  }

  return (
    <div className="bg-transparent border border-border rounded-xl p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-xl bg-secondary">
            <Phone className="h-4 w-4 text-foreground" />
          </div>
          <h3 className="text-base font-medium text-foreground">Currently On-Call</h3>
          <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
        </div>
        {onManageSchedules && (
          <button
            onClick={onManageSchedules}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            Manage
          </button>
        )}
      </div>

      {onCallUsers.length === 0 ? (
        <div className="text-center py-4">
          <UserCircle className="h-10 w-10 text-muted-foreground mx-auto mb-2" />
          <p className="text-muted-foreground text-sm">No one currently on-call</p>
          {onManageSchedules && (
            <button
              onClick={onManageSchedules}
              className="mt-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              Set up schedules
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {onCallUsers.map((user, index) => (
            <div
              key={`${user.user_id}-${user.schedule_id}-${index}`}
              className="flex items-center gap-3 p-2.5 bg-transparent border border-border rounded-lg hover:bg-accent transition-colors"
            >
              <div className="w-10 h-10 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 font-medium text-sm">
                {getInitials(user.user_full_name, user.user_email)}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-base font-medium text-foreground truncate">
                  {user.user_full_name || user.user_email}
                </p>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span className="text-xs px-1.5 py-0 bg-blue-500/10 text-blue-400 rounded-full flex items-center">
                    <CalendarDays className="h-2.5 w-2.5 mr-1" />
                    {user.schedule_name}
                  </span>
                </div>
              </div>
              <div className="text-right">
                <span className="text-xs px-1.5 py-0 bg-emerald-500/10 text-emerald-400 rounded-full flex items-center">
                  <Clock className="h-2.5 w-2.5 mr-1" />
                  {getTimeRemaining(user.shift_end)}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Refresh indicator */}
      <div className="mt-3 pt-3 border-t border-border flex items-center justify-between">
        <span className="text-xs text-muted-foreground">Auto-refreshes every 5 min</span>
        <button
          onClick={loadOnCallUsers}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          Refresh now
        </button>
      </div>
    </div>
  );
};

export default CurrentOnCallWidget;
