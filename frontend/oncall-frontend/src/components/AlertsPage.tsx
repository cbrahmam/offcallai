// frontend/oncall-frontend/src/components/AlertsPage.tsx
import React, { useState, useEffect, useCallback } from 'react';
import {
  AlertTriangle,
  BellOff,
  CheckCircle,
  ChevronRight,
  Clock,
  Eye,
  Filter,
  RefreshCw,
  Search,
  Server,
  X,
  Zap
} from 'lucide-react';
import { Button } from './ui/button';
import { useNotifications } from '../contexts/NotificationContext';

import { API_URL as API_BASE_URL } from '../config/api';

interface Alert {
  id: string;
  title: string;
  description?: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  status: 'firing' | 'acknowledged' | 'resolved' | 'suppressed';
  source: string;
  service_name?: string;
  environment?: string;
  host?: string;
  incident_id?: string;
  started_at?: string;
  ended_at?: string;
  created_at: string;
  labels?: Record<string, string>;
}

interface AlertStats {
  total: number;
  firing: number;
  acknowledged: number;
  resolved: number;
  critical: number;
}

interface AlertsPageProps {
  onNavigateToAlert?: (alertId: string) => void;
  onNavigateToIncident?: (incidentId: string) => void;
}

const AlertsPage: React.FC<AlertsPageProps> = ({ onNavigateToAlert, onNavigateToIncident }) => {
  const { showToast } = useNotifications();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [stats, setStats] = useState<AlertStats>({
    total: 0,
    firing: 0,
    acknowledged: 0,
    resolved: 0,
    critical: 0,
  });
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  const fetchAlerts = useCallback(async () => {
    try {
      const token = localStorage.getItem('access_token');
      const params = new URLSearchParams({
        page: page.toString(),
        per_page: '20',
      });

      if (statusFilter !== 'all') {
        params.append('status', statusFilter);
      }
      if (severityFilter !== 'all') {
        params.append('severity', severityFilter);
      }

      const response = await fetch(`${API_BASE_URL}/alerts?${params}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch alerts');
      }

      const data = await response.json();
      setAlerts(data.alerts || []);
      setTotalPages(data.total_pages || 1);

      // Calculate stats
      const allAlerts = data.alerts || [];
      setStats({
        total: data.total || allAlerts.length,
        firing: allAlerts.filter((a: Alert) => a.status === 'firing').length,
        acknowledged: allAlerts.filter((a: Alert) => a.status === 'acknowledged').length,
        resolved: allAlerts.filter((a: Alert) => a.status === 'resolved').length,
        critical: allAlerts.filter((a: Alert) => a.severity === 'critical').length,
      });
    } catch (error) {
      console.error('Error fetching alerts:', error);
      setAlerts([]);
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, [page, statusFilter, severityFilter]);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await fetchAlerts();
    showToast({
      type: 'success',
      title: 'Refreshed',
      message: 'Alerts list has been updated',
      autoClose: true,
      duration: 2000,
    });
  };

  const handleAcknowledge = async (alertId: string) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/alerts/${alertId}/acknowledge`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to acknowledge alert');
      }

      showToast({
        type: 'success',
        title: 'Alert Acknowledged',
        message: 'Alert has been acknowledged',
        autoClose: true,
      });

      fetchAlerts();
    } catch (error) {
      console.error('Error acknowledging alert:', error);
      showToast({
        type: 'error',
        title: 'Error',
        message: 'Failed to acknowledge alert',
        autoClose: true,
      });
    }
  };

  const handleSuppress = async (alertId: string) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/alerts/${alertId}/suppress`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to suppress alert');
      }

      showToast({
        type: 'success',
        title: 'Alert Suppressed',
        message: 'Alert has been suppressed',
        autoClose: true,
      });

      fetchAlerts();
    } catch (error) {
      console.error('Error suppressing alert:', error);
      showToast({
        type: 'error',
        title: 'Error',
        message: 'Failed to suppress alert',
        autoClose: true,
      });
    }
  };

  const getSeverityVariant = (severity: string): "default" | "secondary" | "destructive" | "outline" | "success" | "warning" | "info" | "critical" => {
    switch (severity) {
      case 'critical': return 'critical';
      case 'high': return 'destructive';
      case 'medium': return 'warning';
      case 'low': return 'info';
      default: return 'secondary';
    }
  };

  const getStatusVariant = (status: string): "default" | "secondary" | "destructive" | "outline" | "success" | "warning" | "info" | "critical" => {
    switch (status) {
      case 'firing': return 'destructive';
      case 'acknowledged': return 'warning';
      case 'resolved': return 'success';
      case 'suppressed': return 'secondary';
      default: return 'secondary';
    }
  };

  const formatTime = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  const filteredAlerts = alerts.filter(alert => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      return (
        alert.title.toLowerCase().includes(query) ||
        (alert.description && alert.description.toLowerCase().includes(query)) ||
        (alert.service_name && alert.service_name.toLowerCase().includes(query)) ||
        (alert.host && alert.host.toLowerCase().includes(query))
      );
    }
    return true;
  });

  // Stats Card Component
  const StatCard = ({ title, value, icon: Icon, gradient, borderColor, textColor, onClick }: {
    title: string;
    value: number;
    icon: any;
    gradient: string;
    borderColor: string;
    textColor: string;
    onClick?: () => void;
  }) => (
    <div
      onClick={onClick}
      className="group relative overflow-hidden rounded-xl bg-transparent border border-border hover:bg-accent transition-all duration-300 cursor-pointer"
    >
      <div className="relative p-4">
        <div className="flex items-center justify-between mb-3">
          <div className={`p-2.5 rounded-xl ${textColor.replace('text-', 'bg-').replace('/80', '/10')}`}>
            <Icon className={`w-4 h-4 ${textColor.replace('/80', '')}`} />
          </div>
        </div>
        <p className="text-3xl font-bold text-foreground">{value}</p>
        <p className={`text-sm ${textColor} mt-1`}>{title}</p>
      </div>
    </div>
  );

  if (loading) {
    return (
      <div className="p-6">
        <div className="max-w-7xl mx-auto">
          <div className="animate-pulse space-y-6">
            <div className="h-8 bg-secondary rounded w-1/4" />
            <div className="grid grid-cols-4 gap-4">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="h-24 bg-secondary rounded-xl" />
              ))}
            </div>
            <div className="h-96 bg-secondary rounded-xl" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-orange-500/10">
                <Zap className="w-6 h-6 text-orange-400" />
              </div>
              <div>
                <h1 className="text-xl font-semibold text-foreground">Alerts</h1>
                <p className="text-muted-foreground text-sm">Monitor and manage all system alerts</p>
              </div>
            </div>
            <Button
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="bg-primary text-primary-foreground hover:bg-white/90"
            >
              <RefreshCw className={`w-5 h-5 ${isRefreshing ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* Stats Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            title="Total Alerts"
            value={stats.total}
            icon={Zap}
            gradient=""
            borderColor=""
            textColor="text-blue-400/80"
            onClick={() => { setStatusFilter('all'); setSeverityFilter('all'); }}
          />
          <StatCard
            title="Firing"
            value={stats.firing}
            icon={AlertTriangle}
            gradient=""
            borderColor=""
            textColor="text-red-400/80"
            onClick={() => setStatusFilter('firing')}
          />
          <StatCard
            title="Acknowledged"
            value={stats.acknowledged}
            icon={Clock}
            gradient=""
            borderColor=""
            textColor="text-yellow-400/80"
            onClick={() => setStatusFilter('acknowledged')}
          />
          <StatCard
            title="Critical"
            value={stats.critical}
            icon={AlertTriangle}
            gradient=""
            borderColor=""
            textColor="text-red-400/80"
            onClick={() => setSeverityFilter('critical')}
          />
        </div>

        {/* Filters */}
        <div className="bg-transparent border border-border rounded-xl">
          <div className="p-4">
            <div className="flex flex-col sm:flex-row sm:items-center gap-4">
              {/* Search */}
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search alerts..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 bg-accent border border-border rounded-lg text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary/30"
                />
              </div>

              {/* Status Filter */}
              <div className="flex items-center gap-2">
                <Filter className="w-4 h-4 text-muted-foreground" />
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="px-3 py-2 bg-accent border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
                >
                  <option value="all">All Status</option>
                  <option value="firing">Firing</option>
                  <option value="acknowledged">Acknowledged</option>
                  <option value="resolved">Resolved</option>
                  <option value="suppressed">Suppressed</option>
                </select>
              </div>

              {/* Severity Filter */}
              <select
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value)}
                className="px-3 py-2 bg-accent border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
              >
                <option value="all">All Severity</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
          </div>
        </div>

        {/* Alerts List */}
        <div className="bg-transparent border border-border rounded-xl">
          <div className="p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-orange-500/10">
                  <AlertTriangle className="w-4 h-4 text-orange-400" />
                </div>
                <span className="font-medium text-foreground text-base">Alert List</span>
              </div>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-secondary text-muted-foreground border-border">
                {filteredAlerts.length} alert{filteredAlerts.length !== 1 ? 's' : ''}
              </span>
            </div>
          </div>
          <div className="px-6 pb-6">
            {filteredAlerts.length === 0 ? (
              <div className="text-center py-12">
                <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-4" />
                <h3 className="text-base font-medium text-foreground mb-2">No alerts</h3>
                <p className="text-muted-foreground text-sm">
                  {searchQuery || statusFilter !== 'all' || severityFilter !== 'all'
                    ? 'No alerts match your filters'
                    : 'All systems are operating normally'}
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {filteredAlerts.map((alert) => (
                  <div
                    key={alert.id}
                    className={`p-4 rounded-lg border transition-all cursor-pointer hover:bg-accent ${
                      alert.status === 'firing' ? 'border-red-500/20 bg-red-500/5' :
                      alert.status === 'acknowledged' ? 'border-yellow-500/20 bg-yellow-500/5' :
                      'border-border bg-transparent'
                    }`}
                    onClick={() => setSelectedAlert(selectedAlert?.id === alert.id ? null : alert)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${
                            alert.severity === 'critical' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                            alert.severity === 'high' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                            alert.severity === 'medium' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                            'bg-blue-500/10 text-blue-400 border-blue-500/20'
                          }`}>
                            {alert.severity.toUpperCase()}
                          </span>
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${
                            alert.status === 'firing' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                            alert.status === 'acknowledged' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                            'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                          }`}>
                            {alert.status.toUpperCase()}
                          </span>
                          <span className="text-xs text-muted-foreground">{alert.source}</span>
                        </div>
                        <h4 className="font-medium text-foreground text-sm mb-1">{alert.title}</h4>
                        {alert.description && (
                          <p className="text-sm text-muted-foreground mb-2 line-clamp-2">
                            {alert.description}
                          </p>
                        )}
                        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                          {alert.service_name && (
                            <span className="flex items-center gap-2">
                              <Server className="w-3 h-3" />
                              {alert.service_name}
                            </span>
                          )}
                          {alert.host && (
                            <span>{alert.host}</span>
                          )}
                          {alert.environment && (
                            <span className="px-1.5 py-0.5 bg-secondary rounded text-xs">
                              {alert.environment}
                            </span>
                          )}
                          <span>{formatTime(alert.created_at)}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 ml-4">
                        {alert.status === 'firing' && (
                          <>
                            <Button
                              size="sm"
                              variant="outline"
                              className="border-border text-foreground hover:bg-accent"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleAcknowledge(alert.id);
                              }}
                            >
                              <CheckCircle className="w-4 h-4 mr-1" />
                              Ack
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="text-muted-foreground hover:bg-accent"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleSuppress(alert.id);
                              }}
                            >
                              <BellOff className="w-4 h-4" />
                            </Button>
                          </>
                        )}
                        <ChevronRight className={`w-5 h-5 text-muted-foreground transition-transform ${
                          selectedAlert?.id === alert.id ? 'rotate-90' : ''
                        }`} />
                      </div>
                    </div>

                    {/* Expanded Details */}
                    {selectedAlert?.id === alert.id && (
                      <div className="mt-4 pt-4 border-t border-border">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                          <div>
                            <p className="text-xs uppercase tracking-wider text-muted-foreground">Started</p>
                            <p className="text-sm text-foreground">
                              {alert.started_at ? new Date(alert.started_at).toLocaleString() : new Date(alert.created_at).toLocaleString()}
                            </p>
                          </div>
                          {alert.ended_at && (
                            <div>
                              <p className="text-xs uppercase tracking-wider text-muted-foreground">Ended</p>
                              <p className="text-sm text-foreground">
                                {new Date(alert.ended_at).toLocaleString()}
                              </p>
                            </div>
                          )}
                          <div>
                            <p className="text-xs uppercase tracking-wider text-muted-foreground">Source</p>
                            <p className="text-sm text-foreground">{alert.source}</p>
                          </div>
                          {alert.incident_id && (
                            <div>
                              <p className="text-xs uppercase tracking-wider text-muted-foreground">Linked Incident</p>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  onNavigateToIncident?.(alert.incident_id!);
                                }}
                                className="text-sm text-muted-foreground hover:text-foreground"
                              >
                                View Incident
                              </button>
                            </div>
                          )}
                        </div>

                        {alert.labels && Object.keys(alert.labels).length > 0 && (
                          <div>
                            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-2">Labels</p>
                            <div className="flex flex-wrap gap-2">
                              {Object.entries(alert.labels).map(([key, value]) => (
                                <span
                                  key={key}
                                  className="px-2 py-1 bg-secondary rounded text-xs text-foreground"
                                >
                                  {key}: {value}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        <div className="flex gap-2 mt-4">
                          <Button
                            size="sm"
                            className="bg-primary text-primary-foreground hover:bg-white/90"
                            onClick={(e) => {
                              e.stopPropagation();
                              onNavigateToAlert?.(alert.id);
                            }}
                          >
                            <Eye className="w-4 h-4 mr-1" />
                            View Details
                          </Button>
                          {!alert.incident_id && alert.status === 'firing' && (
                            <Button
                              size="sm"
                              variant="outline"
                              className="border-border text-foreground hover:bg-accent"
                              onClick={(e) => {
                                e.stopPropagation();
                                showToast({
                                  type: 'info',
                                  title: 'Coming Soon',
                                  message: 'Create incident from alert feature coming soon',
                                  autoClose: true,
                                });
                              }}
                            >
                              Create Incident
                            </Button>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-6 pt-4 border-t border-border">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === 1}
                  onClick={() => setPage(p => p - 1)}
                  className="border-border text-foreground hover:bg-accent"
                >
                  Previous
                </Button>
                <span className="text-sm text-muted-foreground">
                  Page {page} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === totalPages}
                  onClick={() => setPage(p => p + 1)}
                  className="border-border text-foreground hover:bg-accent"
                >
                  Next
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AlertsPage;
