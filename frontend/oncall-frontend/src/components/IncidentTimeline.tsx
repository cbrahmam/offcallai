// frontend/oncall-frontend/src/components/IncidentTimeline.tsx
import React, { useState, useEffect, useCallback } from 'react';
import {
  AlertTriangle,
  Bell,
  CheckCircle,
  Clock,
  MessageSquare,
  RefreshCw,
  Settings2,
  User,
  UserPlus
} from 'lucide-react';

import { API_URL as API_BASE_URL } from '../config/api';

interface TimelineEvent {
  id: string;
  type: 'created' | 'status_changed' | 'assigned' | 'comment' | 'escalated' | 'acknowledged' | 'resolved' | 'updated';
  timestamp: string;
  user_name: string;
  user_id: string;
  description: string;
  details?: {
    old_value?: string;
    new_value?: string;
    comment?: string;
    metadata?: any;
  };
}

interface IncidentTimelineProps {
  incidentId: string;
}

const IncidentTimeline: React.FC<IncidentTimelineProps> = ({ incidentId }) => {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTimeline = useCallback(async () => {
    try {
      setError(null);
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/incidents/${incidentId}/timeline`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        setEvents(data.events || []);
      } else if (response.status === 404) {
        // Timeline endpoint may not exist for this incident yet - that's OK
        setEvents([]);
      } else {
        setError('Failed to load timeline. Please try again.');
      }
    } catch (error) {
      setError('Unable to connect to server. Please check your connection.');
    } finally {
      setIsLoading(false);
    }
  }, [incidentId]);

  useEffect(() => {
    fetchTimeline();
    // Set up polling for real-time updates (only if no error)
    const interval = setInterval(() => {
      if (!error) {
        fetchTimeline();
      }
    }, 30000); // Poll every 30 seconds
    return () => clearInterval(interval);
  }, [fetchTimeline, error]);

  const getEventIcon = (type: string) => {
    switch (type) {
      case 'created':
        return <AlertTriangle className="w-5 h-5 text-orange-400" />;
      case 'status_changed':
        return <RefreshCw className="w-5 h-5 text-blue-400" />;
      case 'assigned':
        return <UserPlus className="w-5 h-5 text-purple-400" />;
      case 'comment':
        return <MessageSquare className="w-5 h-5 text-green-400" />;
      case 'escalated':
        return <Bell className="w-5 h-5 text-red-400" />;
      case 'acknowledged':
        return <CheckCircle className="w-5 h-5 text-yellow-400" />;
      case 'resolved':
        return <CheckCircle className="w-5 h-5 text-green-400" />;
      case 'updated':
        return <Settings2 className="w-5 h-5 text-muted-foreground" />;
      default:
        return <Clock className="w-5 h-5 text-muted-foreground" />;
    }
  };


  const getEventColor = (type: string) => {
    switch (type) {
      case 'created':
        return 'border-orange-500/30 bg-orange-500/5';
      case 'status_changed':
        return 'border-blue-500/30 bg-blue-500/5';
      case 'assigned':
        return 'border-purple-500/30 bg-purple-500/5';
      case 'comment':
        return 'border-green-500/30 bg-green-500/5';
      case 'escalated':
        return 'border-red-500/30 bg-red-500/5';
      case 'acknowledged':
        return 'border-yellow-500/30 bg-yellow-500/5';
      case 'resolved':
        return 'border-green-500/30 bg-green-500/5';
      case 'updated':
        return 'border-border bg-secondary/50';
      default:
        return 'border-border bg-secondary/50';
    }
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    let relative = '';
    if (days > 0) relative = `${days} day${days > 1 ? 's' : ''} ago`;
    else if (hours > 0) relative = `${hours} hour${hours > 1 ? 's' : ''} ago`;
    else if (minutes > 0) relative = `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
    else relative = 'Just now';

    return {
      absolute: date.toLocaleString(),
      relative
    };
  };

  const renderEventDetails = (event: TimelineEvent) => {
    switch (event.type) {
      case 'status_changed':
        return (
          <div className="text-sm text-foreground mt-1 flex items-center gap-2">
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-red-500/10 text-red-400 border-red-500/20">{event.details?.old_value}</span>
            <span className="text-muted-foreground">→</span>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-emerald-500/10 text-emerald-400 border-emerald-500/20">{event.details?.new_value}</span>
          </div>
        );

      case 'assigned':
        return (
          <div className="text-sm text-foreground mt-1 flex items-center gap-2">
            {event.details?.old_value && (
              <>
                <span className="text-muted-foreground">{event.details.old_value}</span>
                <span className="text-muted-foreground">→</span>
              </>
            )}
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-secondary text-muted-foreground border-border">{event.details?.new_value}</span>
          </div>
        );

      case 'comment':
        return (
          <div className="mt-2 p-3 bg-secondary/50 rounded-lg border border-border/30">
            <p className="text-foreground text-sm">{event.details?.comment}</p>
          </div>
        );

      case 'created':
        return event.details?.metadata && (
          <div className="text-sm text-muted-foreground mt-1 flex items-center gap-2">
            Severity: <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-yellow-500/10 text-yellow-400 border-yellow-500/20">{event.details.metadata.severity}</span>
            {event.details.metadata.source && (
              <>
                <span className="text-muted-foreground">Source:</span>
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-secondary text-muted-foreground border-border">{event.details.metadata.source}</span>
              </>
            )}
          </div>
        );

      case 'resolved':
        return event.details?.comment && (
          <div className="mt-2 p-3 bg-green-500/10 rounded-lg border border-green-500/20">
            <p className="text-emerald-400 text-sm">{event.details.comment}</p>
          </div>
        );

      default:
        return null;
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-8 h-8 border-4 border-purple-500/30 border-t-purple-500 rounded-full animate-spin"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <div className="p-3 rounded-xl bg-red-500/10 w-fit mx-auto mb-4">
          <AlertTriangle className="w-6 h-6 text-red-400" />
        </div>
        <h3 className="text-lg font-semibold text-muted-foreground mb-2">Unable to Load Timeline</h3>
        <p className="text-muted-foreground text-sm mb-4">{error}</p>
        <button
          onClick={() => fetchTimeline()}
          className="bg-primary text-primary-foreground hover:bg-white/90 rounded-md px-6 py-2.5 text-sm font-medium"
        >
          Try Again
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {events.length === 0 ? (
        <div className="text-center py-12">
          <div className="p-3 rounded-xl bg-purple-500/10 w-fit mx-auto mb-4">
            <Clock className="w-10 h-10 text-purple-400" />
          </div>
          <h3 className="text-lg font-semibold text-muted-foreground mb-2">No Timeline Events</h3>
          <p className="text-muted-foreground text-sm">
            Timeline events will appear here as the incident progresses.
          </p>
        </div>
      ) : (
        <div className="relative">
          {/* Timeline Line */}
          <div className="absolute left-6 top-0 bottom-0 w-px bg-secondary"></div>

          {events.map((event, index) => {
            const timestamp = formatTimestamp(event.timestamp);
            const isSystem = event.user_id === 'system';

            return (
              <div key={event.id} className="relative flex items-start space-x-4 pb-6">
                {/* Timeline Dot */}
                <div className={`relative z-10 flex items-center justify-center w-12 h-12 rounded-full border-2 ${getEventColor(event.type)} backdrop-blur-sm`}>
                  {getEventIcon(event.type)}
                </div>

                {/* Event Content */}
                <div className="flex-1 min-w-0">
                  <div className="border border-border rounded-lg bg-transparent p-4">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center space-x-2">
                          {!isSystem && <User className="w-4 h-4 text-muted-foreground" />}
                          <span className={`font-medium ${isSystem ? 'text-purple-400' : 'text-foreground'}`}>
                            {event.user_name}
                          </span>
                          <span className="text-muted-foreground text-sm">
                            {event.description}
                          </span>
                        </div>

                        {renderEventDetails(event)}
                      </div>

                      <div className="text-right text-xs text-muted-foreground">
                        <p>{timestamp.relative}</p>
                        <p className="mt-1">{timestamp.absolute}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Real-time Indicator */}
      <div className="flex items-center justify-center py-4">
        <div className="flex items-center space-x-2 px-3 py-1 bg-green-500/10 rounded-full border border-green-500/20">
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 inline-block" />
          <span className="text-emerald-400 text-xs font-medium">Live Timeline</span>
        </div>
      </div>
    </div>
  );
};

export default IncidentTimeline;
