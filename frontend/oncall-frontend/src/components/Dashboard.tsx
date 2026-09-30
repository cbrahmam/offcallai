// Dashboard.tsx - Monitoring-first platform dashboard
import React, { useState, useEffect, useCallback } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Bell,
  Calendar,
  CheckCircle,
  Cpu,
  Database,
  Eye,
  FileText,
  Filter,
  Flame,
  Globe,
  Link,
  Plus,
  Radio,
  RefreshCw,
  Search,
  Server,
  Settings,
  ShieldCheck,
  Sparkles,
  Terminal,
  Users,
  X,
  Zap
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useNotifications } from '../contexts/NotificationContext';
import CurrentOnCallWidget from './CurrentOnCallWidget';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Select } from './ui/select';
import { Label } from './ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';

import { API_URL as API_BASE_URL } from '../config/api';

interface Host {
  id: string;
  hostname: string;
  status: 'online' | 'offline' | 'degraded';
  cpu_percent?: number;
  memory_percent?: number;
  last_seen_at?: string;
}

interface Alert {
  id: string;
  title: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  status: 'firing' | 'acknowledged' | 'resolved';
  source: string;
  created_at: string;
}

interface Incident {
  id: string;
  title: string;
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  status: 'open' | 'acknowledged' | 'resolved';
  assigned_to: string | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

interface LogStats {
  total_logs: number;
  by_level: Array<{ level: string; count: number }>;
}

interface MonitoringStats {
  hosts: { total: number; online: number; offline: number; degraded: number };
  alerts: { total: number; firing: number; acknowledged: number; critical: number };
  incidents: { total: number; open: number; critical: number };
  logs: { total: number; errors: number; warnings: number };
  metrics: { avgCpu: number; avgMemory: number; avgLatency: number; errorRate: number };
}

interface DashboardProps {
  onNavigateToIncident?: (id: string) => void;
  onShowAIAnalysis?: (incidentId: string, analysisData: any) => void;
  isDemoMode?: boolean;
}

// Empty state for when no data is available
const EMPTY_MONITORING_STATS: MonitoringStats = {
  hosts: { total: 0, online: 0, offline: 0, degraded: 0 },
  alerts: { total: 0, firing: 0, acknowledged: 0, critical: 0 },
  incidents: { total: 0, open: 0, critical: 0 },
  logs: { total: 0, errors: 0, warnings: 0 },
  metrics: { avgCpu: 0, avgMemory: 0, avgLatency: 0, errorRate: 0 }
};

const Dashboard: React.FC<DashboardProps> = ({ onNavigateToIncident, onShowAIAnalysis, isDemoMode = false }) => {
  const { user, logout } = useAuth();
  const { showToast } = useNotifications();

  // Start with empty state - data will be loaded from API
  const [stats, setStats] = useState<MonitoringStats>(EMPTY_MONITORING_STATS);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [hosts, setHosts] = useState<Host[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const hasFetchedRef = React.useRef(false);

  const loadDashboardData = useCallback(async () => {
    try {
      const token = localStorage.getItem('access_token');
      if (!token) {
        setLoading(false);
        return;
      }

      const headers: Record<string, string> = token
        ? { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }
        : { 'Content-Type': 'application/json' };

      // Helper to add timeout to fetch requests
      const fetchWithTimeout = (url: string, options: RequestInit, timeout = 5000) => {
        return Promise.race([
          fetch(url, options),
          new Promise<Response>((_, reject) =>
            setTimeout(() => reject(new Error('Request timeout')), timeout)
          )
        ]);
      };

      // Fetch all data in parallel with timeouts
      const [hostsRes, alertsRes, incidentsRes, logStatsRes] = await Promise.allSettled([
        fetchWithTimeout(`${API_BASE_URL}/hosts/`, { headers }, 5000),
        fetchWithTimeout(`${API_BASE_URL}/alerts/?limit=10`, { headers }, 5000),
        fetchWithTimeout(`${API_BASE_URL}/incidents/`, { headers }, 5000),
        fetchWithTimeout(`${API_BASE_URL}/logs/stats?hours=1`, { headers }, 3000), // Reduced to 1 hour for faster load
      ]);

      // Process hosts
      if (hostsRes.status === 'fulfilled' && hostsRes.value.ok) {
        const hostsData = await hostsRes.value.json();
        const hostList = hostsData.hosts || [];
        setHosts(hostList);

        const online = hostList.filter((h: Host) => h.status === 'online').length;
        const offline = hostList.filter((h: Host) => h.status === 'offline').length;
        const degraded = hostList.filter((h: Host) => h.status === 'degraded').length;

        const avgCpu = hostList.length > 0
          ? hostList.reduce((acc: number, h: Host) => acc + (h.cpu_percent || 0), 0) / hostList.length
          : 0;
        const avgMemory = hostList.length > 0
          ? hostList.reduce((acc: number, h: Host) => acc + (h.memory_percent || 0), 0) / hostList.length
          : 0;

        setStats(prev => ({
          ...prev,
          hosts: { total: hostList.length, online, offline, degraded },
          metrics: { ...prev.metrics, avgCpu, avgMemory }
        }));
      }

      // Process alerts
      if (alertsRes.status === 'fulfilled' && alertsRes.value.ok) {
        const alertsData = await alertsRes.value.json();
        const alertList = alertsData.alerts || [];
        setAlerts(alertList);

        const firing = alertList.filter((a: Alert) => a.status === 'firing').length;
        const acknowledged = alertList.filter((a: Alert) => a.status === 'acknowledged').length;
        const critical = alertList.filter((a: Alert) => a.severity === 'critical' && a.status === 'firing').length;

        setStats(prev => ({
          ...prev,
          alerts: { total: alertList.length, firing, acknowledged, critical }
        }));
      }

      // Process incidents
      if (incidentsRes.status === 'fulfilled' && incidentsRes.value.ok) {
        const incidentsData = await incidentsRes.value.json();
        const incidentList = incidentsData.incidents || [];
        setIncidents(incidentList.slice(0, 5));

        const open = incidentList.filter((i: Incident) => i.status !== 'resolved').length;
        const criticalIncidents = incidentList.filter((i: Incident) => i.severity === 'critical' && i.status !== 'resolved').length;

        setStats(prev => ({
          ...prev,
          incidents: { total: incidentList.length, open, critical: criticalIncidents }
        }));
      } else if (incidentsRes.status === 'fulfilled' && incidentsRes.value.status === 401) {
        logout();
        return;
      }

      // Process log stats
      if (logStatsRes.status === 'fulfilled' && logStatsRes.value.ok) {
        const logData: LogStats = await logStatsRes.value.json();
        const errors = logData.by_level?.find(l => l.level.toLowerCase() === 'error')?.count || 0;
        const warnings = logData.by_level?.find(l => l.level.toLowerCase() === 'warn')?.count || 0;

        setStats(prev => ({
          ...prev,
          logs: { total: logData.total_logs, errors, warnings }
        }));
      }

    } catch (error) {
      console.error('Error loading dashboard data:', error);
    } finally {
      setLoading(false);
    }
  }, [logout]);

  useEffect(() => {
    if (hasFetchedRef.current) return;
    hasFetchedRef.current = true;
    loadDashboardData();
    const interval = setInterval(loadDashboardData, 30000);
    return () => clearInterval(interval);
  }, [loadDashboardData]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await loadDashboardData();
    setIsRefreshing(false);
    showToast({
      type: 'success',
      title: 'Refreshed',
      message: 'Dashboard data has been updated',
      autoClose: true,
      duration: 2000
    });
  };

  const createIncident = async (incidentData: {title: string, description: string, severity: string}) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/incidents/`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(incidentData),
      });
      if (response.ok) {
        setShowCreateModal(false);
        showToast({ type: 'success', title: 'Incident Created', message: `Incident "${incidentData.title}" has been created`, autoClose: true });
        await loadDashboardData();
      }
    } catch (error) {
      console.error('Error creating incident:', error);
      showToast({ type: 'error', title: 'Error', message: 'Failed to create incident', autoClose: true });
    }
  };

  const getTimeAgo = (dateString: string): string => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  };

  // Status colors
  const severityColors = {
    critical: 'bg-red-500/10 text-red-400 border-red-500/20',
    high: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
    medium: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    low: 'bg-blue-500/10 text-blue-400 border-blue-500/20'
  };

  const hostStatusColors = {
    online: 'bg-emerald-500',
    offline: 'bg-red-500',
    degraded: 'bg-yellow-500'
  };

  // Create Incident Modal
  const CreateIncidentModal = () => {
    const [formData, setFormData] = useState({ title: '', description: '', severity: 'medium' });
    const handleSubmit = (e: React.FormEvent) => {
      e.preventDefault();
      if (formData.title.trim()) {
        createIncident(formData);
        setFormData({ title: '', description: '', severity: 'medium' });
      }
    };
    return (
      <Dialog open={showCreateModal} onOpenChange={setShowCreateModal}>
        <DialogContent onClose={() => setShowCreateModal(false)} className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-secondary">
                <Plus className="w-5 h-5 text-foreground" />
              </div>
              Create New Incident
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title">Title *</Label>
              <Input
                id="title"
                value={formData.title}
                onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
                placeholder="Brief description of the issue"
                required
                className="bg-accent"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                rows={3}
                placeholder="Detailed description of the incident"
                className="bg-accent"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="severity">Severity</Label>
              <Select
                id="severity"
                value={formData.severity}
                onChange={(e) => setFormData(prev => ({ ...prev, severity: e.target.value }))}
                className="bg-accent"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </Select>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowCreateModal(false)}>Cancel</Button>
              <Button type="submit" className="bg-primary text-primary-foreground hover:bg-white/90">
                Create Incident
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    );
  };

  const currentHour = new Date().getHours();
  const greeting = currentHour < 12 ? 'Good morning' : currentHour < 18 ? 'Good afternoon' : 'Good evening';

  // Determine overall system health
  const getSystemHealth = () => {
    if (stats.alerts.critical > 0 || stats.hosts.offline > 0) {
      return { status: 'Critical', color: 'text-red-400', bgColor: 'bg-red-500', pulse: true };
    }
    if (stats.alerts.firing > 2 || stats.hosts.degraded > 0) {
      return { status: 'Degraded', color: 'text-yellow-400', bgColor: 'bg-yellow-500', pulse: true };
    }
    return { status: 'Healthy', color: 'text-emerald-400', bgColor: 'bg-emerald-500', pulse: false };
  };

  const systemHealth = getSystemHealth();

  if (loading) {
    return (
      <div className="min-h-screen bg-background p-6">
        <div className="max-w-7xl mx-auto">
          <div className="space-y-6">
            <div className="h-24 bg-accent rounded-xl relative overflow-hidden">
              <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-white/5 to-transparent" />
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="h-28 bg-accent rounded-xl relative overflow-hidden">
                  <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-white/5 to-transparent" style={{ animationDelay: `${i * 100}ms` }} />
                </div>
              ))}
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {[...Array(3)].map((_, i) => (
                <div key={i} className={`h-64 bg-accent rounded-xl relative overflow-hidden ${i === 0 ? 'lg:col-span-2' : ''}`}>
                  <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-white/5 to-transparent" style={{ animationDelay: `${i * 150}ms` }} />
                </div>
              ))}
            </div>
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
            <div>
              <p className="text-muted-foreground font-medium mb-1 text-sm">{greeting}</p>
              <h1 className="text-base font-medium text-foreground mb-1">
                Monitoring Overview
              </h1>
              <p className="text-muted-foreground text-sm">
                Real-time status of your infrastructure and services
              </p>
            </div>
            <div className="flex items-center gap-3">
              {/* System Health Badge */}
              <div className={`flex items-center gap-2 px-4 py-2 rounded-xl border transition-all ${
                systemHealth.status === 'Critical' ? 'bg-red-500/10 border-red-500/20' :
                systemHealth.status === 'Degraded' ? 'bg-yellow-500/10 border-yellow-500/20' :
                'bg-emerald-500/10 border-emerald-500/20'
              }`}>
                <span className={`h-2.5 w-2.5 rounded-full ${
                  systemHealth.status === 'Critical' ? 'bg-red-500' : systemHealth.status === 'Degraded' ? 'bg-yellow-500' : 'bg-emerald-500'
                } inline-block`} />
                <span className={`text-sm font-medium ${systemHealth.color}`}>System {systemHealth.status}</span>
              </div>
              <Button
                onClick={handleRefresh}
                disabled={isRefreshing}
                variant="outline"
                size="sm"
                className="border-border hover:bg-accent"
              >
                <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
              </Button>
              <Button
                onClick={() => setShowCreateModal(true)}
                size="sm"
                className="bg-primary text-primary-foreground hover:bg-white/90"
              >
                <Plus className="w-4 h-4" />
                New Incident
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6">
        {/* Key Metrics Row */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
          {/* Hosts */}
          <div
            onClick={() => window.location.href = '/infrastructure'}
            className="p-4 rounded-xl bg-transparent border border-border hover:bg-accent cursor-pointer transition-all group"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 rounded-lg bg-blue-500/10">
                <Server className="w-4 h-4 text-blue-400" />
              </div>
              <ArrowRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
            <p className="text-2xl font-bold text-foreground">{stats.hosts.online}/{stats.hosts.total}</p>
            <p className="text-xs text-muted-foreground">Hosts Online</p>
            {stats.hosts.offline > 0 && (
              <p className="text-xs text-red-400 mt-1 font-medium">{stats.hosts.offline} offline</p>
            )}
          </div>

          {/* Active Alerts */}
          <div
            onClick={() => window.location.href = '/alerts'}
            className="p-4 rounded-xl bg-transparent border border-border hover:bg-accent cursor-pointer transition-all group"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 rounded-lg bg-orange-500/10">
                <Bell className="w-4 h-4 text-orange-400" />
              </div>
              <ArrowRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
            <p className="text-2xl font-bold text-foreground">{stats.alerts.firing}</p>
            <p className="text-xs text-muted-foreground">Active Alerts</p>
            {stats.alerts.critical > 0 && (
              <p className="text-xs text-red-400 mt-1 font-medium">{stats.alerts.critical} critical</p>
            )}
          </div>

          {/* Open Incidents */}
          <div
            onClick={() => window.location.href = '/dashboard?filter=open'}
            className="p-4 rounded-xl bg-transparent border border-border hover:bg-accent cursor-pointer transition-all group"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 rounded-lg bg-red-500/10">
                <Flame className="w-4 h-4 text-red-400" />
              </div>
              <ArrowRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
            <p className="text-2xl font-bold text-foreground">{stats.incidents.open}</p>
            <p className="text-xs text-muted-foreground">Open Incidents</p>
            {stats.incidents.critical > 0 && (
              <p className="text-xs text-red-400 mt-1 font-medium">{stats.incidents.critical} critical</p>
            )}
          </div>

          {/* Error Rate */}
          <div
            onClick={() => window.location.href = '/logs'}
            className="p-4 rounded-xl bg-transparent border border-border hover:bg-accent cursor-pointer transition-all group"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 rounded-lg bg-purple-500/10">
                <Terminal className="w-4 h-4 text-purple-400" />
              </div>
              <ArrowRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
            <p className="text-2xl font-bold text-foreground">{stats.logs.errors}</p>
            <p className="text-xs text-muted-foreground">Log Errors (24h)</p>
            {stats.logs.warnings > 0 && (
              <p className="text-xs text-yellow-400 mt-1 font-medium">{stats.logs.warnings} warnings</p>
            )}
          </div>

          {/* Avg CPU */}
          <div
            onClick={() => window.location.href = '/infrastructure'}
            className="p-4 rounded-xl bg-transparent border border-border hover:bg-accent cursor-pointer transition-all group"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 rounded-lg bg-cyan-500/10">
                <Cpu className="w-4 h-4 text-cyan-400" />
              </div>
              <ArrowRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
            <p className="text-2xl font-bold text-foreground">{stats.metrics.avgCpu.toFixed(1)}%</p>
            <p className="text-xs text-muted-foreground">Avg CPU</p>
            {stats.metrics.avgCpu > 80 && (
              <p className="text-xs text-orange-400 mt-1 font-medium">High load</p>
            )}
          </div>

          {/* Avg Memory */}
          <div
            onClick={() => window.location.href = '/infrastructure'}
            className="p-4 rounded-xl bg-transparent border border-border hover:bg-accent cursor-pointer transition-all group"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 rounded-lg bg-emerald-500/10">
                <Database className="w-4 h-4 text-emerald-400" />
              </div>
              <ArrowRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
            <p className="text-2xl font-bold text-foreground">{stats.metrics.avgMemory.toFixed(1)}%</p>
            <p className="text-xs text-muted-foreground">Avg Memory</p>
            {stats.metrics.avgMemory > 85 && (
              <p className="text-xs text-orange-400 mt-1 font-medium">High usage</p>
            )}
          </div>
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Alerts & Incidents */}
          <div className="lg:col-span-2 space-y-6">
            {/* Active Alerts */}
            <div className="bg-transparent border border-border rounded-xl">
              <div className="flex flex-row items-center justify-between p-6 pb-3">
                <h3 className="font-medium flex items-center gap-3 text-base">
                  <div className="p-2 rounded-xl bg-orange-500/10">
                    <Bell className="w-5 h-5 text-orange-400" />
                  </div>
                  <span className="text-foreground">Active Alerts</span>
                  {stats.alerts.firing > 0 && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-yellow-500/10 text-yellow-400 border-yellow-500/20">
                      {stats.alerts.firing}
                    </span>
                  )}
                </h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => window.location.href = '/alerts'}
                  className="text-muted-foreground hover:text-foreground hover:bg-accent"
                >
                  View All
                  <ArrowRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
              <div className="p-6 pt-0">
                {alerts.filter(a => a.status !== 'resolved').length === 0 ? (
                  <div className="text-center py-8">
                    <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-3 opacity-50" />
                    <p className="text-muted-foreground">No active alerts</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {alerts.filter(a => a.status !== 'resolved').slice(0, 5).map((alert) => (
                      <div
                        key={alert.id}
                        onClick={() => window.location.href = `/alerts/${alert.id}`}
                        className="flex items-center justify-between p-3 rounded-lg bg-transparent border border-border hover:bg-accent cursor-pointer transition-all"
                      >
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                          <div className={`p-1.5 rounded ${severityColors[alert.severity]}`}>
                            {alert.severity === 'critical' ? <Flame className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium text-foreground truncate">{alert.title}</p>
                            <p className="text-xs text-muted-foreground">{alert.source} • {getTimeAgo(alert.created_at)}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-0.5 text-xs rounded-full border ${severityColors[alert.severity]}`}>
                            {alert.severity}
                          </span>
                          {alert.status === 'acknowledged' && (
                            <span className="px-2 py-0.5 text-xs rounded-full bg-yellow-500/10 text-yellow-400 border border-yellow-500/20">
                              ACK
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Recent Incidents */}
            <div className="bg-transparent border border-border rounded-xl">
              <div className="flex flex-row items-center justify-between p-6 pb-3">
                <h3 className="font-medium flex items-center gap-3 text-base">
                  <div className="p-2 rounded-xl bg-red-500/10">
                    <Flame className="w-5 h-5 text-red-400" />
                  </div>
                  <span className="text-foreground">Recent Incidents</span>
                  {stats.incidents.open > 0 && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-red-500/10 text-red-400 border-red-500/20">
                      {stats.incidents.open} open
                    </span>
                  )}
                </h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => window.location.href = '/incidents'}
                  className="text-muted-foreground hover:text-foreground hover:bg-accent"
                >
                  View All
                  <ArrowRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
              <div className="p-6 pt-0">
                {incidents.length === 0 ? (
                  <div className="text-center py-8">
                    <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-3 opacity-50" />
                    <p className="text-muted-foreground">No recent incidents</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {incidents.slice(0, 4).map((incident) => (
                      <div
                        key={incident.id}
                        onClick={() => onNavigateToIncident?.(incident.id)}
                        className="flex items-center justify-between p-3 rounded-lg bg-transparent border border-border hover:bg-accent cursor-pointer transition-all"
                      >
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                          <div className={`p-1.5 rounded ${severityColors[incident.severity]}`}>
                            {incident.severity === 'critical' ? <Flame className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium text-foreground truncate">{incident.title}</p>
                            <p className="text-xs text-muted-foreground">
                              {incident.assigned_to || 'Unassigned'} • {getTimeAgo(incident.created_at)}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-0.5 text-xs rounded-full border ${
                            incident.status === 'resolved' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
                            incident.status === 'acknowledged' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                            'bg-red-500/10 text-red-400 border-red-500/20'
                          }`}>
                            {incident.status}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right Column */}
          <div className="space-y-6">
            {/* Host Status */}
            <div className="bg-transparent border border-border rounded-xl">
              <div className="flex flex-row items-center justify-between p-6 pb-3">
                <h3 className="font-medium flex items-center gap-3 text-base">
                  <div className="p-2 rounded-xl bg-blue-500/10">
                    <Server className="w-5 h-5 text-blue-400" />
                  </div>
                  <span className="text-foreground">Infrastructure</span>
                </h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => window.location.href = '/infrastructure'}
                  className="text-muted-foreground hover:text-foreground hover:bg-accent"
                >
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </div>
              <div className="p-6 pt-0">
                <div className="space-y-2">
                  {hosts.slice(0, 6).map((host) => (
                    <div
                      key={host.id}
                      onClick={() => window.location.href = `/hosts/${host.id}`}
                      className="flex items-center justify-between p-2 rounded-lg hover:bg-accent cursor-pointer transition-all"
                    >
                      <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full ${hostStatusColors[host.status]}`} />
                        <span className="text-sm text-foreground truncate max-w-[120px]">{host.hostname}</span>
                      </div>
                      <div className="flex items-center gap-3 text-xs text-muted-foreground">
                        <span>{host.cpu_percent || 0}%</span>
                        <span>{host.memory_percent || 0}%</span>
                      </div>
                    </div>
                  ))}
                </div>
                {hosts.length > 6 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => window.location.href = '/infrastructure'}
                    className="w-full mt-3 text-muted-foreground hover:text-foreground"
                  >
                    View all {hosts.length} hosts
                  </Button>
                )}
              </div>
            </div>

