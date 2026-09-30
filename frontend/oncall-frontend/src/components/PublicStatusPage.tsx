// PublicStatusPage.tsx - Public-facing status page
import React, { useState, useEffect, useCallback } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle,
  Mail,
  RefreshCw,
  Wrench
} from 'lucide-react';

import { API_URL as API_BASE_URL } from '../config/api';

type ServiceStatus = 'operational' | 'degraded' | 'partial_outage' | 'major_outage' | 'maintenance';

interface ServiceWithUptime {
  id: string;
  name: string;
  description: string | null;
  status: ServiceStatus;
  group_name: string | null;
  uptime_records: {
    date: string;
    uptime_percentage: number;
  }[];
}

interface PublicIncident {
  id: string;
  title: string;
  status: string;
  severity: string;
  created_at: string;
  resolved_at: string | null;
  description: string | null;
}

interface PublicMaintenance {
  id: string;
  name: string;
  description: string | null;
  start_time: string;
  end_time: string;
  services: string[];
  is_currently_active: boolean;
}

interface PublicStatusPageData {
  name: string;
  description: string | null;
  logo_url: string | null;
  primary_color: string;
  overall_status: ServiceStatus;
  services: ServiceWithUptime[];
  active_incidents: PublicIncident[];
  scheduled_maintenance: PublicMaintenance[];
  past_incidents: PublicIncident[];
  allow_subscriptions: boolean;
  support_url: string | null;
  support_email: string | null;
}

const statusConfig: Record<ServiceStatus, { label: string; color: string; bgColor: string; borderColor: string; icon: React.ReactNode }> = {
  operational: {
    label: 'All Systems Operational',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500/20',
    icon: <CheckCircle className="h-6 w-6 text-emerald-400" />,
  },
  degraded: {
    label: 'Degraded Performance',
    color: 'text-yellow-400',
    bgColor: 'bg-yellow-500/10',
    borderColor: 'border-yellow-500/20',
    icon: <AlertTriangle className="h-6 w-6 text-yellow-400" />,
  },
  partial_outage: {
    label: 'Partial System Outage',
    color: 'text-orange-400',
    bgColor: 'bg-orange-500/10',
    borderColor: 'border-orange-500/20',
    icon: <AlertCircle className="h-6 w-6 text-orange-400" />,
  },
  major_outage: {
    label: 'Major System Outage',
    color: 'text-red-400',
    bgColor: 'bg-red-500/10',
    borderColor: 'border-red-500/20',
    icon: <AlertCircle className="h-6 w-6 text-red-400" />,
  },
  maintenance: {
    label: 'Under Maintenance',
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10',
    borderColor: 'border-blue-500/20',
    icon: <Wrench className="h-6 w-6 text-blue-400" />,
  }
};

interface PublicStatusPageProps {
  slug: string;
}

