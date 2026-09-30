// frontend/oncall-frontend/src/components/ErrorTrackingDashboard.tsx
import React, { useState, useEffect, useCallback } from 'react';
import {
  AlertTriangle,
  BarChart3,
  Bug,
  CheckCircle,
  ChevronRight,
  Clock,
  EyeOff,
  RefreshCw,
  Search,
  Server,
  Square,
  SquareCheck,
  Users,
  X,
} from 'lucide-react';
import { AreaChart, Area, ResponsiveContainer } from 'recharts';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Tabs, TabsList, TabsTrigger } from './ui/tabs';
import { useNotifications } from '../contexts/NotificationContext';

import { API_URL as API_BASE_URL } from '../config/api';

interface ErrorGroup {
  id: string;
  title: string;
  error_type?: string;
  service_name?: string;
  status: 'unresolved' | 'resolved' | 'ignored';
  is_regression?: boolean;
  event_count: number;
  user_count: number;
  first_seen_at: string;
  last_seen_at: string;
  last_release?: string;
  environments?: string[];
  assigned_to_name?: string;
  sparkline_data?: number[];
}

interface ErrorStats {
  total_events: number;
  total_groups: number;
  unresolved_groups: number;
  events_by_day: { date: string; count: number }[];
  top_errors: ErrorGroup[];
  affected_users: number;
  affected_services: string[];
}

type Period = '1h' | '24h' | '7d' | '14d' | '30d';

interface ErrorTrackingDashboardProps {
  onNavigateToGroup?: (groupId: string) => void;
}

const MiniSparkline: React.FC<{ data: number[] }> = ({ data }) => {
  const chartData = data.map((count, i) => ({ count, i }));
  const hasData = data.some((v) => v > 0);
  return (
    <div className="w-[120px] h-[32px] flex-shrink-0">
      {hasData ? (
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#ef4444" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#ef4444" stopOpacity={0} />
              </linearGradient>
            </defs>
            <Area
              type="monotone"
              dataKey="count"
              stroke="#ef4444"
              strokeWidth={1.5}
              fill="url(#sparkFill)"
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      ) : (
        <div className="w-full h-full flex items-end px-1">
          <div className="w-full h-px bg-border" />
        </div>
      )}
    </div>
  );
};

