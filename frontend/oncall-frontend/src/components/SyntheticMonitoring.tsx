// frontend/oncall-frontend/src/components/SyntheticMonitoring.tsx
import React, { useState, useEffect } from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Clock,
  Code,
  Edit2,
  ExternalLink,
  Eye,
  Filter,
  Globe,
  Loader2,
  MapPin,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Search,
  Server,
  Settings,
  Shield,
  Trash2,
  TrendingUp,
  Wifi,
  XCircle
} from 'lucide-react';

import { API_URL as API_BASE_URL } from '../config/api';

interface SyntheticCheck {
  id: string;
  name: string;
  description: string | null;
  check_type: string;
  status: string;
  target_url: string;
  method: string;
  interval_seconds: number;
  timeout_seconds: number;
  locations: string[];
  current_status: string;
  last_check_at: string | null;
  consecutive_failures: number;
  consecutive_successes: number;
  uptime_percentage_24h: number | null;
  avg_response_time_24h: number | null;
  total_checks_24h: number;
  failed_checks_24h: number;
  created_at: string;
}

interface SyntheticCheckResult {
  id: string;
  check_id: string;
  status: string;
  location: string | null;
  executed_at: string;
  response_time_ms: number | null;
  status_code: number | null;
  error_message: string | null;
  assertions_passed: number;
  assertions_failed: number;
}

interface SyntheticLocation {
  id: string;
  code: string;
  name: string;
  region: string | null;
  country: string | null;
  active: boolean;
}

interface SyntheticStats {
  total_checks: number;
  active_checks: number;
  paused_checks: number;
  checks_up: number;
  checks_down: number;
  checks_degraded: number;
  total_executions_24h: number;
  successful_executions_24h: number;
  failed_executions_24h: number;
  avg_uptime_24h: number;
  avg_response_time_24h: number;
  open_incidents: number;
}

type TabType = 'overview' | 'checks' | 'results' | 'locations';

