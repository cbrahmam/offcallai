// frontend/oncall-frontend/src/components/DatabaseMonitoring.tsx
import React, { useState, useEffect } from 'react';
import {
  Activity,
  AlertCircle,
  BarChart3,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Clock,
  Code,
  Cpu,
  Database,
  GitBranch,
  HardDrive,
  MoreVertical,
  Plus,
  RefreshCw,
  Search,
  Server,
  Settings,
  Trash2,
  XCircle,
  Zap
} from 'lucide-react';
import { API_URL } from '../config/api';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';

// Types
interface DatabaseInstance {
  id: string;
  name: string;
  display_name: string;
  description: string;
  database_type: string;
  version: string;
  hostname: string;
  port: number;
  database_name: string;
  status: string;
  connection_status: string;
  last_check: string;
  replication_role: string;
  replication_lag_seconds: number;
  connections_used: number;
  connections_max: number;
  connection_utilization: number;
  storage_used_bytes: number;
  storage_total_bytes: number;
  storage_utilization: number;
  queries_per_second: number;
  avg_query_time_ms: number;
  slow_queries_count: number;
  cache_hit_ratio: number;
  locks_waiting: number;
  deadlocks_count: number;
}

interface DatabaseQuery {
  id: string;
  instance_id: string;
  query_normalized: string;
  query_sample: string;
  database_name: string;
  call_count: number;
  total_time_ms: number;
  avg_time_ms: number;
  max_time_ms: number;
  avg_rows_returned: number;
  is_slow: boolean;
  query_type: string;
  last_seen: string;
}

interface DatabaseAlert {
  id: string;
  instance_id: string;
  alert_type: string;
  severity: string;
  status: string;
  title: string;
  message: string;
  triggered_at: string;
}

interface DatabaseSummary {
  total_instances: number;
  healthy_instances: number;
  warning_instances: number;
  critical_instances: number;
  unreachable_instances: number;
  by_type: Record<string, number>;
  total_connections_used: number;
  total_connections_max: number;
  total_storage_used_bytes: number;
  total_storage_bytes: number;
  avg_cache_hit_ratio: number;
  total_slow_queries: number;
  total_active_alerts: number;
}

type ViewMode = 'overview' | 'instances' | 'queries' | 'alerts';