const AssigneeAvatar: React.FC<{ name?: string }> = ({ name }) => {
  if (!name) {
    return (
      <div className="w-6 h-6 rounded-full border-2 border-dashed border-muted-foreground/30 flex items-center justify-center" title="Unassigned">
        <span className="text-[8px] text-muted-foreground">?</span>
      </div>
    );
  }
  const initials = name
    .split(' ')
    .map((p) => p[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
  return (
    <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center" title={name}>
      <span className="text-[10px] font-medium text-primary">{initials}</span>
    </div>
  );
};

const PERIODS: { value: Period; label: string }[] = [
  { value: '1h', label: '1h' },
  { value: '24h', label: '24h' },
  { value: '7d', label: '7d' },
  { value: '14d', label: '14d' },
  { value: '30d', label: '30d' },
];

const ErrorTrackingDashboard: React.FC<ErrorTrackingDashboardProps> = ({
  onNavigateToGroup,
}) => {
  const { showToast } = useNotifications();
  const [groups, setGroups] = useState<ErrorGroup[]>([]);
  const [stats, setStats] = useState<ErrorStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [total, setTotal] = useState(0);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('unresolved');
  const [serviceFilter, setServiceFilter] = useState<string>('');
  const [environmentFilter, setEnvironmentFilter] = useState<string>('');
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState('last_seen_at');
  const [period, setPeriod] = useState<Period | ''>('');

  // Environments
  const [environments, setEnvironments] = useState<string[]>([]);

  // Bulk selection
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Pagination
  const [offset, setOffset] = useState(0);
  const limit = 20;

  const fetchEnvironments = useCallback(async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/errors/environments`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (response.ok) {
        const data = await response.json();
        setEnvironments(data);
      }
    } catch {
      // ignore
    }
  }, []);

  const fetchGroups = useCallback(async () => {
    try {
      const token = localStorage.getItem('access_token');
      const params = new URLSearchParams({
        limit: String(limit),
        offset: String(offset),
        sort_by: sortBy,
        sort_order: 'desc',
        include_sparkline: 'true',
      });

      if (statusFilter && statusFilter !== 'all') {
        params.append('status', statusFilter);
      }
      if (serviceFilter) {
        params.append('service_name', serviceFilter);
      }
      if (environmentFilter) {
        params.append('environment', environmentFilter);
      }
      if (search) {
        params.append('search', search);
      }
      if (period) {
        params.append('period', period);
      }

      const response = await fetch(`${API_BASE_URL}/errors/groups?${params}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        setGroups(data.groups || []);
        setTotal(data.total || 0);
      } else {
        setGroups([]);
        setTotal(0);
      }
    } catch {
      setGroups([]);
      setTotal(0);
    } finally {
      setIsLoading(false);
    }
  }, [offset, statusFilter, serviceFilter, environmentFilter, search, sortBy, period]);

  const fetchStats = useCallback(async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/errors/stats?days=7`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (response.ok) {
        setStats(await response.json());
      } else {
        setStats(null);
      }
    } catch {
      setStats(null);
    }
  }, []);

  useEffect(() => {
    fetchGroups();
    fetchStats();
    fetchEnvironments();
  }, [fetchGroups, fetchStats, fetchEnvironments]);

  // Clear selection when filters change
  useEffect(() => {
    setSelectedIds(new Set());
  }, [statusFilter, serviceFilter, environmentFilter, search, period, offset]);

  const updateGroupStatus = async (groupId: string, newStatus: string) => {
    try {
      const token = localStorage.getItem('access_token');
      const endpoint = newStatus === 'resolved' ? 'resolve' :
                       newStatus === 'ignored' ? 'ignore' : 'reopen';

      const response = await fetch(`${API_BASE_URL}/errors/groups/${groupId}/${endpoint}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        showToast({ type: 'success', title: 'Status Updated', message: `Error ${newStatus}`, autoClose: true });
        fetchGroups();
        fetchStats();
      }
    } catch {
      showToast({ type: 'error', title: 'Update Failed', message: 'Failed to update error status', autoClose: true });
    }
  };

  const bulkUpdate = async (newStatus: string) => {
    if (selectedIds.size === 0) return;
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/errors/groups/bulk-update`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          group_ids: Array.from(selectedIds),
          status: newStatus,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        showToast({ type: 'success', title: 'Bulk Update', message: `${data.updated} errors ${newStatus}`, autoClose: true });
        setSelectedIds(new Set());
        fetchGroups();
        fetchStats();
      }
    } catch {
      showToast({ type: 'error', title: 'Bulk Update Failed', message: 'Failed to update errors', autoClose: true });
    }
  };

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === groups.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(groups.map((g) => g.id)));
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  const formatAbsolute = (dateString: string) => new Date(dateString).toLocaleString();

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'unresolved': return 'bg-red-500/20 text-red-400 border-red-500/30';
      case 'resolved': return 'bg-green-500/20 text-green-400 border-green-500/30';
      case 'ignored': return 'bg-secondary text-muted-foreground border-border';
      default: return 'bg-secondary text-muted-foreground';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'unresolved': return <AlertTriangle className="w-4 h-4" />;
      case 'resolved': return <CheckCircle className="w-4 h-4" />;
      case 'ignored': return <EyeOff className="w-4 h-4" />;
      default: return <Bug className="w-4 h-4" />;
    }
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-red-500/10">
                <Bug className="w-6 h-6 text-red-400" />
              </div>
              <div>
                <h1 className="text-base font-medium text-foreground">Error Tracking</h1>
                <p className="text-muted-foreground text-sm">Track and resolve application errors</p>
              </div>
            </div>
            <Button
              variant="outline"
              onClick={() => { fetchGroups(); fetchStats(); }}
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </Button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div className="border border-border rounded-lg bg-transparent">
              <div className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-muted-foreground">Unresolved</span>
                  <div className="p-2 rounded-xl bg-red-500/10">
                    <AlertTriangle className="w-4 h-4 text-red-400" />
                  </div>
                </div>
                <p className="text-2xl font-bold text-red-400">{stats.unresolved_groups}</p>
              </div>
            </div>
            <div className="border border-border rounded-lg bg-transparent">
              <div className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-muted-foreground">Events (7d)</span>
                  <div className="p-2 rounded-xl bg-blue-500/10">
                    <BarChart3 className="w-4 h-4 text-blue-400" />
                  </div>
                </div>
                <p className="text-2xl font-bold text-foreground">{stats.total_events.toLocaleString()}</p>
              </div>
            </div>
            <div className="border border-border rounded-lg bg-transparent">
              <div className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-muted-foreground">Affected Users</span>
                  <div className="p-2 rounded-xl bg-purple-500/10">
                    <Users className="w-4 h-4 text-purple-400" />
                  </div>
                </div>
                <p className="text-2xl font-bold text-foreground">{stats.affected_users.toLocaleString()}</p>
              </div>
            </div>
            <div className="border border-border rounded-lg bg-transparent">
              <div className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-muted-foreground">Services</span>
                  <div className="p-2 rounded-xl bg-green-500/10">
                    <Server className="w-4 h-4 text-green-400" />
                  </div>
                </div>
                <p className="text-2xl font-bold text-foreground">{stats.affected_services.length}</p>
              </div>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="border border-border rounded-lg bg-transparent mb-6">
          <div className="p-4">
            <div className="flex flex-wrap items-center gap-4">
              {/* Search */}
              <div className="relative flex-1 min-w-[200px]">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  placeholder="Search errors..."
                  value={search}
                  onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
                  className="pl-9"
                />
              </div>

              {/* Status Filter */}
              <Tabs value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setOffset(0); }}>
                <TabsList>
                  <TabsTrigger value="unresolved">Unresolved</TabsTrigger>
                  <TabsTrigger value="resolved">Resolved</TabsTrigger>
                  <TabsTrigger value="ignored">Ignored</TabsTrigger>
                  <TabsTrigger value="all">All</TabsTrigger>
                </TabsList>
              </Tabs>

              {/* Time Range */}
              <div className="flex items-center border border-border rounded-md overflow-hidden">
                {PERIODS.map((p) => (
                  <button
                    key={p.value}
                    onClick={() => { setPeriod(period === p.value ? '' : p.value); setOffset(0); }}
                    className={`px-2.5 py-1.5 text-xs font-medium transition-colors ${
                      period === p.value
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted hover:bg-muted/80 text-muted-foreground'
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>

              {/* Environment Filter */}
              {environments.length > 0 && (
                <select
                  value={environmentFilter}
                  onChange={(e) => { setEnvironmentFilter(e.target.value); setOffset(0); }}
                  className="bg-muted border border-border rounded-md px-3 py-2 text-sm"
                >
                  <option value="">All Envs</option>
                  {environments.map((env) => (
                    <option key={env} value={env}>{env}</option>
                  ))}
                </select>
              )}

              {/* Sort */}
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="bg-muted border border-border rounded-md px-3 py-2 text-sm"
              >
                <option value="last_seen_at">Last Seen</option>
                <option value="first_seen_at">First Seen</option>
                <option value="event_count">Event Count</option>
                <option value="user_count">User Count</option>
              </select>
            </div>
          </div>
        </div>

        {/* Bulk Action Bar */}
        {selectedIds.size > 0 && (
          <div className="sticky top-0 z-10 bg-primary/10 border border-primary/30 rounded-lg px-4 py-3 flex items-center justify-between backdrop-blur-sm">
            <span className="text-sm font-medium">{selectedIds.size} selected</span>
            <div className="flex items-center gap-2">
              <Button size="sm" onClick={() => bulkUpdate('resolved')} className="bg-green-600 hover:bg-green-700 text-white">
                <CheckCircle className="w-3.5 h-3.5 mr-1" /> Resolve
              </Button>
              <Button size="sm" variant="outline" onClick={() => bulkUpdate('ignored')}>
                <EyeOff className="w-3.5 h-3.5 mr-1" /> Ignore
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setSelectedIds(new Set())}>
                <X className="w-3.5 h-3.5 mr-1" /> Cancel
              </Button>
            </div>
          </div>
        )}

        {/* Error Groups List */}
        <div className="border border-border rounded-lg bg-transparent">
          <div className="p-6">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold flex items-center gap-2">
                Error Groups
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-secondary text-muted-foreground border-border">{total}</span>
              </h3>
              {groups.length > 0 && (
                <button
                  onClick={toggleSelectAll}
                  className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
                >
                  {selectedIds.size === groups.length ? (
                    <SquareCheck className="w-4 h-4" />
                  ) : (
                    <Square className="w-4 h-4" />
                  )}
                  {selectedIds.size === groups.length ? 'Deselect All' : 'Select All'}
                </button>
              )}
            </div>
          </div>
          <div className="p-6 pt-0">
            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
              </div>
            ) : groups.length === 0 ? (
              <div className="text-center py-12">
                <Bug className="w-12 h-12 mx-auto text-muted-foreground/50 mb-3" />
                <p className="text-muted-foreground">No errors found</p>
                <p className="text-sm text-muted-foreground mt-1">
                  {statusFilter !== 'all' ? 'Try changing the filter' : 'Great job keeping your app error-free!'}
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {groups.map((group) => (
                  <div
                    key={group.id}
                    className={`p-4 bg-muted/30 rounded-lg hover:bg-muted/50 transition-colors border cursor-pointer ${
                      selectedIds.has(group.id) ? 'border-primary bg-primary/5' : 'border-border'
                    }`}
                    onClick={() => onNavigateToGroup?.(group.id)}
                  >
                    <div className="flex items-start justify-between gap-4">
                      {/* Checkbox */}
                      <button
                        className="mt-1 flex-shrink-0"
                        onClick={(e) => { e.stopPropagation(); toggleSelect(group.id); }}
                      >
                        {selectedIds.has(group.id) ? (
                          <SquareCheck className="w-4 h-4 text-primary" />
                        ) : (
                          <Square className="w-4 h-4 text-muted-foreground/50" />
                        )}
                      </button>

                      <div className="flex-1 min-w-0">
                        {/* Title */}
                        <div className="flex items-center gap-2 mb-1">
                          <Bug className="w-4 h-4 text-red-500 flex-shrink-0" />
                          <h3 className="font-medium text-foreground truncate">
                            {group.title}
                          </h3>
                        </div>

                        {/* Metadata */}
                        <div className="flex flex-wrap items-center gap-2 text-sm">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${getStatusColor(group.status)}`}>
                            {getStatusIcon(group.status)}
                            <span className="ml-1 capitalize">{group.status}</span>
                          </span>

                          {group.is_regression && (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-orange-500/20 text-orange-400 border-orange-500/30">
                              Regression
                            </span>
                          )}

                          {group.error_type && (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-secondary text-muted-foreground border-border">
                              {group.error_type}
                            </span>
                          )}

                          {group.service_name && (
                            <span className="text-muted-foreground flex items-center gap-1">
                              <Server className="w-3 h-3" />
                              {group.service_name}
                            </span>
                          )}

                          {group.environments && group.environments.length > 0 && (
                            <span className="text-muted-foreground">
                              {group.environments.join(', ')}
                            </span>
                          )}
                        </div>

                        {/* Times — relative with absolute on hover */}
                        <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                          <span
                            className="flex items-center gap-1"
                            title={formatAbsolute(group.last_seen_at)}
                          >
                            <Clock className="w-3 h-3" />
                            Last: {formatDate(group.last_seen_at)}
                          </span>
                          <span title={formatAbsolute(group.first_seen_at)}>
                            First: {formatDate(group.first_seen_at)}
                          </span>
                          {group.last_release && (
                            <span>Release: {group.last_release}</span>
                          )}
                        </div>
                      </div>

                      {/* Sparkline + Stats */}
                      <div className="flex items-center gap-4 flex-shrink-0">
                        {/* Sparkline */}
                        {group.sparkline_data && (
                          <MiniSparkline data={group.sparkline_data} />
                        )}

                        <div className="text-center min-w-[48px]">
                          <p className="text-lg font-bold text-foreground">{group.event_count.toLocaleString()}</p>
                          <p className="text-xs text-muted-foreground">events</p>
                        </div>
                        <div className="text-center min-w-[48px]">
                          <p className="text-lg font-bold text-foreground">{group.user_count.toLocaleString()}</p>
                          <p className="text-xs text-muted-foreground">users</p>
                        </div>

                        {/* Assignee */}
                        <AssigneeAvatar name={group.assigned_to_name} />

                        {/* Actions */}
                        <div className="flex items-center gap-2">
                          {group.status === 'unresolved' && (
                            <>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={(e) => { e.stopPropagation(); updateGroupStatus(group.id, 'resolved'); }}
                                title="Mark as Resolved"
                              >
                                <CheckCircle className="w-4 h-4 text-green-500" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={(e) => { e.stopPropagation(); updateGroupStatus(group.id, 'ignored'); }}
                                title="Ignore"
                              >
                                <EyeOff className="w-4 h-4 text-muted-foreground" />
                              </Button>
                            </>
                          )}
                          {(group.status === 'resolved' || group.status === 'ignored') && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={(e) => { e.stopPropagation(); updateGroupStatus(group.id, 'unresolved'); }}
                              title="Reopen"
                            >
                              <RefreshCw className="w-4 h-4 text-yellow-500" />
                            </Button>
                          )}
                          <ChevronRight className="w-4 h-4 text-muted-foreground" />
                        </div>
                      </div>
                    </div>
                  </div>
                ))}

                {/* Pagination */}
                {total > limit && (
                  <div className="flex items-center justify-between pt-4">
                    <p className="text-sm text-muted-foreground">
                      Showing {offset + 1}-{Math.min(offset + limit, total)} of {total}
                    </p>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setOffset(Math.max(0, offset - limit))}
                        disabled={offset === 0}
                      >
                        Previous
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setOffset(offset + limit)}
                        disabled={offset + limit >= total}
                      >
                        Next
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ErrorTrackingDashboard;