const SyntheticMonitoring: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [checks, setChecks] = useState<SyntheticCheck[]>([]);
  const [results, setResults] = useState<SyntheticCheckResult[]>([]);
  const [locations, setLocations] = useState<SyntheticLocation[]>([]);
  const [stats, setStats] = useState<SyntheticStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreateCheck, setShowCreateCheck] = useState(false);
  const [expandedCheck, setExpandedCheck] = useState<string | null>(null);
  const [runningCheck, setRunningCheck] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState<string>('');
  const [filterStatus, setFilterStatus] = useState<string>('');

  const getAuthHeaders = () => {
    const token = localStorage.getItem('access_token');
    return {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    };
  };

  useEffect(() => {
    fetchData();
  }, [activeTab]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const headers = getAuthHeaders();

      if (activeTab === 'overview' || activeTab === 'checks') {
        let statsLoaded = false;
        let checksLoaded = false;
        let locsLoaded = false;

        try {
          const [statsRes, checksRes, locsRes] = await Promise.all([
            fetch(`${API_BASE_URL}/synthetic/stats`, { headers }),
            fetch(`${API_BASE_URL}/synthetic/checks?page_size=100`, { headers }),
            fetch(`${API_BASE_URL}/synthetic/locations`, { headers })
          ]);

          if (statsRes.ok) {
            const statsData = await statsRes.json();
            if (statsData && statsData.total_checks > 0) {
              setStats(statsData);
              statsLoaded = true;
            }
          }

          if (checksRes.ok) {
            const checksData = await checksRes.json();
            if (checksData.items && checksData.items.length > 0) {
              setChecks(checksData.items);
              checksLoaded = true;
            }
          }

          if (locsRes.ok) {
            const locsData = await locsRes.json();
            if (locsData.items && locsData.items.length > 0) {
              setLocations(locsData.items);
              locsLoaded = true;
            }
          }
        } catch (err) {
          console.error('Error fetching overview/checks data:', err);
        }

        // Use empty data as fallback for any data not loaded
        if (!statsLoaded) setStats(null);
        if (!checksLoaded) setChecks([]);
        if (!locsLoaded) setLocations([]);
      }

      if (activeTab === 'results') {
        try {
          const resultsRes = await fetch(`${API_BASE_URL}/synthetic/results?page_size=100`, { headers });
          if (resultsRes.ok) {
            const resultsData = await resultsRes.json();
            setResults(resultsData.items || []);
          } else {
            setResults([]);
          }
        } catch (err) {
          console.error('Error fetching results:', err);
          setResults([]);
        }
      }

      if (activeTab === 'locations') {
        try {
          const locsRes = await fetch(`${API_BASE_URL}/synthetic/locations`, { headers });
          if (locsRes.ok) {
            const locsData = await locsRes.json();
            setLocations(locsData.items || []);
          } else {
            setLocations([]);
          }
        } catch (err) {
          console.error('Error fetching locations:', err);
          setLocations([]);
        }
      }
    } catch (error) {
      console.error('Error fetching synthetic data:', error);
      // Use empty data on complete failure
      setStats(null);
      setChecks([]);
      setResults([]);
      setLocations([]);
    } finally {
      setLoading(false);
    }
  };

  const toggleCheck = async (checkId: string, status: string) => {
    try {
      const res = await fetch(
        `${API_BASE_URL}/synthetic/checks/${checkId}/toggle?status=${status}`,
        { method: 'POST', headers: getAuthHeaders() }
      );
      if (res.ok) {
        fetchData();
      }
    } catch (error) {
      console.error('Error toggling check:', error);
    }
  };

  const runCheck = async (checkId: string) => {
    setRunningCheck(checkId);
    try {
      const res = await fetch(
        `${API_BASE_URL}/synthetic/checks/${checkId}/run`,
        { method: 'POST', headers: getAuthHeaders() }
      );
      if (res.ok) {
        fetchData();
      }
    } catch (error) {
      console.error('Error running check:', error);
    } finally {
      setRunningCheck(null);
    }
  };

  const deleteCheck = async (checkId: string) => {
    if (!window.confirm('Are you sure you want to delete this check?')) return;
    try {
      const res = await fetch(`${API_BASE_URL}/synthetic/checks/${checkId}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });
      if (res.ok) {
        fetchData();
      }
    } catch (error) {
      console.error('Error deleting check:', error);
    }
  };

  const getCheckTypeIcon = (type: string) => {
    const icons: Record<string, React.ReactNode> = {
      'http': <Globe className="w-4 h-4" />,
      'api': <Code className="w-4 h-4" />,
      'browser': <ExternalLink className="w-4 h-4" />,
      'tcp': <Wifi className="w-4 h-4" />,
      'dns': <Server className="w-4 h-4" />,
      'ssl': <Shield className="w-4 h-4" />
    };
    return icons[type] || <Globe className="w-4 h-4" />;
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      'up': 'bg-green-500/20 text-green-400',
      'down': 'bg-red-500/20 text-red-400',
      'degraded': 'bg-yellow-500/20 text-yellow-400',
      'unknown': 'bg-secondary text-muted-foreground',
      'success': 'bg-green-500/20 text-green-400',
      'failure': 'bg-red-500/20 text-red-400',
      'timeout': 'bg-orange-500/20 text-orange-400',
      'error': 'bg-red-500/20 text-red-400',
      'active': 'bg-green-500/20 text-green-400',
      'paused': 'bg-yellow-500/20 text-yellow-400',
      'disabled': 'bg-secondary text-muted-foreground'
    };
    return colors[status] || 'bg-secondary text-muted-foreground';
  };

  const formatDuration = (ms: number | null) => {
    if (!ms) return '-';
    if (ms < 1000) return `${Math.round(ms)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const formatInterval = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
    return `${Math.floor(seconds / 3600)}h`;
  };

  const filteredChecks = checks.filter(check => {
    if (searchTerm && !check.name.toLowerCase().includes(searchTerm.toLowerCase()) &&
        !check.target_url.toLowerCase().includes(searchTerm.toLowerCase())) {
      return false;
    }
    if (filterType && check.check_type !== filterType) return false;
    if (filterStatus && check.current_status !== filterStatus) return false;
    return true;
  });

  const renderOverview = () => (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-muted/50 rounded-xl p-4 border border-border/50">
          <div className="flex items-center gap-3 mb-2">
            <Globe className="w-5 h-5 text-blue-400" />
            <span className="text-muted-foreground text-sm">Active Checks</span>
          </div>
          <div className="text-2xl font-bold text-foreground">
            {stats?.active_checks || 0}
            <span className="text-sm text-muted-foreground ml-2">/ {stats?.total_checks || 0}</span>
          </div>
        </div>

        <div className="bg-muted/50 rounded-xl p-4 border border-border/50">
          <div className="flex items-center gap-3 mb-2">
            <CheckCircle className="w-5 h-5 text-green-400" />
            <span className="text-muted-foreground text-sm">Checks Up</span>
          </div>
          <div className="flex items-baseline gap-3">
            <span className="text-2xl font-bold text-green-400">{stats?.checks_up || 0}</span>
            <span className="text-xs text-yellow-400">{stats?.checks_degraded || 0} degraded</span>
            <span className="text-xs text-red-400">{stats?.checks_down || 0} down</span>
          </div>
        </div>

        <div className="bg-muted/50 rounded-xl p-4 border border-border/50">
          <div className="flex items-center gap-3 mb-2">
            <TrendingUp className="w-5 h-5 text-green-400" />
            <span className="text-muted-foreground text-sm">Avg Uptime (24h)</span>
          </div>
          <div className="text-2xl font-bold text-foreground">
            {stats?.avg_uptime_24h?.toFixed(2) || 100}%
          </div>
        </div>

        <div className="bg-muted/50 rounded-xl p-4 border border-border/50">
          <div className="flex items-center gap-3 mb-2">
            <Activity className="w-5 h-5 text-blue-400" />
            <span className="text-muted-foreground text-sm">Avg Response Time</span>
          </div>
          <div className="text-2xl font-bold text-foreground">
            {formatDuration(stats?.avg_response_time_24h || 0)}
          </div>
        </div>
      </div>

      {/* Checks Grid */}
      <div className="bg-muted/50 rounded-xl border border-border/50">
        <div className="p-4 border-b border-border/50 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-foreground">Monitored Endpoints</h3>
          <button
            onClick={() => setShowCreateCheck(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-foreground text-sm"
          >
            <Plus className="w-4 h-4" />
            Add Check
          </button>
        </div>
        <div className="divide-y divide-border">
          {checks.slice(0, 10).map((check) => (
            <div key={check.id} className="p-4 hover:bg-muted/50">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-3 h-3 rounded-full ${
                    check.current_status === 'up' ? 'bg-green-500' :
                    check.current_status === 'down' ? 'bg-red-500' :
                    check.current_status === 'degraded' ? 'bg-yellow-500' : 'bg-muted'
                  }`} />
                  {getCheckTypeIcon(check.check_type)}
                  <div>
                    <div className="text-foreground font-medium">{check.name}</div>
                    <div className="text-sm text-muted-foreground truncate max-w-md">{check.target_url}</div>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <div className="text-foreground">{formatDuration(check.avg_response_time_24h)}</div>
                    <div className="text-sm text-muted-foreground">avg response</div>
                  </div>
                  <div className="text-right">
                    <div className="text-foreground">{check.uptime_percentage_24h?.toFixed(2) || 100}%</div>
                    <div className="text-sm text-muted-foreground">uptime</div>
                  </div>
                  <span className={`px-2 py-1 rounded-full text-xs ${getStatusColor(check.status)}`}>
                    {check.status}
                  </span>
                </div>
              </div>
            </div>
          ))}
          {checks.length === 0 && (
            <div className="p-8 text-center text-muted-foreground">
              No synthetic checks configured. Click "Add Check" to start monitoring your endpoints.
            </div>
          )}
        </div>
      </div>

      {/* Recent Results */}
      {results.length > 0 && (
        <div className="bg-muted/50 rounded-xl border border-border/50">
          <div className="p-4 border-b border-border/50">
            <h3 className="text-lg font-semibold text-foreground">Recent Results</h3>
          </div>
          <div className="divide-y divide-border max-h-64 overflow-y-auto">
            {results.slice(0, 20).map((result) => (
              <div key={result.id} className="p-3 flex items-center justify-between text-sm">
                <div className="flex items-center gap-3">
                  <span className={`w-2 h-2 rounded-full ${
                    result.status === 'success' ? 'bg-green-500' : 'bg-red-500'
                  }`} />
                  <span className="text-muted-foreground">
                    {new Date(result.executed_at).toLocaleTimeString()}
                  </span>
                  <span className="text-foreground">{result.location || 'default'}</span>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-foreground">{formatDuration(result.response_time_ms)}</span>
                  {result.status_code && (
                    <span className={`${result.status_code < 400 ? 'text-green-400' : 'text-red-400'}`}>
                      {result.status_code}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );

  const renderChecks = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-foreground">Synthetic Checks</h2>
        <button
          onClick={() => setShowCreateCheck(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-foreground"
        >
          <Plus className="w-4 h-4" />
          Create Check
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search checks..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-muted border border-border rounded-lg pl-10 pr-4 py-2 text-foreground placeholder-muted-foreground"
          />
        </div>
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="bg-muted border border-border rounded-lg px-4 py-2 text-foreground"
        >
          <option value="">All Types</option>
          <option value="http">HTTP</option>
          <option value="api">API</option>
          <option value="browser">Browser</option>
          <option value="tcp">TCP</option>
          <option value="dns">DNS</option>
          <option value="ssl">SSL</option>
        </select>
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="bg-muted border border-border rounded-lg px-4 py-2 text-foreground"
        >
          <option value="">All Status</option>
          <option value="up">Up</option>
          <option value="down">Down</option>
          <option value="degraded">Degraded</option>
        </select>
      </div>

      {/* Checks List */}
      <div className="bg-muted/50 rounded-xl border border-border/50">
        <div className="divide-y divide-border">
          {filteredChecks.map((check) => (
            <div key={check.id} className="p-4">
              <div
                className="flex items-center justify-between cursor-pointer"
                onClick={() => setExpandedCheck(expandedCheck === check.id ? null : check.id)}
              >
                <div className="flex items-center gap-3">
                  {expandedCheck === check.id ? (
                    <ChevronDown className="w-5 h-5 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="w-5 h-5 text-muted-foreground" />
                  )}
                  <div className={`w-3 h-3 rounded-full ${
                    check.current_status === 'up' ? 'bg-green-500' :
                    check.current_status === 'down' ? 'bg-red-500' :
                    check.current_status === 'degraded' ? 'bg-yellow-500' : 'bg-muted'
                  }`} />
                  {getCheckTypeIcon(check.check_type)}
                  <div>
                    <div className="text-foreground font-medium">{check.name}</div>
                    <div className="text-sm text-muted-foreground">{check.target_url}</div>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-right text-sm">
                    <div className="text-foreground">{formatDuration(check.avg_response_time_24h)}</div>
                    <div className="text-muted-foreground">Every {formatInterval(check.interval_seconds)}</div>
                  </div>
                  <span className={`px-2 py-1 rounded-full text-xs ${getStatusColor(check.status)}`}>
                    {check.status}
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      runCheck(check.id);
                    }}
                    disabled={runningCheck === check.id}
                    className="p-2 hover:bg-blue-500/20 rounded text-blue-400"
                    title="Run now"
                  >
                    {runningCheck === check.id ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Play className="w-4 h-4" />
                    )}
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleCheck(check.id, check.status === 'active' ? 'paused' : 'active');
                    }}
                    className={`p-2 hover:bg-muted rounded ${
                      check.status === 'active' ? 'text-yellow-400' : 'text-green-400'
                    }`}
                    title={check.status === 'active' ? 'Pause' : 'Resume'}
                  >
                    {check.status === 'active' ? (
                      <Pause className="w-4 h-4" />
                    ) : (
                      <Play className="w-4 h-4" />
                    )}
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteCheck(check.id);
                    }}
                    className="p-2 hover:bg-red-500/20 rounded text-red-400"
                    title="Delete"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {expandedCheck === check.id && (
                <div className="mt-4 pl-10 space-y-4">
                  <div className="grid grid-cols-4 gap-4">
                    <div className="bg-muted rounded-lg p-3">
                      <div className="text-muted-foreground text-sm">Uptime (24h)</div>
                      <div className="text-xl font-bold text-foreground">
                        {check.uptime_percentage_24h?.toFixed(2) || 100}%
                      </div>
                    </div>
                    <div className="bg-muted rounded-lg p-3">
                      <div className="text-muted-foreground text-sm">Checks (24h)</div>
                      <div className="text-xl font-bold text-foreground">
                        {check.total_checks_24h}
                        <span className="text-sm text-red-400 ml-2">{check.failed_checks_24h} failed</span>
                      </div>
                    </div>
                    <div className="bg-muted rounded-lg p-3">
                      <div className="text-muted-foreground text-sm">Consecutive</div>
                      <div className="text-xl font-bold">
                        {check.consecutive_failures > 0 ? (
                          <span className="text-red-400">{check.consecutive_failures} failures</span>
                        ) : (
                          <span className="text-green-400">{check.consecutive_successes} successes</span>
                        )}
                      </div>
                    </div>
                    <div className="bg-muted rounded-lg p-3">
                      <div className="text-muted-foreground text-sm">Last Check</div>
                      <div className="text-foreground">
                        {check.last_check_at ? new Date(check.last_check_at).toLocaleString() : 'Never'}
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">Method:</span>
                      <span className="text-foreground ml-2">{check.method}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Timeout:</span>
                      <span className="text-foreground ml-2">{check.timeout_seconds}s</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Locations:</span>
                      <span className="text-foreground ml-2">{check.locations.length || 'All'}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Type:</span>
                      <span className="text-foreground ml-2">{check.check_type.toUpperCase()}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
          {filteredChecks.length === 0 && (
            <div className="p-8 text-center text-muted-foreground">
              No checks found matching your criteria.
            </div>
          )}
        </div>
      </div>
    </div>
  );

  const renderResults = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-foreground">Check Results</h2>
        <button
          onClick={fetchData}
          className="flex items-center gap-2 px-4 py-2 bg-muted hover:bg-muted/80 rounded-lg text-foreground"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      <div className="bg-muted/50 rounded-xl border border-border/50 overflow-hidden">
        <table className="w-full">
          <thead className="bg-muted/50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Status</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Location</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Response Time</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Status Code</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Assertions</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Time</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {results.map((result) => (
              <tr key={result.id} className="hover:bg-muted/20">
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs ${getStatusColor(result.status)}`}>
                    {result.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-foreground">{result.location || 'default'}</td>
                <td className="px-4 py-3 text-foreground">{formatDuration(result.response_time_ms)}</td>
                <td className="px-4 py-3">
                  {result.status_code && (
                    <span className={`${result.status_code < 400 ? 'text-green-400' : 'text-red-400'}`}>
                      {result.status_code}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span className="text-green-400">{result.assertions_passed}</span>
                  <span className="text-muted-foreground mx-1">/</span>
                  <span className="text-red-400">{result.assertions_failed}</span>
                </td>
                <td className="px-4 py-3 text-muted-foreground text-sm">
                  {new Date(result.executed_at).toLocaleString()}
                </td>
              </tr>
            ))}
            {results.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                  No results yet. Run a check to see results here.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );

  const renderLocations = () => (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold text-foreground">Check Locations</h2>
      <p className="text-muted-foreground">Available locations for running synthetic checks from around the world.</p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {locations.map((location) => (
          <div
            key={location.id}
            className="bg-muted/50 rounded-xl border border-border/50 p-4"
          >
            <div className="flex items-center gap-3">
              <MapPin className="w-5 h-5 text-blue-400" />
              <div>
                <h3 className="text-foreground font-medium">{location.name}</h3>
                <p className="text-muted-foreground text-sm">{location.region}</p>
              </div>
            </div>
            <div className="mt-3 flex items-center justify-between">
              <span className="text-muted-foreground text-sm">{location.country}</span>
              <span className={`px-2 py-1 rounded text-xs ${
                location.active ? 'bg-green-500/20 text-green-400' : 'bg-secondary text-muted-foreground'
              }`}>
                {location.active ? 'Active' : 'Inactive'}
              </span>
            </div>
          </div>
        ))}
        {locations.length === 0 && (
          <div className="col-span-3 bg-muted/50 rounded-xl border border-border/50 p-8 text-center text-muted-foreground">
            No locations available.
          </div>
        )}
      </div>
    </div>
  );

  // Create Check Modal
  const CreateCheckModal = () => {
    const [formData, setFormData] = useState({
      name: '',
      description: '',
      check_type: 'http',
      target_url: '',
      method: 'GET',
      interval_seconds: 60,
      timeout_seconds: 30,
      locations: [] as string[]
    });

    const handleSubmit = async (e: React.FormEvent) => {
      e.preventDefault();
      try {
        const res = await fetch(`${API_BASE_URL}/synthetic/checks`, {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify(formData)
        });
        if (res.ok) {
          setShowCreateCheck(false);
          fetchData();
        }
      } catch (error) {
        console.error('Error creating check:', error);
      }
    };

    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-muted/50 rounded-lg border border-border w-full max-w-lg mx-4">
          <div className="p-4 border-b border-border flex items-center justify-between">
            <h3 className="text-lg font-medium text-foreground">Create Synthetic Check</h3>
            <button
              onClick={() => setShowCreateCheck(false)}
              className="text-muted-foreground hover:text-foreground"
            >
              <XCircle className="w-5 h-5" />
            </button>
          </div>
          <form onSubmit={handleSubmit} className="p-4 space-y-4">
            <div>
              <label className="block text-sm text-muted-foreground mb-1">Check Name</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full bg-muted border border-border rounded px-3 py-2 text-foreground"
                placeholder="API Health Check"
                required
              />
            </div>

            <div>
              <label className="block text-sm text-muted-foreground mb-1">Target URL</label>
              <input
                type="url"
                value={formData.target_url}
                onChange={(e) => setFormData({ ...formData, target_url: e.target.value })}
                className="w-full bg-muted border border-border rounded px-3 py-2 text-foreground"
                placeholder="https://api.example.com/health"
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-muted-foreground mb-1">Check Type</label>
                <select
                  value={formData.check_type}
                  onChange={(e) => setFormData({ ...formData, check_type: e.target.value })}
                  className="w-full bg-muted border border-border rounded px-3 py-2 text-foreground"
                >
                  <option value="http">HTTP</option>
                  <option value="api">API</option>
                  <option value="tcp">TCP</option>
                  <option value="dns">DNS</option>
                  <option value="ssl">SSL Certificate</option>
                </select>
              </div>

              <div>
                <label className="block text-sm text-muted-foreground mb-1">Method</label>
                <select
                  value={formData.method}
                  onChange={(e) => setFormData({ ...formData, method: e.target.value })}
                  className="w-full bg-muted border border-border rounded px-3 py-2 text-foreground"
                >
                  <option value="GET">GET</option>
                  <option value="POST">POST</option>
                  <option value="PUT">PUT</option>
                  <option value="DELETE">DELETE</option>
                  <option value="HEAD">HEAD</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-muted-foreground mb-1">Check Interval</label>
                <select
                  value={formData.interval_seconds}
                  onChange={(e) => setFormData({ ...formData, interval_seconds: parseInt(e.target.value) })}
                  className="w-full bg-muted border border-border rounded px-3 py-2 text-foreground"
                >
                  <option value="30">Every 30 seconds</option>
                  <option value="60">Every 1 minute</option>
                  <option value="300">Every 5 minutes</option>
                  <option value="600">Every 10 minutes</option>
                  <option value="1800">Every 30 minutes</option>
                  <option value="3600">Every 1 hour</option>
                </select>
              </div>

              <div>
                <label className="block text-sm text-muted-foreground mb-1">Timeout</label>
                <select
                  value={formData.timeout_seconds}
                  onChange={(e) => setFormData({ ...formData, timeout_seconds: parseInt(e.target.value) })}
                  className="w-full bg-muted border border-border rounded px-3 py-2 text-foreground"
                >
                  <option value="10">10 seconds</option>
                  <option value="30">30 seconds</option>
                  <option value="60">60 seconds</option>
                  <option value="120">2 minutes</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-sm text-muted-foreground mb-1">Description (optional)</label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="w-full bg-muted border border-border rounded px-3 py-2 text-foreground"
                rows={2}
              />
            </div>

            <div className="flex justify-end gap-3 pt-4 border-t border-border">
              <button
                type="button"
                onClick={() => setShowCreateCheck(false)}
                className="px-4 py-2 bg-muted hover:bg-muted/80 rounded text-foreground"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded text-foreground"
              >
                Create Check
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Colorful Header */}
      <div className="relative overflow-hidden border-b border-border">

        <div className="relative max-w-7xl mx-auto px-6 py-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-teal-500/10">
                <Globe className="w-6 h-6 text-teal-400" />
              </div>
              <div>
                <h1 className="text-base font-medium text-foreground">Synthetic Monitoring</h1>
                <p className="text-muted-foreground text-sm">Proactive monitoring with HTTP, API, and browser checks</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
      {/* Tabs */}
      <div className="border-b border-border mb-6">
        <nav className="flex gap-6">
          {[
            { id: 'overview', label: 'Overview', icon: Activity },
            { id: 'checks', label: 'Checks', icon: Globe },
            { id: 'results', label: 'Results', icon: Clock },
            { id: 'locations', label: 'Locations', icon: MapPin },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as TabType)}
              className={`flex items-center gap-2 pb-3 px-1 border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-400'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
        </div>
      ) : (
        <>
          {activeTab === 'overview' && renderOverview()}
          {activeTab === 'checks' && renderChecks()}
          {activeTab === 'results' && renderResults()}
          {activeTab === 'locations' && renderLocations()}
        </>
      )}

      </div>

      {/* Modals */}
      {showCreateCheck && <CreateCheckModal />}
    </div>
  );
};

export default SyntheticMonitoring;