            {/* On-Call Widget */}
            <CurrentOnCallWidget onManageSchedules={() => window.location.href = '/on-call-schedules'} />

            {/* Quick Links */}
            <div className="bg-transparent border border-border rounded-xl">
              <div className="p-6 pb-3">
                <h3 className="font-medium flex items-center gap-3 text-base">
                  <div className="p-2 rounded-xl bg-cyan-500/10">
                    <Link className="w-5 h-5 text-cyan-400" />
                  </div>
                  <span className="text-foreground">Quick Links</span>
                </h3>
              </div>
              <div className="p-6 pt-0">
                <div className="grid grid-cols-2 gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => window.location.href = '/logs'}
                    className="justify-start items-center gap-2 border-border hover:bg-accent text-foreground"
                  >
                    <Terminal className="w-4 h-4 text-muted-foreground" />
                    Logs
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => window.location.href = '/apm'}
                    className="justify-start items-center gap-2 border-border hover:bg-accent text-foreground"
                  >
                    <Radio className="w-4 h-4 text-muted-foreground" />
                    APM
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => window.location.href = '/runbooks'}
                    className="justify-start items-center gap-2 border-border hover:bg-accent text-foreground"
                  >
                    <FileText className="w-4 h-4 text-muted-foreground" />
                    Runbooks
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => window.location.href = '/alert-rules'}
                    className="justify-start items-center gap-2 border-border hover:bg-accent text-foreground"
                  >
                    <Settings className="w-4 h-4 text-muted-foreground" />
                    Alert Rules
                  </Button>
                </div>
              </div>
            </div>

            {/* AI Insights Card */}
            <div className="bg-transparent border border-border rounded-xl">
              <div className="p-5">
                <div className="flex items-center gap-3 mb-3">
                  <div className="p-2 rounded-xl bg-secondary">
                    <Sparkles className="w-5 h-5 text-foreground" />
                  </div>
                  <div>
                    <h3 className="font-medium text-foreground text-sm">AI-Powered Insights</h3>
                    <p className="text-xs text-muted-foreground">BYOK enabled</p>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground mb-3">
                  Get instant RCA and recommendations powered by Claude and Gemini.
                </p>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => window.location.href = '/settings'}
                  className="w-full text-muted-foreground hover:text-foreground hover:bg-accent border border-border"
                >
                  Configure AI Keys
                  <ArrowRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Create Incident Modal */}
      <CreateIncidentModal />
    </div>
  );
};

export default Dashboard;
