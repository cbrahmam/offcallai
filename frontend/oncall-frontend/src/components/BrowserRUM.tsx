// frontend/oncall-frontend/src/components/BrowserRUM.tsx
import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  CheckCircle,
  Chrome,
  Clock,
  Code,
  Copy,
  Eye,
  FileText,
  Gauge,
  Globe,
  Key,
  Monitor,
  MousePointer,
  MoveVertical,
  Plus,
  RefreshCw,
  Search,
  Settings,
  Smartphone,
  Tablet,
  Timer,
  Trash2,
  TrendingDown,
  TrendingUp,
  Users,
  XCircle,
  Zap
} from 'lucide-react';

import { API_URL as API_BASE } from '../config/api';

interface RUMApplication {
  id: string;
  name: string;
  description?: string;
  domain?: string;
  api_key: string;
  enabled: boolean;
  sample_rate: number;
  track_errors: boolean;
  track_performance: boolean;
  track_user_actions: boolean;
  error_rate_threshold: number;
  lcp_threshold_ms: number;
  fid_threshold_ms: number;
  cls_threshold: number;
  created_at: string;
}

interface RUMSession {
  id: string;
  session_id: string;
  user_id?: string;
  session_start: string;
  session_end?: string;
  duration_ms?: number;
  page_views: number;
  interactions: number;
  errors_count: number;
  browser_name?: string;
  os_name?: string;
  device_type?: string;
  country?: string;
  entry_url?: string;
  is_bounce: boolean;
}

interface RUMPageView {
  id: string;
  url: string;
  url_path?: string;
  page_title?: string;
  timestamp: string;
  lcp_ms?: number;
  fid_ms?: number;
  cls?: number;
  fcp_ms?: number;
  ttfb_ms?: number;
  load_event_ms?: number;
  resource_count: number;
  js_errors_count: number;
}

interface RUMError {
  id: string;
  error_type: string;
  error_name?: string;
  message: string;
  stack_trace?: string;
  filename?: string;
  line_number?: number;
  url?: string;
  fingerprint?: string;
  timestamp: string;
  is_handled: boolean;
}

interface RUMAlert {
  id: string;
  alert_type: string;
  severity: string;
  status: string;
  title: string;
  message?: string;
  metric_value?: number;
  threshold_value?: number;
  triggered_at: string;
}

interface CoreWebVitals {
  lcp_p50_ms: number;
  lcp_p75_ms: number;
  lcp_p90_ms: number;
  fid_p50_ms: number;
  fid_p75_ms: number;
  fid_p90_ms: number;
  cls_p50: number;
  cls_p75: number;
  cls_p90: number;
  fcp_p50_ms: number;
  fcp_p75_ms: number;
  ttfb_p50_ms: number;
  ttfb_p75_ms: number;
}

interface RUMStats {
  total_sessions: number;
  active_sessions: number;
  total_page_views: number;
  total_errors: number;
  error_rate_percent: number;
  unique_users: number;
  avg_session_duration_ms: number;
  bounce_rate_percent: number;
  avg_page_views_per_session: number;
  core_web_vitals: CoreWebVitals;
  top_pages: any[];
  top_errors: any[];
  browser_breakdown: Record<string, number>;
  device_breakdown: Record<string, number>;
}

type TabType = 'overview' | 'applications' | 'sessions' | 'pageviews' | 'errors' | 'vitals' | 'alerts';