const DatabaseMonitoring: React.FC = () => {
  const [viewMode, setViewMode] = useState<ViewMode>('overview');
  const [instances, setInstances] = useState<DatabaseInstance[]>([]);
  const [queries, setQueries] = useState<DatabaseQuery[]>([]);
  const [alerts, setAlerts] = useState<DatabaseAlert[]>([]);
  const [summary, setSummary] = useState<DatabaseSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedInstance, setSelectedInstance] = useState<string | null>(null);
  const [expandedInstance, setExpandedInstance] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [showAddInstance, setShowAddInstance] = useState(false);

  const getAuthHeaders = () => ({
    'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
    'Content-Type': 'application/json',
  });

  useEffect(() => {
    fetchInstances();
    fetchSummary();
    fetchAlerts();
  }, []);

  useEffect(() => {
    if (selectedInstance) {
      fetchQueries(selectedInstance);
    } else {
      fetchAllQueries();
    }
  }, [selectedInstance]);

  const fetchInstances = async () => {
    try {
      const response = await fetch(`${API_URL}/databases/instances`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        const instancesData = data.instances || [];
        setInstances(instancesData);
      } else {
        setInstances([]);
      }
    } catch (error) {
      console.error('Failed to fetch instances:', error);
      setInstances([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchSummary = async () => {
    try {
      const response = await fetch(`${API_URL}/databases/summary`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        if (data && data.total_instances > 0) {
          setSummary(data);
        } else {
          setSummary(null);
        }
      } else {
        setSummary(null);
      }
    } catch (error) {
      console.error('Failed to fetch summary:', error);
      setSummary(null);
    }
  };

  const fetchQueries = async (instanceId: string) => {
    try {
      const response = await fetch(`${API_URL}/databases/queries?instance_id=${instanceId}&limit=50`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        const queriesData = data.queries || [];
        setQueries(queriesData);
      } else {
        setQueries([]);
      }
    } catch (error) {
      console.error('Failed to fetch queries:', error);
      setQueries([]);
    }
  };

  const fetchAllQueries = async () => {
    try {
      const response = await fetch(`${API_URL}/databases/queries?limit=50`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        const queriesData = data.queries || [];
        setQueries(queriesData);
      } else {
        setQueries([]);
      }
    } catch (error) {
      console.error('Failed to fetch queries:', error);
      setQueries([]);
    }
  };

  const fetchAlerts = async () => {
    try {
      const response = await fetch(`${API_URL}/databases/alerts?status=active`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        const alertsData = data.alerts || [];
        setAlerts(alertsData);
      } else {
        setAlerts([]);
      }
    } catch (error) {
      console.error('Failed to fetch alerts:', error);
      setAlerts([]);
    }
  };

  // Helper functions
  const formatBytes = (bytes: number): string => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatMs = (ms: number): string => {
    if (!ms) return '0ms';
    if (ms < 1) return `${(ms * 1000).toFixed(0)}µs`;
    if (ms < 1000) return `${ms.toFixed(2)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const getStatusColor = (status: string): string => {
    switch (status?.toLowerCase()) {
      case 'healthy':
      case 'connected':
        return 'text-green-400';
      case 'warning':
        return 'text-yellow-400';
      case 'critical':
      case 'unreachable':
      case 'error':
        return 'text-red-400';
      default:
        return 'text-muted-foreground';
    }
  };

  const getStatusBg = (status: string): string => {
    switch (status?.toLowerCase()) {
      case 'healthy':
      case 'connected':
        return 'bg-green-500/20 text-green-400';
      case 'warning':
        return 'bg-yellow-500/20 text-yellow-400';
      case 'critical':
      case 'unreachable':
      case 'error':
        return 'bg-red-500/20 text-red-400';
      default:
        return 'bg-secondary text-muted-foreground';
    }
  };

  const getDatabaseIcon = (type: string) => {
    const iconClass = "w-5 h-5";
    return <Database className={iconClass} />;
  };

  const getDatabaseTypeColor = (type: string): string => {
    switch (type?.toLowerCase()) {
      case 'postgresql':
        return 'bg-blue-500/20 text-blue-400';
      case 'mysql':
      case 'mariadb':
        return 'bg-orange-500/20 text-orange-400';
      case 'mongodb':
        return 'bg-green-500/20 text-green-400';
      case 'redis':
        return 'bg-red-500/20 text-red-400';
      case 'elasticsearch':
        return 'bg-yellow-500/20 text-yellow-400';
      default:
        return 'bg-secondary text-muted-foreground';
    }
  };

  // Render Overview
  const renderOverview = () => (
    <div className="space-y-6">
      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-muted/50 rounded-xl p-4 border border-border/50">
            <div className="flex items-center gap-3 mb-2">
              <Database className="w-5 h-5 text-blue-400" />
              <span className="text-muted-foreground text-sm">Databases</span>
            </div>
            <div className="text-2xl font-bold text-foreground">{summary.total_instances}</div>
            <div className="flex gap-2 mt-2 text-xs">
              <span className="text-green-400">{summary.healthy_instances} healthy</span>
              {summary.warning_instances > 0 && (
                <span className="text-yellow-400">{summary.warning_instances} warning</span>
              )}
              {summary.critical_instances > 0 && (
                <span className="text-red-400">{summary.critical_instances} critical</span>
              )}
            </div>
          </div>

          <div className="bg-muted/50 rounded-xl p-4 border border-border/50">
            <div className="flex items-center gap-3 mb-2">
              <Zap className="w-5 h-5 text-purple-400" />
              <span className="text-muted-foreground text-sm">Connections</span>
            </div>
            <div className="text-2xl font-bold text-foreground">
              {summary.total_connections_used}
              <span className="text-sm text-muted-foreground">/{summary.total_connections_max}</span>
            </div>
            <div className="mt-2">
              <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-purple-500 rounded-full"
                  style={{
                    width: `${summary.total_connections_max > 0
                      ? Math.min(100, (summary.total_connections_used / summary.total_connections_max) * 100)
                      : 0}%`
                  }}
                />
              </div>
            </div>
          </div>

          <div className="bg-muted/50 rounded-xl p-4 border border-border/50">
            <div className="flex items-center gap-3 mb-2">
              <HardDrive className="w-5 h-5 text-green-400" />
              <span className="text-muted-foreground text-sm">Storage</span>
            </div>
            <div className="text-2xl font-bold text-foreground">
              {formatBytes(summary.total_storage_used_bytes)}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              of {formatBytes(summary.total_storage_bytes)} total
            </div>
          </div>

          <div className="bg-muted/50 rounded-xl p-4 border border-border/50">
            <div className="flex items-center gap-3 mb-2">
              <BarChart3 className="w-5 h-5 text-orange-400" />
              <span className="text-muted-foreground text-sm">Cache Hit Ratio</span>
            </div>
            <div className="text-2xl font-bold text-foreground">
              {(summary.avg_cache_hit_ratio * 100).toFixed(1)}%
            </div>
            <div className="flex gap-2 mt-2 text-xs">
              <span className="text-yellow-400">{summary.total_slow_queries} slow queries</span>
            </div>
          </div>
        </div>
      )}

      {/* Active Alerts */}
      {alerts.length > 0 && (
        <div className="bg-muted/50 rounded-xl border border-border/50">
          <div className="p-4 border-b border-border/50 flex items-center justify-between">
            <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
              Active Alerts ({alerts.length})
            </h3>
            <button
              onClick={() => setViewMode('alerts')}
              className="text-sm text-blue-400 hover:text-blue-300"
            >
              View All
            </button>
          </div>
          <div className="divide-y divide-border">
            {alerts.slice(0, 5).map(alert => (
              <div key={alert.id} className="p-4 hover:bg-muted/20">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded text-xs flex-shrink-0 ${
                        alert.severity === 'critical' ? 'bg-red-500/20 text-red-400' : 'bg-yellow-500/20 text-yellow-400'
                      }`}>
                        {alert.severity}
                      </span>
                      <h4 className="font-medium text-foreground">{alert.title}</h4>
                    </div>
                    <p className="text-sm text-muted-foreground mt-1">{alert.message}</p>
                  </div>
                  <span className="text-xs text-muted-foreground flex-shrink-0">
                    {new Date(alert.triggered_at).toLocaleTimeString()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Instances List */}
      <div className="bg-muted/50 rounded-xl border border-border/50">
        <div className="p-4 border-b border-border/50 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-foreground">Database Instances</h3>
          <button
            onClick={() => setShowAddInstance(true)}
            className="flex items-center gap-2 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-foreground rounded-lg text-sm transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Database
          </button>
        </div>

        {instances.length === 0 ? (
          <div className="p-8 text-center">
            <Database className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
            <h4 className="text-lg font-medium text-foreground mb-2">No Databases Configured</h4>
            <p className="text-muted-foreground mb-4">
              Add a database to start monitoring performance, queries, and health.
            </p>
            <button
              onClick={() => setShowAddInstance(true)}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-foreground rounded-lg transition-colors"
            >
              Add Your First Database
            </button>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {instances.map(instance => (
              <div key={instance.id} className="p-4">
                <div
                  className="flex items-center justify-between cursor-pointer"
                  onClick={() => setExpandedInstance(expandedInstance === instance.id ? null : instance.id)}
                >
                  <div className="flex items-center gap-4">
                    <div className={`p-2 rounded-lg flex-shrink-0 ${getDatabaseTypeColor(instance.database_type)}`}>
                      {getDatabaseIcon(instance.database_type)}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="font-medium text-foreground">{instance.display_name || instance.name}</h4>
                        <span className={`px-2 py-0.5 rounded text-xs ${getStatusBg(instance.status)}`}>
                          {instance.status}
                        </span>
                        <span className={`px-2 py-0.5 rounded text-xs ${getDatabaseTypeColor(instance.database_type)}`}>
                          {instance.database_type}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-sm text-muted-foreground">
                        <span>{instance.hostname}:{instance.port}</span>
                        {instance.version && <span>v{instance.version}</span>}
                        {instance.replication_role !== 'standalone' && (
                          <span className="flex items-center gap-1">
                            <GitBranch className="w-3 h-3" />
                            {instance.replication_role}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-6">
                    <div className="grid grid-cols-4 gap-6 text-center">
                      <div>
                        <div className="text-lg font-semibold text-foreground">
                          {instance.queries_per_second?.toFixed(1) || 0}
                        </div>
                        <div className="text-xs text-muted-foreground">QPS</div>
                      </div>
                      <div>
                        <div className="text-lg font-semibold text-foreground">
                          {formatMs(instance.avg_query_time_ms || 0)}
                        </div>
                        <div className="text-xs text-muted-foreground">Avg Latency</div>
                      </div>
                      <div>
                        <div className="text-lg font-semibold text-foreground">
                          {instance.connections_used || 0}
                        </div>
                        <div className="text-xs text-muted-foreground">Connections</div>
                      </div>
                      <div>
                        <div className="text-lg font-semibold text-foreground">
                          {((instance.cache_hit_ratio || 0) * 100).toFixed(0)}%
                        </div>
                        <div className="text-xs text-muted-foreground">Cache Hit</div>
                      </div>
                    </div>
                    {expandedInstance === instance.id ? (
                      <ChevronDown className="w-5 h-5 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="w-5 h-5 text-muted-foreground" />
                    )}
                  </div>
                </div>

                {expandedInstance === instance.id && (
                  <div className="mt-4 pt-4 border-t border-border/50">
                    <div className="grid grid-cols-3 gap-4 mb-4">
                      <div className="bg-muted/50 rounded-lg p-3">
                        <div className="text-sm text-muted-foreground mb-2">Connection Usage</div>
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                            <div
                              className="h-full bg-purple-500 rounded-full"
                              style={{ width: `${instance.connection_utilization || 0}%` }}
                            />
                          </div>
                          <span className="text-sm text-foreground">
                            {instance.connections_used}/{instance.connections_max}
                          </span>
                        </div>
                      </div>
                      <div className="bg-muted/50 rounded-lg p-3">
                        <div className="text-sm text-muted-foreground mb-2">Storage Usage</div>
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                            <div
                              className="h-full bg-green-500 rounded-full"
                              style={{ width: `${instance.storage_utilization || 0}%` }}
                            />
                          </div>
                          <span className="text-sm text-foreground">
                            {formatBytes(instance.storage_used_bytes)}
                          </span>
                        </div>
                      </div>
                      <div className="bg-muted/50 rounded-lg p-3">
                        <div className="text-sm text-muted-foreground mb-2">Performance</div>
                        <div className="flex items-center gap-4 text-sm">
                          <span className="text-yellow-400">{instance.slow_queries_count || 0} slow</span>
                          <span className="text-orange-400">{instance.locks_waiting || 0} locks</span>
                          <span className="text-red-400">{instance.deadlocks_count || 0} deadlocks</span>
                        </div>
                      </div>
                    </div>

                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          setSelectedInstance(instance.id);
                          setViewMode('queries');
                        }}
                        className="flex items-center gap-2 px-3 py-1.5 bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 rounded-lg text-sm transition-colors"
                      >
                        <Code className="w-4 h-4" />
                        View Queries
                      </button>
                      <button className="flex items-center gap-2 px-3 py-1.5 bg-muted/50 text-foreground hover:bg-muted rounded-lg text-sm transition-colors">
                        <BarChart3 className="w-4 h-4" />
                        View Metrics
                      </button>
                      <button className="flex items-center gap-2 px-3 py-1.5 bg-muted/50 text-foreground hover:bg-muted rounded-lg text-sm transition-colors">
                        <Settings className="w-4 h-4" />
                        Settings
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );

  // Render Queries View
  const renderQueriesView = () => (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search queries..."
            className="w-full pl-10 pr-4 py-2 bg-muted/50 border border-border/50 rounded-lg text-foreground placeholder-muted-foreground focus:outline-none focus:border-blue-500"
          />
        </div>
        <select
          value={selectedInstance || ''}
          onChange={(e) => setSelectedInstance(e.target.value || null)}
          className="px-4 py-2 bg-muted/50 border border-border/50 rounded-lg text-foreground focus:outline-none focus:border-blue-500"
        >
          <option value="">All Databases</option>
          {instances.map(inst => (
            <option key={inst.id} value={inst.id}>{inst.display_name || inst.name}</option>
          ))}
        </select>
      </div>

      <div className="bg-muted/50 rounded-xl border border-border/50 overflow-hidden">
        <table className="w-full">
          <thead className="bg-muted/50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Query</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Calls</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Total Time</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Avg Time</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Max Time</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Rows</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {queries
              .filter(q => !searchTerm || q.query_normalized?.toLowerCase().includes(searchTerm.toLowerCase()))
              .map(query => (
                <tr key={query.id} className="hover:bg-muted/20">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      {query.is_slow && (
                        <span className="px-1.5 py-0.5 bg-yellow-500/20 text-yellow-400 rounded text-xs">SLOW</span>
                      )}
                      <span className={`px-1.5 py-0.5 rounded text-xs ${
                        query.query_type === 'SELECT' ? 'bg-blue-500/20 text-blue-400' :
                        query.query_type === 'INSERT' ? 'bg-green-500/20 text-green-400' :
                        query.query_type === 'UPDATE' ? 'bg-orange-500/20 text-orange-400' :
                        query.query_type === 'DELETE' ? 'bg-red-500/20 text-red-400' :
                        'bg-secondary text-muted-foreground'
                      }`}>
                        {query.query_type || 'SQL'}
                      </span>
                    </div>
                    <div className="mt-1 font-mono text-sm text-foreground truncate max-w-md" title={query.query_normalized}>
                      {query.query_normalized || query.query_sample}
                    </div>
                    {query.database_name && (
                      <div className="text-xs text-muted-foreground mt-1">{query.database_name}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-foreground">
                    {query.call_count.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-foreground">
                    {formatMs(query.total_time_ms)}
                  </td>
                  <td className="px-4 py-3">
                    <span className={query.is_slow ? 'text-yellow-400' : 'text-foreground'}>
                      {formatMs(query.avg_time_ms)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-foreground">
                    {formatMs(query.max_time_ms)}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {query.avg_rows_returned?.toFixed(0) || '-'}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>

        {queries.length === 0 && (
          <div className="p-8 text-center">
            <Code className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">No query statistics available yet.</p>
          </div>
        )}
      </div>
    </div>
  );

  // Render Alerts View
  const renderAlertsView = () => (
    <div className="bg-muted/50 rounded-xl border border-border/50">
      {alerts.length === 0 ? (
        <div className="p-8 text-center">
          <CheckCircle className="w-12 h-12 text-green-400 mx-auto mb-4" />
          <h4 className="text-lg font-medium text-foreground mb-2">No Active Alerts</h4>
          <p className="text-muted-foreground">All database instances are operating normally.</p>
        </div>
      ) : (
        <div className="divide-y divide-border">
          {alerts.map(alert => (
            <div key={alert.id} className="p-4 hover:bg-muted/20">
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3">
                  {alert.severity === 'critical' ? (
                    <XCircle className="w-5 h-5 text-red-400 mt-0.5 flex-shrink-0" />
                  ) : (
                    <AlertCircle className="w-5 h-5 text-yellow-400 mt-0.5 flex-shrink-0" />
                  )}
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded text-xs flex-shrink-0 ${
                        alert.severity === 'critical' ? 'bg-red-500/20 text-red-400' : 'bg-yellow-500/20 text-yellow-400'
                      }`}>
                        {alert.severity}
                      </span>
                      <h4 className="font-medium text-foreground">{alert.title}</h4>
                    </div>
                    <p className="text-sm text-muted-foreground mt-1">{alert.message}</p>
                    <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                      <span>Type: {alert.alert_type}</span>
                      <span>{new Date(alert.triggered_at).toLocaleString()}</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button className="px-3 py-1 bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 rounded text-sm">
                    Acknowledge
                  </button>
                  <button className="px-3 py-1 bg-green-600/20 text-green-400 hover:bg-green-600/30 rounded text-sm">
                    Resolve
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-blue-400 animate-spin" />
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
              <div className="p-3 rounded-xl bg-indigo-500/10">
                <Database className="w-6 h-6 text-indigo-400" />
              </div>
              <div>
                <h1 className="text-base font-medium text-foreground">Database Monitoring</h1>
                <p className="text-muted-foreground text-sm">Monitor database health, performance, and queries</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              {selectedInstance && (
                <button
                  onClick={() => setSelectedInstance(null)}
                  className="px-3 py-1.5 text-muted-foreground hover:text-foreground"
                >
                  Clear Filter
                </button>
              )}
              <button
                onClick={() => {
                  fetchInstances();
                  fetchSummary();
                  fetchAlerts();
                }}
                className="p-2 text-muted-foreground hover:text-foreground hover:bg-muted/50 rounded-lg transition-colors"
              >
                <RefreshCw className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
      {/* Navigation Tabs */}
      <div className="flex items-center gap-1 mb-6 bg-muted/30 p-1 rounded-lg w-fit">
        {[
          { id: 'overview', label: 'Overview', icon: Activity },
          { id: 'queries', label: 'Queries', icon: Code },
          { id: 'alerts', label: 'Alerts', icon: AlertCircle, badge: alerts.length },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setViewMode(tab.id as ViewMode)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              viewMode === tab.id
                ? 'bg-blue-600 text-foreground'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
            {tab.badge && tab.badge > 0 && (
              <span className="px-1.5 py-0.5 bg-red-500 text-foreground text-xs rounded-full">
                {tab.badge}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      {viewMode === 'overview' && renderOverview()}
      {viewMode === 'queries' && renderQueriesView()}
      {viewMode === 'alerts' && renderAlertsView()}
      </div>

      {/* Add Instance Modal */}
      {showAddInstance && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-muted rounded-xl max-w-lg w-full">
            <div className="p-4 border-b border-border">
              <h3 className="text-lg font-semibold text-foreground">Add Database Instance</h3>
            </div>
            <div className="p-4">
              <p className="text-muted-foreground mb-4">
                To add a database for monitoring, install the OffCall database agent or configure direct connection.
              </p>
              <div className="space-y-4">
                <div className="bg-muted/50 rounded-lg p-4">
                  <div className="text-sm text-muted-foreground mb-2">Supported Databases:</div>
                  <div className="flex flex-wrap gap-2">
                    {['PostgreSQL', 'MySQL', 'MongoDB', 'Redis', 'Elasticsearch', 'MariaDB'].map(db => (
                      <span key={db} className="px-2 py-1 bg-muted/50 text-foreground rounded text-sm">
                        {db}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
              <div className="flex justify-end gap-2 mt-4">
                <button
                  onClick={() => setShowAddInstance(false)}
                  className="px-4 py-2 text-muted-foreground hover:text-foreground"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DatabaseMonitoring;