const PublicStatusPage: React.FC<PublicStatusPageProps> = ({ slug }) => {
  const [data, setData] = useState<PublicStatusPageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [subscribeEmail, setSubscribeEmail] = useState('');
  const [subscribing, setSubscribing] = useState(false);
  const [subscribeMessage, setSubscribeMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  const loadStatus = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/status-pages/public/${slug}`);

      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('Status page not found');
        }
        throw new Error('Failed to load status page');
      }

      const result = await response.json();
      setData(result);
      setLastUpdated(new Date());
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    loadStatus();

    // Auto-refresh every 60 seconds
    const interval = setInterval(loadStatus, 60000);
    return () => clearInterval(interval);
  }, [loadStatus]);

  const handleSubscribe = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!subscribeEmail) return;

    setSubscribing(true);
    setSubscribeMessage(null);

    try {
      const response = await fetch(`${API_BASE_URL}/status-pages/public/${slug}/subscribe`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ email: subscribeEmail })
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Failed to subscribe');
      }

      setSubscribeMessage({ type: 'success', text: 'Subscribed! Please check your email to verify.' });
      setSubscribeEmail('');
    } catch (err: any) {
      setSubscribeMessage({ type: 'error', text: err.message });
    } finally {
      setSubscribing(false);
    }
  };

  const getServiceStatusIcon = (status: ServiceStatus) => {
    switch (status) {
      case 'operational':
        return <CheckCircle className="h-5 w-5 text-emerald-400" />;
      case 'degraded':
        return <AlertTriangle className="h-5 w-5 text-yellow-400" />;
      case 'partial_outage':
        return <AlertCircle className="h-5 w-5 text-orange-400" />;
      case 'major_outage':
        return <AlertCircle className="h-5 w-5 text-red-400" />;
      case 'maintenance':
        return <Wrench className="h-5 w-5 text-blue-400" />;
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  const formatRelativeTime = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  if (loading && !data) {
    return (
      <div className="min-h-screen bg-background">
        <div className="flex items-center justify-center min-h-screen">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white/20 mx-auto mb-4"></div>
            <p className="text-sm text-muted-foreground">Loading status...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-background">
        <div className="flex items-center justify-center min-h-screen">
          <div className="text-center">
            <AlertCircle className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
            <h1 className="text-xl font-semibold text-foreground mb-2">Status Page Not Found</h1>
            <p className="text-sm text-muted-foreground">{error || 'The requested status page does not exist.'}</p>
          </div>
        </div>
      </div>
    );
  }

  const overallConfig = statusConfig[data.overall_status];

  // Group services by group_name
  const groupedServices = data.services.reduce((acc, service) => {
    const group = service.group_name || 'Services';
    if (!acc[group]) acc[group] = [];
    acc[group].push(service);
    return acc;
  }, {} as Record<string, ServiceWithUptime[]>);

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-background">
        <div className="max-w-4xl mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              {data.logo_url && (
                <img src={data.logo_url} alt={data.name} className="h-10 w-auto" />
              )}
              <div>
                <h1 className="text-xl font-semibold text-foreground">{data.name}</h1>
                {data.description && (
                  <p className="text-sm text-muted-foreground">{data.description}</p>
                )}
              </div>
            </div>
            <button
              onClick={loadStatus}
              className="p-2 text-muted-foreground hover:text-foreground transition-colors"
              title="Refresh"
            >
              <RefreshCw className={`h-5 w-5 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8">
        {/* Overall Status */}
        <div className={`bg-transparent border ${overallConfig.borderColor} rounded-xl p-6 mb-8`}>
          <div className="flex items-center gap-3">
            <span className={`w-2.5 h-2.5 rounded-full ${overallConfig.bgColor.replace('/10', '')}`}></span>
            {overallConfig.icon}
            <span className={`text-base font-medium ${overallConfig.color}`}>
              {overallConfig.label}
            </span>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            Last updated: {lastUpdated.toLocaleTimeString()}
          </p>
        </div>

        {/* Active Incidents */}
        {data.active_incidents.length > 0 && (
          <div className="mb-8">
            <h2 className="text-base font-medium text-foreground mb-4">Active Incidents</h2>
            <div className="space-y-3">
              {data.active_incidents.map((incident) => (
                <div key={incident.id} className="bg-transparent border border-red-500/20 rounded-xl p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="text-sm font-medium text-red-400">{incident.title}</h3>
                      {incident.description && (
                        <p className="text-sm text-red-400/70 mt-1">{incident.description}</p>
                      )}
                    </div>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-red-500/10 text-red-400">
                      {incident.severity}
                    </span>
                  </div>
                  <p className="text-xs text-red-400/50 mt-2">
                    Started {formatRelativeTime(incident.created_at)}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Scheduled Maintenance */}
        {data.scheduled_maintenance.length > 0 && (
          <div className="mb-8">
            <h2 className="text-base font-medium text-foreground mb-4">Scheduled Maintenance</h2>
            <div className="space-y-3">
              {data.scheduled_maintenance.map((maint) => (
                <div key={maint.id} className={`bg-transparent border ${maint.is_currently_active ? 'border-blue-500/20' : 'border-border'} rounded-xl p-4`}>
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="text-sm font-medium text-foreground flex items-center gap-2">
                        {maint.name}
                        {maint.is_currently_active && (
                          <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400">
                            In Progress
                          </span>
                        )}
                      </h3>
                      {maint.description && (
                        <p className="text-sm text-muted-foreground mt-1">{maint.description}</p>
                      )}
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    {formatDate(maint.start_time)} - {formatDate(maint.end_time)}
                  </p>
                  {maint.services.length > 0 && (
                    <p className="text-xs text-muted-foreground mt-1">
                      Affected: {maint.services.join(', ')}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Services */}
        <div className="mb-8">
          <h2 className="text-base font-medium text-foreground mb-4">System Status</h2>
          {Object.entries(groupedServices).map(([groupName, services]) => (
            <div key={groupName} className="mb-4">
              {Object.keys(groupedServices).length > 1 && (
                <h3 className="text-xs uppercase tracking-wider text-muted-foreground mb-2">{groupName}</h3>
              )}
              <div className="bg-transparent border border-border rounded-xl divide-y divide-border">
                {services.map((service) => (
                  <div key={service.id} className="p-4 flex items-center justify-between">
                    <div>
                      <h4 className="text-sm font-medium text-foreground">{service.name}</h4>
                      {service.description && (
                        <p className="text-xs text-muted-foreground">{service.description}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${statusConfig[service.status].color === 'text-emerald-400' ? 'bg-emerald-400' : statusConfig[service.status].color === 'text-yellow-400' ? 'bg-yellow-400' : statusConfig[service.status].color === 'text-orange-400' ? 'bg-orange-400' : statusConfig[service.status].color === 'text-red-400' ? 'bg-red-400' : 'bg-blue-400'}`}></span>
                      {getServiceStatusIcon(service.status)}
                      <span className={`text-sm font-medium ${statusConfig[service.status].color}`}>
                        {statusConfig[service.status].label.replace('All Systems ', '').replace(' System', '')}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Past Incidents */}
        {data.past_incidents.length > 0 && (
          <div className="mb-8">
            <h2 className="text-base font-medium text-foreground mb-4">Past Incidents</h2>
            <div className="space-y-3">
              {data.past_incidents.map((incident) => (
                <div key={incident.id} className="bg-transparent border border-border rounded-xl p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="text-sm font-medium text-foreground">{incident.title}</h3>
                      {incident.description && (
                        <p className="text-sm text-muted-foreground mt-1">{incident.description}</p>
                      )}
                    </div>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400">
                      Resolved
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    {formatDate(incident.created_at)}
                    {incident.resolved_at && ` - Resolved ${formatRelativeTime(incident.resolved_at)}`}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Subscribe */}
        {data.allow_subscriptions && (
          <div className="bg-transparent border border-border rounded-xl p-6">
            <div className="flex items-center gap-2 mb-3">
              <div className="p-2 rounded-lg bg-blue-500/10">
                <Mail className="h-5 w-5 text-blue-400" />
              </div>
              <h2 className="text-base font-medium text-foreground">Subscribe to Updates</h2>
            </div>
            <p className="text-sm text-muted-foreground mb-4">
              Get notified when there are incidents or scheduled maintenance.
            </p>
            <form onSubmit={handleSubscribe} className="flex gap-3">
              <input
                type="email"
                value={subscribeEmail}
                onChange={(e) => setSubscribeEmail(e.target.value)}
                placeholder="you@example.com"
                required
                className="flex-1 bg-transparent border border-border rounded-lg px-4 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-white/20"
              />
              <button
                type="submit"
                disabled={subscribing}
                className="px-4 py-2 bg-primary text-primary-foreground font-medium rounded-lg hover:bg-white/90 transition-colors disabled:opacity-50 text-sm"
              >
                {subscribing ? 'Subscribing...' : 'Subscribe'}
              </button>
            </form>
            {subscribeMessage && (
              <p className={`mt-3 text-sm ${subscribeMessage.type === 'success' ? 'text-emerald-400' : 'text-red-400'}`}>
                {subscribeMessage.text}
              </p>
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-border bg-background mt-12">
        <div className="max-w-4xl mx-auto px-4 py-6">
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>Powered by OffCall AI</span>
            <div className="flex items-center gap-4">
              {data.support_url && (
                <a href={data.support_url} target="_blank" rel="noopener noreferrer" className="hover:text-foreground transition-colors">
                  Support
                </a>
              )}
              {data.support_email && (
                <a href={`mailto:${data.support_email}`} className="hover:text-foreground transition-colors">
                  Contact
                </a>
              )}
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default PublicStatusPage;