export default function BrowserRUM() {
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [applications, setApplications] = useState<RUMApplication[]>([]);
  const [selectedApp, setSelectedApp] = useState<RUMApplication | null>(null);
  const [sessions, setSessions] = useState<RUMSession[]>([]);
  const [pageViews, setPageViews] = useState<RUMPageView[]>([]);
  const [errors, setErrors] = useState<RUMError[]>([]);
  const [alerts, setAlerts] = useState<RUMAlert[]>([]);
  const [stats, setStats] = useState<RUMStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showApiKeyModal, setShowApiKeyModal] = useState(false);
  const [copiedKey, setCopiedKey] = useState(false);

  const getAuthHeaders = useCallback(() => {
    const token = localStorage.getItem('access_token');
    return {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    };
  }, []);

  const fetchApplications = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/rum/applications`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        const fetchedApps = data.items || [];
        setApplications(fetchedApps);
        if (fetchedApps.length > 0 && !selectedApp) {
          setSelectedApp(fetchedApps[0]);
        }
      } else {
        setApplications([]);
      }
    } catch (error) {
      console.error('Failed to fetch applications:', error);
      setApplications([]);
    }
  }, [getAuthHeaders, selectedApp]);

  const fetchStats = useCallback(async (appId: string) => {
    try {
      const response = await fetch(`${API_BASE}/rum/applications/${appId}/stats?hours=24`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setStats(data && data.total_sessions !== undefined ? data : null);
      } else {
        setStats(null);
      }
    } catch (error) {
      console.error('Failed to fetch stats:', error);
      setStats(null);
    }
  }, [getAuthHeaders]);

  const fetchSessions = useCallback(async (appId: string) => {
    try {
      const response = await fetch(`${API_BASE}/rum/applications/${appId}/sessions?page_size=50`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setSessions(data.items || []);
      } else {
        setSessions([]);
      }
    } catch (error) {
      console.error('Failed to fetch sessions:', error);
      setSessions([]);
    }
  }, [getAuthHeaders]);

  const fetchPageViews = useCallback(async (appId: string) => {
    try {
      const response = await fetch(`${API_BASE}/rum/applications/${appId}/pageviews?page_size=50`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setPageViews(data.items || []);
      } else {
        setPageViews([]);
      }
    } catch (error) {
      console.error('Failed to fetch page views:', error);
      setPageViews([]);
    }
  }, [getAuthHeaders]);

  const fetchErrors = useCallback(async (appId: string) => {
    try {
      const response = await fetch(`${API_BASE}/rum/applications/${appId}/errors?page_size=50`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setErrors(data.items || []);
      } else {
        setErrors([]);
      }
    } catch (error) {
      console.error('Failed to fetch errors:', error);
      setErrors([]);
    }
  }, [getAuthHeaders]);

  const fetchAlerts = useCallback(async (appId: string) => {
    try {
      const response = await fetch(`${API_BASE}/rum/applications/${appId}/alerts?status=active`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setAlerts(data.items || []);
      } else {
        setAlerts([]);
      }
    } catch (error) {
      console.error('Failed to fetch alerts:', error);
      setAlerts([]);
    }
  }, [getAuthHeaders]);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await fetchApplications();
      setLoading(false);
    };
    loadData();
  }, [fetchApplications]);

  useEffect(() => {
    if (selectedApp) {
      fetchStats(selectedApp.id);
      fetchAlerts(selectedApp.id);
    }
  }, [selectedApp, fetchStats, fetchAlerts]);

  useEffect(() => {
    if (selectedApp) {
      if (activeTab === 'sessions') fetchSessions(selectedApp.id);
      if (activeTab === 'pageviews') fetchPageViews(selectedApp.id);
      if (activeTab === 'errors') fetchErrors(selectedApp.id);
    }
  }, [activeTab, selectedApp, fetchSessions, fetchPageViews, fetchErrors]);

  const copyApiKey = (key: string) => {
    navigator.clipboard.writeText(key);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2000);
  };

  const deleteApplication = async (appId: string) => {
    if (!window.confirm('Are you sure you want to delete this application?')) return;
    try {
      await fetch(`${API_BASE}/rum/applications/${appId}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });
      fetchApplications();
      if (selectedApp?.id === appId) {
        setSelectedApp(null);
      }
    } catch (error) {
      console.error('Failed to delete application:', error);
    }
  };

  const getDeviceIcon = (type?: string) => {
    switch (type) {
      case 'mobile': return Smartphone;
      case 'tablet': return Tablet;
      default: return Monitor;
    }
  };

  const getVitalStatus = (value: number, good: number, poor: number) => {
    if (value <= good) return 'good';
    if (value <= poor) return 'needs-improvement';
    return 'poor';
  };

  const getVitalColor = (status: string) => {
    switch (status) {
      case 'good': return 'text-green-400';
      case 'needs-improvement': return 'text-yellow-400';
      case 'poor': return 'text-red-400';
      default: return 'text-muted-foreground';
    }
  };

  const getVitalBg = (status: string) => {
    switch (status) {
      case 'good': return 'bg-green-500/20';
      case 'needs-improvement': return 'bg-yellow-500/20';
      case 'poor': return 'bg-red-500/20';
      default: return 'bg-secondary';
    }
  };

  const formatDuration = (ms?: number) => {
    if (!ms) return '-';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  const formatSessionDuration = (ms?: number) => {
    if (!ms) return '-';
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    if (minutes > 0) return `${minutes}m ${remainingSeconds}s`;
    return `${seconds}s`;
  };

  const tabs = [
    { id: 'overview' as TabType, label: 'Overview', icon: BarChart3 },
    { id: 'applications' as TabType, label: 'Applications', icon: Globe },
    { id: 'sessions' as TabType, label: 'Sessions', icon: Users },
    { id: 'pageviews' as TabType, label: 'Page Views', icon: FileText },
    { id: 'errors' as TabType, label: 'Errors', icon: AlertTriangle },
    { id: 'vitals' as TabType, label: 'Web Vitals', icon: Gauge },
    { id: 'alerts' as TabType, label: 'Alerts', icon: AlertTriangle },
  ];

  const renderOverview = () => {
    if (!stats) {
      return (
        <div className="text-center py-12 text-muted-foreground">
          <Globe className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>Select an application to view overview</p>
        </div>
      );
    }

    return (
      <div className="space-y-6">
        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-muted/50 rounded-xl p-4 border border-border/50">
            <div className="flex items-center gap-3 mb-2">
              <Users className="w-5 h-5 text-blue-400" />
              <span className="text-muted-foreground text-sm">Total Sessions</span>
            </div>
            <div className="text-2xl font-bold text-foreground">{stats.total_sessions.toLocaleString()}</div>
            <div className="text-xs text-green-400 mt-2">
              {stats.active_sessions} active now
            </div>
          </div>

          <div className="bg-muted/50 rounded-xl p-4 border border-border/50">
            <div className="flex items-center gap-3 mb-2">
              <FileText className="w-5 h-5 text-purple-400" />
              <span className="text-muted-foreground text-sm">Page Views</span>
            </div>
            <div className="text-2xl font-bold text-foreground">{stats.total_page_views.toLocaleString()}</div>
            <div className="text-xs text-muted-foreground mt-2">
              {stats.avg_page_views_per_session.toFixed(1)} per session
            </div>
          </div>

          <div className="bg-muted/50 rounded-xl p-4 border border-border/50">
            <div className="flex items-center gap-3 mb-2">
              <AlertTriangle className="w-5 h-5 text-red-400" />
              <span className="text-muted-foreground text-sm">Errors</span>
            </div>
            <div className="text-2xl font-bold text-foreground">{stats.total_errors.toLocaleString()}</div>
            <div className={`text-xs mt-2 ${stats.error_rate_percent > 5 ? 'text-red-400' : 'text-green-400'}`}>
              {stats.error_rate_percent.toFixed(2)}% error rate
            </div>
          </div>

          <div className="bg-muted/50 rounded-xl p-4 border border-border/50">
            <div className="flex items-center gap-3 mb-2">
              <ArrowUpRight className="w-5 h-5 text-yellow-400" />
              <span className="text-muted-foreground text-sm">Bounce Rate</span>
            </div>
            <div className="text-2xl font-bold text-foreground">{stats.bounce_rate_percent.toFixed(1)}%</div>
            <div className="text-xs text-muted-foreground mt-2">
              Avg session: {formatSessionDuration(stats.avg_session_duration_ms)}
            </div>
          </div>
        </div>

        {/* Core Web Vitals Summary */}
        <div className="bg-card border border-border rounded-lg p-4">
          <h3 className="text-lg font-semibold mb-4">Core Web Vitals (p75)</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* LCP */}
            <div className="p-4 bg-muted/30 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Timer className="h-4 w-4" />
                  <span className="text-sm font-medium">LCP</span>
                </div>
                <span className="text-xs text-muted-foreground">Largest Contentful Paint</span>
              </div>
              <div className={`text-2xl font-bold ${getVitalColor(getVitalStatus(stats.core_web_vitals.lcp_p75_ms, 2500, 4000))}`}>
                {formatDuration(stats.core_web_vitals.lcp_p75_ms)}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                Good: &lt;2.5s | Poor: &gt;4s
              </div>
            </div>

            {/* FID */}
            <div className="p-4 bg-muted/30 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <MousePointer className="h-4 w-4" />
                  <span className="text-sm font-medium">FID</span>
                </div>
                <span className="text-xs text-muted-foreground">First Input Delay</span>
              </div>
              <div className={`text-2xl font-bold ${getVitalColor(getVitalStatus(stats.core_web_vitals.fid_p75_ms, 100, 300))}`}>
                {formatDuration(stats.core_web_vitals.fid_p75_ms)}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                Good: &lt;100ms | Poor: &gt;300ms
              </div>
            </div>

            {/* CLS */}
            <div className="p-4 bg-muted/30 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <MoveVertical className="h-4 w-4" />
                  <span className="text-sm font-medium">CLS</span>
                </div>
                <span className="text-xs text-muted-foreground">Cumulative Layout Shift</span>
              </div>
              <div className={`text-2xl font-bold ${getVitalColor(getVitalStatus(stats.core_web_vitals.cls_p75, 0.1, 0.25))}`}>
                {stats.core_web_vitals.cls_p75.toFixed(3)}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                Good: &lt;0.1 | Poor: &gt;0.25
              </div>
            </div>
          </div>
        </div>

        {/* Top Pages & Browser Breakdown */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-card border border-border rounded-lg p-4">
            <h3 className="text-lg font-semibold mb-4">Top Pages</h3>
            <div className="space-y-2">
              {stats.top_pages.slice(0, 5).map((page, index) => (
                <div key={index} className="flex items-center justify-between p-2 bg-muted/30 rounded">
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <span className="text-muted-foreground">#{index + 1}</span>
                    <span className="truncate">{page.url_path || '/'}</span>
                  </div>
                  <div className="text-right ml-2">
                    <div className="font-medium">{page.views?.toLocaleString()}</div>
                    <div className="text-xs text-muted-foreground">{formatDuration(page.avg_load_time_ms)}</div>
                  </div>
                </div>
              ))}
              {stats.top_pages.length === 0 && (
                <div className="text-center text-muted-foreground py-4">No data available</div>
              )}
            </div>
          </div>

          <div className="bg-card border border-border rounded-lg p-4">
            <h3 className="text-lg font-semibold mb-4">Browser Breakdown</h3>
            <div className="space-y-2">
              {Object.entries(stats.browser_breakdown).slice(0, 5).map(([browser, count]) => {
                const total = Object.values(stats.browser_breakdown).reduce((a, b) => a + b, 0);
                const percent = total > 0 ? (count / total * 100) : 0;
                return (
                  <div key={browser} className="flex items-center gap-3">
                    <Chrome className="h-4 w-4 text-blue-400" />
                    <div className="flex-1">
                      <div className="flex justify-between mb-1">
                        <span>{browser}</span>
                        <span className="text-muted-foreground">{percent.toFixed(1)}%</span>
                      </div>
                      <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                        <div
                          className="h-full bg-blue-500 rounded-full"
                          style={{ width: `${percent}%` }}
                        />
                      </div>
                    </div>
                  </div>
                );
              })}
              {Object.keys(stats.browser_breakdown).length === 0 && (
                <div className="text-center text-muted-foreground py-4">No data available</div>
              )}
            </div>
          </div>
        </div>

        {/* Device Breakdown */}
        <div className="bg-card border border-border rounded-lg p-4">
          <h3 className="text-lg font-semibold mb-4">Device Breakdown</h3>
          <div className="grid grid-cols-3 gap-4">
            {Object.entries(stats.device_breakdown).map(([device, count]) => {
              const total = Object.values(stats.device_breakdown).reduce((a, b) => a + b, 0);
              const percent = total > 0 ? (count / total * 100) : 0;
              const Icon = getDeviceIcon(device);
              return (
                <div key={device} className="text-center p-4 bg-muted/30 rounded-lg">
                  <Icon className="h-8 w-8 mx-auto mb-2 text-blue-400" />
                  <div className="font-medium capitalize">{device}</div>
                  <div className="text-2xl font-bold">{percent.toFixed(1)}%</div>
                  <div className="text-xs text-muted-foreground">{count.toLocaleString()} sessions</div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    );
  };

  const renderApplications = () => (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-foreground rounded-lg hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" />
          Add Application
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {applications.map((app) => (
          <div
            key={app.id}
            className={`bg-card border rounded-lg p-4 cursor-pointer transition-colors ${
              selectedApp?.id === app.id ? 'border-blue-500' : 'border-border hover:border-blue-500/50'
            }`}
            onClick={() => setSelectedApp(app)}
          >
            <div className="flex items-start justify-between mb-3">
              <div>
                <div className="font-semibold">{app.name}</div>
                <div className="text-sm text-muted-foreground">{app.domain || 'No domain set'}</div>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedApp(app);
                    setShowApiKeyModal(true);
                  }}
                  className="p-1.5 text-muted-foreground hover:text-foreground rounded"
                  title="View API Key"
                >
                  <Key className="h-4 w-4" />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteApplication(app.id);
                  }}
                  className="p-1.5 text-muted-foreground hover:text-red-400 rounded"
                  title="Delete"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>

            <div className="flex items-center gap-2 mb-3">
              <span className={`px-2 py-1 rounded-full text-xs ${
                app.enabled ? 'bg-green-500/20 text-green-400' : 'bg-secondary text-muted-foreground'
              }`}>
                {app.enabled ? 'Active' : 'Disabled'}
              </span>
              <span className="text-xs text-muted-foreground">
                {app.sample_rate}% sampling
              </span>
            </div>

            <div className="grid grid-cols-3 gap-2 text-center text-xs">
              <div className={`p-2 rounded ${app.track_errors ? 'bg-green-500/10 text-green-400' : 'bg-muted/30 text-muted-foreground'}`}>
                Errors
              </div>
              <div className={`p-2 rounded ${app.track_performance ? 'bg-green-500/10 text-green-400' : 'bg-muted/30 text-muted-foreground'}`}>
                Perf
              </div>
              <div className={`p-2 rounded ${app.track_user_actions ? 'bg-green-500/10 text-green-400' : 'bg-muted/30 text-muted-foreground'}`}>
                Actions
              </div>
            </div>
          </div>
        ))}
      </div>

      {applications.length === 0 && !loading && (
        <div className="text-center py-12 text-muted-foreground">
          <Globe className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>No RUM applications configured</p>
          <p className="text-sm mt-1">Add an application to start monitoring</p>
        </div>
      )}
    </div>
  );

  const renderSessions = () => (
    <div className="space-y-4">
      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <table className="w-full">
          <thead className="bg-muted/50">
            <tr>
              <th className="text-left px-4 py-3 text-sm font-medium">Session</th>
              <th className="text-left px-4 py-3 text-sm font-medium">User</th>
              <th className="text-left px-4 py-3 text-sm font-medium">Device</th>
              <th className="text-left px-4 py-3 text-sm font-medium">Location</th>
              <th className="text-center px-4 py-3 text-sm font-medium">Pages</th>
              <th className="text-center px-4 py-3 text-sm font-medium">Errors</th>
              <th className="text-right px-4 py-3 text-sm font-medium">Duration</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {sessions.map((session) => {
              const DeviceIcon = getDeviceIcon(session.device_type);
              return (
                <tr key={session.id} className="hover:bg-muted/30">
                  <td className="px-4 py-3">
                    <div className="text-sm font-mono">{session.session_id.substring(0, 8)}...</div>
                    <div className="text-xs text-muted-foreground">
                      {new Date(session.session_start).toLocaleString()}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {session.user_id || <span className="text-muted-foreground">Anonymous</span>}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <DeviceIcon className="h-4 w-4 text-muted-foreground" />
                      <div>
                        <div className="text-sm">{session.browser_name || 'Unknown'}</div>
                        <div className="text-xs text-muted-foreground">{session.os_name}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm">{session.country || '-'}</td>
                  <td className="px-4 py-3 text-center">
                    <span className="font-medium">{session.page_views}</span>
                    {session.is_bounce && (
                      <span className="ml-1 text-xs text-yellow-400">(bounce)</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {session.errors_count > 0 ? (
                      <span className="text-red-400 font-medium">{session.errors_count}</span>
                    ) : (
                      <span className="text-green-400">0</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right text-sm">
                    {formatSessionDuration(session.duration_ms)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {sessions.length === 0 && (
          <div className="text-center py-8 text-muted-foreground">
            No sessions recorded yet
          </div>
        )}
      </div>
    </div>
  );

  const renderErrors = () => (
    <div className="space-y-4">
      <div className="space-y-3">
        {errors.map((error) => (
          <div key={error.id} className="bg-card border border-border rounded-lg p-4">
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-3">
                <div className={`p-2 rounded-lg ${error.is_handled ? 'bg-yellow-500/20' : 'bg-red-500/20'}`}>
                  <AlertTriangle className={`h-5 w-5 ${error.is_handled ? 'text-yellow-400' : 'text-red-400'}`} />
                </div>
                <div>
                  <div className="font-semibold">
                    {error.error_name || error.error_type}
                  </div>
                  <div className="text-sm text-muted-foreground mt-1">{error.message}</div>
                  {error.filename && (
                    <div className="text-xs text-muted-foreground mt-2 font-mono">
                      {error.filename}:{error.line_number}
                    </div>
                  )}
                  <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                    <span>{error.url}</span>
                    <span>{new Date(error.timestamp).toLocaleString()}</span>
                    <span className={error.is_handled ? 'text-yellow-400' : 'text-red-400'}>
                      {error.is_handled ? 'Handled' : 'Unhandled'}
                    </span>
                  </div>
                </div>
              </div>
              <span className="text-xs font-mono text-muted-foreground">
                {error.fingerprint?.substring(0, 8)}
              </span>
            </div>
            {error.stack_trace && (
              <details className="mt-3">
                <summary className="text-xs text-blue-400 cursor-pointer">View Stack Trace</summary>
                <pre className="mt-2 p-3 bg-muted/50 rounded text-xs overflow-auto max-h-48">
                  {error.stack_trace}
                </pre>
              </details>
            )}
          </div>
        ))}
        {errors.length === 0 && (
          <div className="text-center py-12 text-muted-foreground">
            <CheckCircle className="h-12 w-12 mx-auto mb-4 text-green-400 opacity-50" />
            <p>No errors recorded</p>
            <p className="text-sm mt-1">Your application is running smoothly</p>
          </div>
        )}
      </div>
    </div>
  );

  const renderVitals = () => {
    if (!stats) {
      return (
        <div className="text-center py-12 text-muted-foreground">
          Select an application to view Core Web Vitals
        </div>
      );
    }

    const vitals = stats.core_web_vitals;

    return (
      <div className="space-y-6">
        {/* LCP */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <Timer className="h-6 w-6 text-blue-400" />
            <div>
              <h3 className="text-lg font-semibold">Largest Contentful Paint (LCP)</h3>
              <p className="text-sm text-muted-foreground">
                Measures loading performance. Should occur within 2.5 seconds.
              </p>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: 'p50', value: vitals.lcp_p50_ms, good: 2500, poor: 4000 },
              { label: 'p75', value: vitals.lcp_p75_ms, good: 2500, poor: 4000 },
              { label: 'p90', value: vitals.lcp_p90_ms, good: 2500, poor: 4000 },
            ].map((item) => {
              const status = getVitalStatus(item.value, item.good, item.poor);
              return (
                <div key={item.label} className={`p-4 rounded-lg ${getVitalBg(status)}`}>
                  <div className="text-xs text-muted-foreground mb-1">{item.label}</div>
                  <div className={`text-2xl font-bold ${getVitalColor(status)}`}>
                    {formatDuration(item.value)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* FID */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <MousePointer className="h-6 w-6 text-purple-400" />
            <div>
              <h3 className="text-lg font-semibold">First Input Delay (FID)</h3>
              <p className="text-sm text-muted-foreground">
                Measures interactivity. Should be less than 100 milliseconds.
              </p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            {[
              { label: 'p50', value: vitals.fid_p50_ms, good: 100, poor: 300 },
              { label: 'p75', value: vitals.fid_p75_ms, good: 100, poor: 300 },
            ].map((item) => {
              const status = getVitalStatus(item.value, item.good, item.poor);
              return (
                <div key={item.label} className={`p-4 rounded-lg ${getVitalBg(status)}`}>
                  <div className="text-xs text-muted-foreground mb-1">{item.label}</div>
                  <div className={`text-2xl font-bold ${getVitalColor(status)}`}>
                    {formatDuration(item.value)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* CLS */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <MoveVertical className="h-6 w-6 text-yellow-400" />
            <div>
              <h3 className="text-lg font-semibold">Cumulative Layout Shift (CLS)</h3>
              <p className="text-sm text-muted-foreground">
                Measures visual stability. Should be less than 0.1.
              </p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            {[
              { label: 'p50', value: vitals.cls_p50, good: 0.1, poor: 0.25 },
              { label: 'p75', value: vitals.cls_p75, good: 0.1, poor: 0.25 },
            ].map((item) => {
              const status = getVitalStatus(item.value, item.good, item.poor);
              return (
                <div key={item.label} className={`p-4 rounded-lg ${getVitalBg(status)}`}>
                  <div className="text-xs text-muted-foreground mb-1">{item.label}</div>
                  <div className={`text-2xl font-bold ${getVitalColor(status)}`}>
                    {item.value.toFixed(3)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Additional Metrics */}
        <div className="bg-card border border-border rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4">Additional Metrics</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 bg-muted/30 rounded-lg">
              <div className="text-xs text-muted-foreground mb-1">FCP (p75)</div>
              <div className="text-xl font-bold">{formatDuration(vitals.fcp_p75_ms)}</div>
              <div className="text-xs text-muted-foreground">First Contentful Paint</div>
            </div>
            <div className="p-4 bg-muted/30 rounded-lg">
              <div className="text-xs text-muted-foreground mb-1">TTFB (p75)</div>
              <div className="text-xl font-bold">{formatDuration(vitals.ttfb_p75_ms)}</div>
              <div className="text-xs text-muted-foreground">Time to First Byte</div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderAlerts = () => (
    <div className="space-y-3">
      {alerts.map((alert) => (
        <div key={alert.id} className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-3">
              <div className={`p-2 rounded-lg ${
                alert.severity === 'critical' ? 'bg-red-500/20' : 'bg-yellow-500/20'
              }`}>
                <AlertTriangle className={`h-5 w-5 ${
                  alert.severity === 'critical' ? 'text-red-400' : 'text-yellow-400'
                }`} />
              </div>
              <div>
                <div className="font-semibold">{alert.title}</div>
                {alert.message && (
                  <div className="text-sm text-muted-foreground mt-1">{alert.message}</div>
                )}
                <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                  <span>Type: {alert.alert_type}</span>
                  {alert.metric_value && (
                    <span>
                      Value: {alert.metric_value.toFixed(2)}
                      {alert.threshold_value && ` (threshold: ${alert.threshold_value})`}
                    </span>
                  )}
                  <span>{new Date(alert.triggered_at).toLocaleString()}</span>
                </div>
              </div>
            </div>
            <span className={`px-2 py-1 rounded-full text-xs ${
              alert.severity === 'critical' ? 'bg-red-500/20 text-red-400' : 'bg-yellow-500/20 text-yellow-400'
            }`}>
              {alert.severity}
            </span>
          </div>
        </div>
      ))}
      {alerts.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          <CheckCircle className="h-12 w-12 mx-auto mb-4 text-green-400 opacity-50" />
          <p>No active alerts</p>
        </div>
      )}
    </div>
  );

  // Create Application Modal
  const CreateModal = () => {
    const [formData, setFormData] = useState({
      name: '',
      description: '',
      domain: '',
      sample_rate: 100,
      track_errors: true,
      track_performance: true,
      track_user_actions: true,
    });
    const [creating, setCreating] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
      e.preventDefault();
      setCreating(true);
      try {
        const response = await fetch(`${API_BASE}/rum/applications`, {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify(formData),
        });
        if (response.ok) {
          setShowCreateModal(false);
          fetchApplications();
        }
      } catch (error) {
        console.error('Failed to create application:', error);
      }
      setCreating(false);
    };

    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
        <div className="bg-card border border-border rounded-lg w-full max-w-lg">
          <div className="p-4 border-b border-border">
            <h2 className="text-lg font-semibold">Add RUM Application</h2>
          </div>
          <form onSubmit={handleSubmit} className="p-4 space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Application Name *</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 bg-muted border border-border rounded-lg"
                placeholder="My Web App"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Domain</label>
              <input
                type="text"
                value={formData.domain}
                onChange={(e) => setFormData({ ...formData, domain: e.target.value })}
                className="w-full px-3 py-2 bg-muted border border-border rounded-lg"
                placeholder="example.com"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Description</label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={2}
                className="w-full px-3 py-2 bg-muted border border-border rounded-lg"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Sample Rate (%)</label>
              <input
                type="number"
                value={formData.sample_rate}
                onChange={(e) => setFormData({ ...formData, sample_rate: parseFloat(e.target.value) })}
                min={1}
                max={100}
                className="w-full px-3 py-2 bg-muted border border-border rounded-lg"
              />
            </div>
            <div className="space-y-2">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={formData.track_errors}
                  onChange={(e) => setFormData({ ...formData, track_errors: e.target.checked })}
                  className="rounded"
                />
                <span className="text-sm">Track JavaScript Errors</span>
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={formData.track_performance}
                  onChange={(e) => setFormData({ ...formData, track_performance: e.target.checked })}
                  className="rounded"
                />
                <span className="text-sm">Track Performance (Core Web Vitals)</span>
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={formData.track_user_actions}
                  onChange={(e) => setFormData({ ...formData, track_user_actions: e.target.checked })}
                  className="rounded"
                />
                <span className="text-sm">Track User Actions</span>
              </label>
            </div>
            <div className="flex justify-end gap-3 pt-4 border-t border-border">
              <button
                type="button"
                onClick={() => setShowCreateModal(false)}
                className="px-4 py-2 text-muted-foreground hover:text-foreground"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={creating || !formData.name}
                className="px-4 py-2 bg-blue-600 text-foreground rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {creating ? 'Creating...' : 'Create Application'}
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  };

  // API Key Modal
  const ApiKeyModal = () => {
    if (!selectedApp) return null;

    const selfOrigin = API_BASE.replace(/\/api\/v1\/?$/, '');
    const sdkSnippet = `<script src="${selfOrigin}/offcall-rum.js"></script>
<script>
  OffCallRUM.init({
    apiKey: '${selectedApp.api_key}',
    appName: '${selectedApp.name}',
    endpoint: '${API_BASE}/rum/ingest/batch',
    environment: 'production',
    sampleRate: 1.0,
    trackErrors: true,
    trackPerformance: true,
    trackActions: true
  });
</script>`;

    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
        <div className="bg-card border border-border rounded-lg w-full max-w-2xl">
          <div className="p-4 border-b border-border">
            <h2 className="text-lg font-semibold">Integration Instructions</h2>
          </div>
          <div className="p-4 space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">API Key</label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={selectedApp.api_key}
                  readOnly
                  className="flex-1 px-3 py-2 bg-muted border border-border rounded-lg font-mono text-sm"
                />
                <button
                  onClick={() => copyApiKey(selectedApp.api_key)}
                  className="px-3 py-2 bg-blue-600 text-foreground rounded-lg hover:bg-blue-700"
                >
                  {copiedKey ? <CheckCircle className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Installation</label>
              <p className="text-sm text-muted-foreground mb-2">
                Add the following script to your HTML, just before the closing &lt;/head&gt; tag:
              </p>
              <div className="relative">
                <pre className="p-4 bg-muted rounded-lg text-xs overflow-auto">
                  {sdkSnippet}
                </pre>
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(sdkSnippet);
                    setCopiedKey(true);
                    setTimeout(() => setCopiedKey(false), 2000);
                  }}
                  className="absolute top-2 right-2 p-2 bg-card border border-border rounded hover:bg-muted"
                >
                  <Copy className="h-4 w-4" />
                </button>
              </div>
            </div>

            <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4">
              <h4 className="font-medium text-blue-400 mb-2">What gets tracked</h4>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>- Page views and navigation timing</li>
                <li>- Core Web Vitals (LCP, FID, CLS)</li>
                <li>- JavaScript errors and stack traces</li>
                <li>- User interactions (clicks, inputs)</li>
                <li>- Session information and user journey</li>
              </ul>
            </div>
          </div>
          <div className="p-4 border-t border-border flex justify-end">
            <button
              onClick={() => setShowApiKeyModal(false)}
              className="px-4 py-2 bg-muted hover:bg-muted/80 rounded-lg"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background">
        {/* Colorful Header */}
        <div className="relative overflow-hidden border-b border-border">

          <div className="relative max-w-7xl mx-auto px-6 py-6">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className="p-3 rounded-xl bg-blue-500/10">
                  <Globe className="w-6 h-6 text-blue-400" />
                </div>
                <div>
                  <h1 className="text-xl font-semibold text-foreground">Browser RUM</h1>
                  <p className="text-muted-foreground text-sm">Real User Monitoring - Track user experience, errors, and Core Web Vitals</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
          <div className="flex items-center justify-center h-64">
            <RefreshCw className="h-8 w-8 animate-spin text-blue-500" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Colorful Header */}
      <div className="relative overflow-hidden border-b border-border">

        <div className="relative max-w-7xl mx-auto px-6 py-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-cyan-500/10">
                <Globe className="w-6 h-6 text-cyan-400" />
              </div>
              <div>
                <h1 className="text-base font-medium text-foreground">Browser RUM</h1>
                <p className="text-muted-foreground text-sm">Real User Monitoring - Track user experience, errors, and Core Web Vitals</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              {applications.length > 0 && (
                <select
                  value={selectedApp?.id || ''}
                  onChange={(e) => {
                    const app = applications.find(a => a.id === e.target.value);
                    setSelectedApp(app || null);
                  }}
                  className="px-3 py-2 bg-muted border border-border rounded-lg"
                >
                  {applications.map((app) => (
                    <option key={app.id} value={app.id}>{app.name}</option>
                  ))}
                </select>
              )}
              <button
                onClick={() => selectedApp && fetchStats(selectedApp.id)}
                className="flex items-center gap-2 px-4 py-2 bg-muted hover:bg-muted/80 rounded-lg"
              >
                <RefreshCw className="h-4 w-4" />
                Refresh
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-border overflow-x-auto">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 border-b-2 transition-colors whitespace-nowrap ${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-500'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && renderOverview()}
      {activeTab === 'applications' && renderApplications()}
      {activeTab === 'sessions' && renderSessions()}
      {activeTab === 'pageviews' && (
        <div className="text-center py-12 text-muted-foreground">
          Page views data coming from SDK integration
        </div>
      )}
      {activeTab === 'errors' && renderErrors()}
      {activeTab === 'vitals' && renderVitals()}
        {activeTab === 'alerts' && renderAlerts()}
      </div>

      {/* Modals */}
      {showCreateModal && <CreateModal />}
      {showApiKeyModal && <ApiKeyModal />}
    </div>
  );
}
