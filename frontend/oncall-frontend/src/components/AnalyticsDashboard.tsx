// AnalyticsDashboard.tsx - Refactored with shadcn/ui
import React, { useState, useEffect, useCallback } from 'react';
import {
  AlertTriangle,
  BarChart3,
  BellRing,
  CheckCircle,
  Clock,
  Download,
  RefreshCw,
  TrendingDown,
  TrendingUp,
  Users
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { Button } from './ui/button';
import { Select } from './ui/select';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from './ui/table';

import { API_URL as API_BASE_URL } from '../config/api';

interface OverviewMetrics {
  total_incidents: number;
  open_incidents: number;
  resolved_incidents: number;
  mttr_minutes: number | null;
  mtta_minutes: number | null;
  period_days: number;
  incident_change_pct: number;
  previous_period_incidents: number;
}

interface SeverityData {
  severity: string;
  count: number;
}

interface StatusData {
  status: string;
  count: number;
}

interface TrendData {
  date: string;
  total: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
}

interface ResponderData {
  user_id: string;
  name: string;
  email: string;
  incidents_handled: number;
  resolved: number;
  avg_resolution_minutes: number | null;
}

interface HourlyData {
  hour: number;
  count: number;
}

interface DayOfWeekData {
  day: string;
  day_number: number;
  count: number;
}

interface AlertSourceData {
  source: string;
  count: number;
}

interface AlertOverview {
  total_alerts: number;
  active_alerts: number;
  resolved_alerts: number;
  alert_change_pct: number;
  previous_period_alerts: number;
  period_days: number;
}

interface AlertTrendData {
  date: string;
  total: number;
  critical: number;
  high: number;
  warning: number;
  error: number;
}

interface AlertSeverityData {
  severity: string;
  count: number;
}

const severityColors: Record<string, string> = {
  critical: '#dc2626',
  high: '#f97316',
  medium: '#eab308',
  low: '#22c55e'
};

const statusColors: Record<string, string> = {
  open: '#dc2626',
  acknowledged: '#f97316',
  resolved: '#22c55e',
  closed: '#6b7280'
};

const AnalyticsDashboard: React.FC = () => {
  const { token } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);

  const [overview, setOverview] = useState<OverviewMetrics | null>(null);
  const [bySeverity, setBySeverity] = useState<SeverityData[]>([]);
  const [byStatus, setByStatus] = useState<StatusData[]>([]);
  const [trend, setTrend] = useState<TrendData[]>([]);
  const [responders, setResponders] = useState<ResponderData[]>([]);
  const [hourlyDistribution, setHourlyDistribution] = useState<HourlyData[]>([]);
  const [dayOfWeek, setDayOfWeek] = useState<DayOfWeekData[]>([]);
  const [alertSources, setAlertSources] = useState<AlertSourceData[]>([]);
  const [alertOverview, setAlertOverview] = useState<AlertOverview | null>(null);
  const [alertTrend, setAlertTrend] = useState<AlertTrendData[]>([]);
  const [alertsBySeverity, setAlertsBySeverity] = useState<AlertSeverityData[]>([]);

  const loadAnalytics = useCallback(async () => {
    if (!token) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/analytics/full?days=${days}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) throw new Error('Failed to fetch analytics');

      const data = await response.json();
      setOverview(data.overview);
      setBySeverity(data.by_severity);
      setByStatus(data.by_status);
      setTrend(data.trend);
      setResponders(data.responders);
      setHourlyDistribution(data.hourly_distribution);
      setDayOfWeek(data.day_of_week);
      setAlertSources(data.alert_sources);
      if (data.alert_overview) setAlertOverview(data.alert_overview);
      if (data.alert_trend) setAlertTrend(data.alert_trend);
      if (data.alerts_by_severity) setAlertsBySeverity(data.alerts_by_severity);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token, days]);

  useEffect(() => {
    loadAnalytics();
  }, [loadAnalytics]);

  const handleExport = async () => {
    if (!token) return;

    try {
      const response = await fetch(`${API_BASE_URL}/analytics/export?days=${days}&format=csv`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `analytics_${days}d.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export failed:', err);
    }
  };

  const formatMinutes = (minutes: number | null): string => {
    if (minutes === null || minutes === undefined) return '-';
    if (minutes < 60) return `${Math.round(minutes)}m`;
    const hours = Math.floor(minutes / 60);
    const mins = Math.round(minutes % 60);
    return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
  };

  const getMaxCount = (data: { count: number }[]): number => {
    return Math.max(...data.map(d => d.count), 1);
  };

  const BarChart: React.FC<{ data: { label: string; value: number; color: string }[]; maxValue: number }> = ({ data, maxValue }) => (
    <div className="space-y-3">
      {data.map((item, idx) => (
        <div key={idx} className="flex items-center gap-3">
          <div className="w-20 text-sm text-muted-foreground truncate">{item.label}</div>
          <div className="flex-1 bg-secondary rounded-full h-5 overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${(item.value / maxValue) * 100}%`,
                backgroundColor: item.color
              }}
            />
          </div>
          <div className="w-10 text-sm font-medium text-foreground text-right">{item.value}</div>
        </div>
      ))}
    </div>
  );

  const TrendChart: React.FC<{ data: TrendData[] }> = ({ data }) => {
    if (data.length === 0) return <div className="text-muted-foreground text-center py-8">No data available</div>;

    const maxTotal = Math.max(...data.map(d => d.total), 1);
    const chartHeight = 200;

    return (
      <div className="relative h-[200px]">
        <div className="absolute inset-0 flex items-end justify-between gap-1 px-2">
          {data.map((point, idx) => (
            <div
              key={idx}
              className="flex-1 flex flex-col items-stretch gap-0.5"
              title={`${point.date?.split('T')[0] || 'N/A'}: ${point.total} incidents`}
            >
              {point.critical > 0 && (
                <div
                  style={{ height: `${(point.critical / maxTotal) * chartHeight}px`, backgroundColor: severityColors.critical }}
                  className="rounded-t"
                />
              )}
              {point.high > 0 && (
                <div
                  style={{ height: `${(point.high / maxTotal) * chartHeight}px`, backgroundColor: severityColors.high }}
                />
              )}
              {point.medium > 0 && (
                <div
                  style={{ height: `${(point.medium / maxTotal) * chartHeight}px`, backgroundColor: severityColors.medium }}
                />
              )}
              {point.low > 0 && (
                <div
                  style={{ height: `${(point.low / maxTotal) * chartHeight}px`, backgroundColor: severityColors.low }}
                  className="rounded-b"
                />
              )}
            </div>
          ))}
        </div>
        <div className="absolute bottom-0 left-0 right-0 flex justify-between text-xs text-muted-foreground pt-2 border-t border-border">
          <span>{data[0]?.date?.split('T')[0] || ''}</span>
          <span>{data[data.length - 1]?.date?.split('T')[0] || ''}</span>
        </div>
      </div>
    );
  };

  const HourlyHeatmap: React.FC<{ data: HourlyData[] }> = ({ data }) => {
    const maxCount = getMaxCount(data);

    return (
      <div className="grid grid-cols-12 gap-1">
        {data.map((h) => {
          const intensity = h.count / maxCount;
          const bgColor = `rgba(59, 130, 246, ${0.2 + intensity * 0.8})`;
          return (
            <div
              key={h.hour}
              className="aspect-square rounded flex items-center justify-center text-xs font-medium"
              style={{ backgroundColor: bgColor, color: intensity > 0.3 ? 'white' : 'var(--muted-foreground)' }}
              title={`${h.hour}:00 - ${h.count} incidents`}
            >
              {h.hour}
            </div>
          );
        })}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background">
        {/* Header */}
        <div className="border-b border-border">
          <div className="max-w-7xl mx-auto px-6 py-6">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className="p-2 rounded-lg bg-secondary">
                  <BarChart3 className="w-5 h-5 text-muted-foreground" />
                </div>
                <div>
                  <h1 className="text-base font-medium text-foreground">Analytics Dashboard</h1>
                  <p className="text-muted-foreground text-sm">Incident metrics and performance insights</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
          <div className="flex items-center justify-center h-64">
            <RefreshCw className="h-8 w-8 text-foreground animate-spin" />
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
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="p-2 rounded-lg bg-secondary">
                <BarChart3 className="w-5 h-5 text-muted-foreground" />
              </div>
              <div>
                <h1 className="text-base font-medium text-foreground">Analytics Dashboard</h1>
                <p className="text-muted-foreground text-sm">Incident metrics and performance insights</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Select
                value={days.toString()}
                onChange={(e) => setDays(parseInt(e.target.value))}
              >
                <option value={7}>Last 7 days</option>
                <option value={14}>Last 14 days</option>
                <option value={30}>Last 30 days</option>
                <option value={60}>Last 60 days</option>
                <option value={90}>Last 90 days</option>
              </Select>
              <Button variant="outline" onClick={handleExport}>
                <Download className="h-4 w-4 mr-2" />
                Export
              </Button>
              <Button variant="ghost" size="sm" onClick={loadAnalytics}>
                <RefreshCw className={`h-5 w-5 ${loading ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* Error Display */}
      {error && (
        <div className="mb-4 border border-red-500/20 bg-red-500/10 rounded-lg">
          <div className="p-4 text-red-400">
            {error}
          </div>
        </div>
      )}

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="border border-border rounded-lg bg-transparent">
          <div className="p-5">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-muted-foreground">Total Incidents</span>
              <AlertTriangle className="h-4 w-4 text-muted-foreground" />
            </div>
            <div className="text-base font-medium text-foreground">{overview?.total_incidents || 0}</div>
            <div className={`flex items-center gap-1 text-sm mt-1 ${(overview?.incident_change_pct || 0) > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
              {(overview?.incident_change_pct || 0) > 0 ? (
                <TrendingUp className="h-3.5 w-3.5" />
              ) : (
                <TrendingDown className="h-3.5 w-3.5" />
              )}
              {Math.abs(overview?.incident_change_pct || 0)}% vs prev period
            </div>
          </div>
        </div>

        <div className="border border-border rounded-lg bg-transparent">
          <div className="p-5">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-muted-foreground">Open Incidents</span>
              <BellRing className="h-4 w-4 text-red-400" />
            </div>
            <div className="text-base font-medium text-foreground">{overview?.open_incidents || 0}</div>
            <div className="text-sm text-muted-foreground mt-1">Require attention</div>
          </div>
        </div>

        <div className="border border-border rounded-lg bg-transparent">
          <div className="p-5">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-muted-foreground">MTTA</span>
              <Clock className="h-4 w-4 text-orange-400" />
            </div>
            <div className="text-base font-medium text-foreground">{formatMinutes(overview?.mtta_minutes ?? null)}</div>
            <div className="text-sm text-muted-foreground mt-1">Mean Time To Acknowledge</div>
          </div>
        </div>

        <div className="border border-border rounded-lg bg-transparent">
          <div className="p-5">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-muted-foreground">MTTR</span>
              <CheckCircle className="h-4 w-4 text-emerald-400" />
            </div>
            <div className="text-base font-medium text-foreground">{formatMinutes(overview?.mttr_minutes ?? null)}</div>
            <div className="text-sm text-muted-foreground mt-1">Mean Time To Resolve</div>
          </div>
        </div>
      </div>

      {/* Alert Overview Cards */}
      {alertOverview && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div className="border border-border rounded-lg bg-transparent">
            <div className="p-5">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-muted-foreground">Total Alerts</span>
                <BellRing className="h-4 w-4 text-muted-foreground" />
              </div>
              <div className="text-base font-medium text-foreground">{alertOverview.total_alerts}</div>
              <div className={`flex items-center gap-1 text-sm mt-1 ${alertOverview.alert_change_pct > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                {alertOverview.alert_change_pct > 0 ? (
                  <TrendingUp className="h-3.5 w-3.5" />
                ) : (
                  <TrendingDown className="h-3.5 w-3.5" />
                )}
                {Math.abs(alertOverview.alert_change_pct)}% vs prev period
              </div>
            </div>
          </div>

          <div className="border border-border rounded-lg bg-transparent">
            <div className="p-5">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-muted-foreground">Active Alerts</span>
                <AlertTriangle className="h-4 w-4 text-orange-400" />
              </div>
              <div className="text-base font-medium text-foreground">{alertOverview.active_alerts}</div>
              <div className="text-sm text-muted-foreground mt-1">Firing or acknowledged</div>
            </div>
          </div>

          <div className="border border-border rounded-lg bg-transparent">
            <div className="p-5">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-muted-foreground">Resolved Alerts</span>
                <CheckCircle className="h-4 w-4 text-emerald-400" />
              </div>
              <div className="text-base font-medium text-foreground">{alertOverview.resolved_alerts}</div>
              <div className="text-sm text-muted-foreground mt-1">
                {alertOverview.total_alerts
                  ? Math.round((alertOverview.resolved_alerts / alertOverview.total_alerts) * 100)
                  : 0}% resolution rate
              </div>
            </div>
          </div>

          <div className="border border-border rounded-lg bg-transparent">
            <div className="p-5">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-muted-foreground">Alert/Incident Ratio</span>
                <BarChart3 className="h-4 w-4 text-blue-400" />
              </div>
              <div className="text-base font-medium text-foreground">
                {overview?.total_incidents
                  ? `${(alertOverview.total_alerts / overview.total_incidents).toFixed(1)}x`
                  : '-'}
              </div>
              <div className="text-sm text-muted-foreground mt-1">Alerts per incident</div>
            </div>
          </div>
        </div>
      )}

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="border border-border rounded-lg bg-transparent">
          <div className="p-6">
            <h3 className="text-sm font-medium text-foreground">Incident Trend</h3>
          </div>
          <div className="p-6 pt-0">
            <TrendChart data={trend} />
            <div className="flex items-center justify-center gap-4 mt-4 text-xs">
              <span className="flex items-center gap-1 text-muted-foreground"><span className="w-3 h-3 rounded" style={{ backgroundColor: severityColors.critical }} /> Critical</span>
              <span className="flex items-center gap-1 text-muted-foreground"><span className="w-3 h-3 rounded" style={{ backgroundColor: severityColors.high }} /> High</span>
              <span className="flex items-center gap-1 text-muted-foreground"><span className="w-3 h-3 rounded" style={{ backgroundColor: severityColors.medium }} /> Medium</span>
              <span className="flex items-center gap-1 text-muted-foreground"><span className="w-3 h-3 rounded" style={{ backgroundColor: severityColors.low }} /> Low</span>
            </div>
          </div>
        </div>

        <div className="border border-border rounded-lg bg-transparent">
          <div className="p-6">
            <h3 className="text-sm font-medium text-foreground">Incidents by Severity</h3>
          </div>
          <div className="p-6 pt-0">
            {bySeverity.length > 0 ? (
              <BarChart
                data={bySeverity.map(s => ({
                  label: s.severity.charAt(0).toUpperCase() + s.severity.slice(1),
                  value: s.count,
                  color: severityColors[s.severity] || '#6b7280'
                }))}
                maxValue={getMaxCount(bySeverity)}
              />
            ) : (
              <div className="text-muted-foreground text-center py-8">No data available</div>
            )}
          </div>
        </div>
      </div>

      {/* Alert Charts Row */}
      {(alertTrend.length > 0 || alertsBySeverity.length > 0) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <div className="border border-border rounded-lg bg-transparent">
            <div className="p-6">
              <h3 className="text-sm font-medium text-foreground">Alert Trend</h3>
            </div>
            <div className="p-6 pt-0">
              {alertTrend.length > 0 ? (
                <>
                  <div className="relative h-[200px]">
                    <div className="absolute inset-0 flex items-end justify-between gap-1 px-2">
                      {alertTrend.map((point, idx) => {
                        const maxTotal = Math.max(...alertTrend.map(d => d.total), 1);
                        return (
                          <div
                            key={idx}
                            className="flex-1 flex flex-col items-stretch gap-0.5"
                            title={`${point.date?.split('T')[0] || 'N/A'}: ${point.total} alerts`}
                          >
                            {point.critical > 0 && (
                              <div
                                style={{ height: `${(point.critical / maxTotal) * 200}px`, backgroundColor: '#dc2626' }}
                                className="rounded-t"
                              />
                            )}
                            {point.high > 0 && (
                              <div style={{ height: `${(point.high / maxTotal) * 200}px`, backgroundColor: '#f97316' }} />
                            )}
                            {point.error > 0 && (
                              <div style={{ height: `${(point.error / maxTotal) * 200}px`, backgroundColor: '#eab308' }} />
                            )}
                            {point.warning > 0 && (
                              <div
                                style={{ height: `${(point.warning / maxTotal) * 200}px`, backgroundColor: '#3b82f6' }}
                                className="rounded-b"
                              />
                            )}
                          </div>
                        );
                      })}
                    </div>
                    <div className="absolute bottom-0 left-0 right-0 flex justify-between text-xs text-muted-foreground pt-2 border-t border-border">
                      <span>{alertTrend[0]?.date?.split('T')[0] || ''}</span>
                      <span>{alertTrend[alertTrend.length - 1]?.date?.split('T')[0] || ''}</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-center gap-4 mt-4 text-xs">
                    <span className="flex items-center gap-1 text-muted-foreground"><span className="w-3 h-3 rounded" style={{ backgroundColor: '#dc2626' }} /> Critical</span>
                    <span className="flex items-center gap-1 text-muted-foreground"><span className="w-3 h-3 rounded" style={{ backgroundColor: '#f97316' }} /> High</span>
                    <span className="flex items-center gap-1 text-muted-foreground"><span className="w-3 h-3 rounded" style={{ backgroundColor: '#eab308' }} /> Error</span>
                    <span className="flex items-center gap-1 text-muted-foreground"><span className="w-3 h-3 rounded" style={{ backgroundColor: '#3b82f6' }} /> Warning</span>
                  </div>
                </>
              ) : (
                <div className="text-muted-foreground text-center py-8">No alert data</div>
              )}
            </div>
          </div>

          <div className="border border-border rounded-lg bg-transparent">
            <div className="p-6">
              <h3 className="text-sm font-medium text-foreground">Alerts by Severity</h3>
            </div>
            <div className="p-6 pt-0">
              {alertsBySeverity.length > 0 ? (
                <BarChart
                  data={alertsBySeverity.map(s => ({
                    label: s.severity.charAt(0).toUpperCase() + s.severity.slice(1),
                    value: s.count,
                    color: severityColors[s.severity] || '#6b7280'
                  }))}
                  maxValue={getMaxCount(alertsBySeverity)}
                />
              ) : (
                <div className="text-muted-foreground text-center py-8">No alert data</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Charts Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="border border-border rounded-lg bg-transparent">
          <div className="p-6">
            <h3 className="text-sm font-medium text-foreground">Incidents by Status</h3>
          </div>
          <div className="p-6 pt-0">
            {byStatus.length > 0 ? (
              <BarChart
                data={byStatus.map(s => ({
                  label: s.status.charAt(0).toUpperCase() + s.status.slice(1),
                  value: s.count,
                  color: statusColors[s.status] || '#6b7280'
                }))}
                maxValue={getMaxCount(byStatus)}
              />
            ) : (
              <div className="text-muted-foreground text-center py-8">No data available</div>
            )}
          </div>
        </div>

        <div className="border border-border rounded-lg bg-transparent">
          <div className="p-6">
            <h3 className="text-sm font-medium text-foreground">Alert Sources</h3>
          </div>
          <div className="p-6 pt-0">
            {alertSources.length > 0 ? (
              <BarChart
                data={alertSources.slice(0, 6).map((s, idx) => ({
                  label: s.source,
                  value: s.count,
                  color: ['#3b82f6', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444'][idx % 6]
                }))}
                maxValue={getMaxCount(alertSources)}
              />
            ) : (
              <div className="text-muted-foreground text-center py-8">No alert data</div>
            )}
          </div>
        </div>
      </div>

      {/* Charts Row 3 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-6">
        <div className="border border-border rounded-lg bg-transparent">
          <div className="p-6">
            <h3 className="text-sm font-medium text-foreground">Incidents by Hour (UTC)</h3>
          </div>
          <div className="p-6 pt-0">
            <HourlyHeatmap data={hourlyDistribution} />
          </div>
        </div>

        <div className="border border-border rounded-lg bg-transparent">
          <div className="p-6">
            <h3 className="text-sm font-medium text-foreground">Incidents by Day</h3>
          </div>
          <div className="p-6 pt-0">
            {dayOfWeek.length > 0 ? (
              <BarChart
                data={dayOfWeek.map(d => ({
                  label: d.day.slice(0, 3),
                  value: d.count,
                  color: '#3b82f6'
                }))}
                maxValue={getMaxCount(dayOfWeek)}
              />
            ) : (
              <div className="text-muted-foreground text-center py-8">No data available</div>
            )}
          </div>
        </div>

        <div className="border border-border rounded-lg bg-transparent">
          <div className="p-6">
            <h3 className="text-sm font-medium text-foreground">Quick Stats</h3>
          </div>
          <div className="p-6 pt-0">
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Resolved</span>
                <span className="font-semibold text-foreground">{overview?.resolved_incidents || 0}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Resolution Rate</span>
                <span className="font-semibold text-foreground">
                  {overview?.total_incidents
                    ? Math.round((overview.resolved_incidents / overview.total_incidents) * 100)
                    : 0}%
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Avg/Day</span>
                <span className="font-semibold text-foreground">
                  {overview?.total_incidents
                    ? (overview.total_incidents / days).toFixed(1)
                    : 0}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Period</span>
                <span className="font-semibold text-foreground">{days} days</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Responders Table */}
      <div className="border border-border rounded-lg bg-transparent">
        <div className="p-6">
          <h3 className="text-sm font-medium text-foreground flex items-center gap-2">
            <Users className="h-4 w-4 text-muted-foreground" />
            Responder Performance
          </h3>
        </div>
        <div className="p-6 pt-0">
          {responders.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Responder</TableHead>
                  <TableHead className="text-right">Incidents</TableHead>
                  <TableHead className="text-right">Resolved</TableHead>
                  <TableHead className="text-right">Resolution Rate</TableHead>
                  <TableHead className="text-right">Avg Resolution</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {responders.map((r) => (
                  <TableRow key={r.user_id}>
                    <TableCell>
                      <div className="font-medium text-foreground">{r.name}</div>
                      <div className="text-sm text-muted-foreground">{r.email}</div>
                    </TableCell>
                    <TableCell className="text-right font-medium">{r.incidents_handled}</TableCell>
                    <TableCell className="text-right">{r.resolved}</TableCell>
                    <TableCell className="text-right">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${
                        (r.resolved / r.incidents_handled) >= 0.9 ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
                        (r.resolved / r.incidents_handled) >= 0.7 ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20'
                      }`}>
                        {Math.round((r.resolved / r.incidents_handled) * 100)}%
                      </span>
                    </TableCell>
                    <TableCell className="text-right text-muted-foreground">
                      {formatMinutes(r.avg_resolution_minutes)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="text-muted-foreground text-center py-8">No responder data available</div>
          )}
        </div>
      </div>
      </div>
    </div>
  );
};

export default AnalyticsDashboard;
