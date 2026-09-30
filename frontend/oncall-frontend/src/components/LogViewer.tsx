// frontend/oncall-frontend/src/components/LogViewer.tsx
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { API_URL as API_BASE } from '../config/api';
import {
  AlertCircle,
  AlertTriangle,
  Bug,
  ChevronDown,
  ChevronUp,
  Clock,
  Download,
  ExternalLink,
  FileText,
  Filter,
  Info,
  Pause,
  Play,
  RefreshCw,
  Search,
  Server,
  Settings,
  X
} from 'lucide-react';

interface LogEntry {
  id: string;
  timestamp: string;
  level: string;
  source?: string;
  service?: string;
  filename?: string;
  line_number?: number;
  message: string;
  fields: Record<string, any>;
  tags: string[];
  host_id: string;
  hostname?: string;
}

interface LogStats {
  total_logs: number;
  time_range_hours: number;
  by_level: Array<{ level: string; count: number }>;
  by_source: Array<{ source: string; count: number }>;
  logs_per_hour: Array<{ hour: string; count: number }>;
}


const LOG_LEVELS = ['trace', 'debug', 'info', 'warn', 'error', 'fatal'];

const getLevelColor = (level: string) => {
  const colors: Record<string, string> = {
    trace: 'text-muted-foreground',
    debug: 'text-blue-400',
    info: 'text-emerald-400',
    warn: 'text-yellow-400',
    error: 'text-orange-400',
    fatal: 'text-red-400',
  };
  return colors[level.toLowerCase()] || 'text-muted-foreground';
};

const getLevelBg = (level: string) => {
  const colors: Record<string, string> = {
    trace: 'bg-accent',
    debug: 'bg-blue-500/10',
    info: 'bg-emerald-500/10',
    warn: 'bg-yellow-500/10',
    error: 'bg-orange-500/10',
    fatal: 'bg-red-500/10',
  };
  return colors[level.toLowerCase()] || 'bg-accent';
};

const getLevelIcon = (level: string) => {
  const icons: Record<string, React.ReactNode> = {
    trace: <Bug className="h-4 w-4" />,
    debug: <Bug className="h-4 w-4" />,
    info: <Info className="h-4 w-4" />,
    warn: <AlertTriangle className="h-4 w-4" />,
    error: <AlertCircle className="h-4 w-4" />,
    fatal: <AlertCircle className="h-4 w-4" />,
  };
  return icons[level.toLowerCase()] || <Info className="h-4 w-4" />;
};

interface LogViewerProps {
  isDemoMode?: boolean;
}

export default function LogViewer({ isDemoMode = false }: LogViewerProps) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [stats, setStats] = useState<LogStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [query, setQuery] = useState('');
  const [selectedLevels, setSelectedLevels] = useState<string[]>([]);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [timeRange, setTimeRange] = useState('1h');
  const [showFilters, setShowFilters] = useState(false);

  // Live tail
  const [liveTail, setLiveTail] = useState(false);
  const liveTailInterval = useRef<NodeJS.Timeout | null>(null);

  // Expanded log
  const [expandedLogId, setExpandedLogId] = useState<string | null>(null);

  // Available sources
  const [availableSources, setAvailableSources] = useState<string[]>([]);

  const logContainerRef = useRef<HTMLDivElement>(null);

  const fetchLogs = useCallback(async () => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 8000);

    try {
      const token = localStorage.getItem('access_token');
      const now = new Date();
      const rangeHours: Record<string, number> = {
        '15m': 0.25, '1h': 1, '6h': 6, '24h': 24, '7d': 168
      };
      const hours = rangeHours[timeRange] || 1;
      const start = new Date(now.getTime() - hours * 60 * 60 * 1000);

      const params = new URLSearchParams({
        start: start.toISOString(),
        end: now.toISOString(),
        limit: '200',
        order: 'desc'
      });

      if (query) params.append('q', query);
      if (selectedLevels.length) params.append('levels', selectedLevels.join(','));
      if (selectedSources.length) params.append('sources', selectedSources.join(','));

      const response = await fetch(`${API_BASE}/logs/search?${params}`, {
        headers: { 'Authorization': `Bearer ${token}` },
        signal: controller.signal,
      });

      if (!response.ok) throw new Error('Failed to fetch logs');
      const data = await response.json();
      setLogs(data.logs || []);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        setError(null);
        setLogs([]);
      } else {
        setError(err instanceof Error ? err.message : 'Failed to load logs');
      }
    } finally {
      clearTimeout(timeoutId);
      setLoading(false);
    }
  }, [query, selectedLevels, selectedSources, timeRange]);

  const fetchStats = async () => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 8000);
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE}/logs/stats/summary?hours=24`, {
        headers: { 'Authorization': `Bearer ${token}` },
        signal: controller.signal,
      });
      if (!response.ok) throw new Error('Failed to fetch stats');
      const data = await response.json();
      setStats(data);
      setAvailableSources(data.by_source?.map((s: any) => s.source) || []);
    } catch (err) {
      if (!(err instanceof DOMException && err.name === 'AbortError')) {
        console.error('Failed to fetch log stats:', err);
      }
    } finally {
      clearTimeout(timeoutId);
    }
  };

  useEffect(() => {
    fetchLogs();
    fetchStats();
  }, [fetchLogs]);

  useEffect(() => {
    if (liveTail) {
      liveTailInterval.current = setInterval(fetchLogs, 3000);
    } else if (liveTailInterval.current) {
      clearInterval(liveTailInterval.current);
      liveTailInterval.current = null;
    }
    return () => {
      if (liveTailInterval.current) {
        clearInterval(liveTailInterval.current);
      }
    };
  }, [liveTail, fetchLogs]);

  const toggleLevel = (level: string) => {
    setSelectedLevels(prev =>
      prev.includes(level)
        ? prev.filter(l => l !== level)
        : [...prev, level]
    );
  };

  const toggleSource = (source: string) => {
    setSelectedSources(prev =>
      prev.includes(source)
        ? prev.filter(s => s !== source)
        : [...prev, source]
    );
  };

  const formatTimestamp = (ts: string) => {
    const date = new Date(ts);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const formatDate = (ts: string) => {
    const date = new Date(ts);
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  if (loading) {
    return (
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-[20px] font-semibold text-foreground flex items-center gap-2">
              <FileText className="h-7 w-7 text-muted-foreground" />
              Log Viewer
            </h1>
            <p className="text-muted-foreground mt-1 text-sm">
              Search and analyze logs from all your infrastructure
            </p>
          </div>
        </div>
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header */}
      <div className="border-b border-border">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-emerald-500/10">
                <FileText className="w-6 h-6 text-emerald-400" />
              </div>
              <div>
                <h1 className="text-base font-medium text-foreground">Log Viewer</h1>
                <p className="text-muted-foreground text-sm">Search and analyze logs from all your infrastructure</p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setLiveTail(!liveTail)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all text-sm ${
                  liveTail
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    : 'bg-accent text-foreground border border-border hover:bg-secondary'
                }`}
              >
                {liveTail ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                {liveTail ? 'Stop Tail' : 'Live Tail'}
              </button>
              <button
                onClick={fetchLogs}
                className="p-2 text-muted-foreground hover:text-foreground hover:bg-accent rounded-lg transition-colors"
                title="Refresh"
              >
                <RefreshCw className={`h-5 w-5 ${liveTail ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 max-w-7xl mx-auto px-6 py-6 space-y-6 w-full">

      {error && (
        <div className="bg-red-500/10 border border-red-500/20 text-red-400 px-4 py-3 rounded-lg text-sm">
          {error}
          <button onClick={() => setError(null)} className="ml-2">
            <X className="h-4 w-4 inline" />
          </button>
        </div>
      )}

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div className="bg-transparent rounded-lg p-3 border border-border">
            <div className="text-xl font-bold text-foreground">{stats.total_logs.toLocaleString()}</div>
            <div className="text-xs uppercase tracking-wider text-muted-foreground">Total (24h)</div>
          </div>
          {stats.by_level.slice(0, 4).map((level) => (
            <div
              key={level.level}
              className={`bg-transparent rounded-lg p-3 border border-border cursor-pointer hover:bg-accent/50 ${
                selectedLevels.includes(level.level) ? 'ring-1 ring-white/20' : ''
              }`}
              onClick={() => toggleLevel(level.level)}
            >
              <div className={`text-xl font-bold ${getLevelColor(level.level)}`}>
                {level.count.toLocaleString()}
              </div>
              <div className="text-xs uppercase tracking-wider text-muted-foreground capitalize">{level.level}</div>
            </div>
          ))}
        </div>
      )}

      {/* Search & Filters */}
      <div className="bg-transparent rounded-lg border border-border p-4">
        <div className="flex items-center gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && fetchLogs()}
              placeholder="Search logs..."
              className="w-full pl-10 pr-4 py-2 bg-accent border border-border rounded-lg text-sm text-foreground placeholder-muted-foreground focus:border-white/20 focus:ring-1 focus:ring-primary/30 focus:outline-none"
            />
          </div>

          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            className="px-3 py-2 bg-accent border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
          >
            <option value="15m">Last 15 min</option>
            <option value="1h">Last hour</option>
            <option value="6h">Last 6 hours</option>
            <option value="24h">Last 24 hours</option>
            <option value="7d">Last 7 days</option>
          </select>

          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-colors text-sm ${
              showFilters || selectedLevels.length || selectedSources.length
                ? 'bg-primary text-primary-foreground'
                : 'bg-accent text-foreground border border-border hover:bg-secondary'
            }`}
          >
            <Filter className="h-4 w-4" />
            Filters
            {(selectedLevels.length + selectedSources.length) > 0 && (
              <span className="bg-black/20 px-1.5 py-0.5 rounded text-xs">
                {selectedLevels.length + selectedSources.length}
              </span>
            )}
          </button>

          <button
            onClick={fetchLogs}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-white/90 transition-colors text-sm"
          >
            Search
          </button>
        </div>

        {/* Filter Panel */}
        {showFilters && (
          <div className="mt-4 pt-4 border-t border-border grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-2">Log Levels</label>
              <div className="flex flex-wrap gap-2">
                {LOG_LEVELS.map((level) => (
                  <button
                    key={level}
                    onClick={() => toggleLevel(level)}
                    className={`px-3 py-1 rounded text-sm capitalize transition-colors ${
                      selectedLevels.includes(level)
                        ? `${getLevelBg(level)} ${getLevelColor(level)} ring-1 ring-current`
                        : 'bg-accent text-muted-foreground hover:bg-secondary'
                    }`}
                  >
                    {level}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-2">Sources</label>
              <div className="flex flex-wrap gap-2">
                {availableSources.slice(0, 8).map((source) => (
                  <button
                    key={source}
                    onClick={() => toggleSource(source)}
                    className={`px-3 py-1 rounded text-sm transition-colors ${
                      selectedSources.includes(source)
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-accent text-muted-foreground hover:bg-secondary'
                    }`}
                  >
                    {source}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Log List */}
      <div
        ref={logContainerRef}
        className="flex-1 bg-transparent rounded-lg border border-border overflow-auto font-mono text-sm"
        style={{ minHeight: '400px', maxHeight: 'calc(100vh - 400px)' }}
      >
        {logs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
            <FileText className="h-12 w-12 mb-4 opacity-50" />
            <p className="text-sm">No logs found matching your criteria</p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {logs.map((log) => (
              <div
                key={log.id}
                className={`hover:bg-accent/50 cursor-pointer transition-colors ${
                  expandedLogId === log.id ? 'bg-accent' : ''
                }`}
                onClick={() => setExpandedLogId(expandedLogId === log.id ? null : log.id)}
              >
                <div className="flex items-start gap-3 px-4 py-2">
                  {/* Timestamp */}
                  <div className="text-muted-foreground whitespace-nowrap flex-shrink-0 w-20">
                    {formatTimestamp(log.timestamp)}
                  </div>

                  {/* Level */}
                  <div className={`flex-shrink-0 w-16 ${getLevelColor(log.level)}`}>
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded ${getLevelBg(log.level)}`}>
                      {getLevelIcon(log.level)}
                      <span className="uppercase text-xs">{log.level}</span>
                    </span>
                  </div>

                  {/* Source & Host */}
                  <div className="flex-shrink-0 w-32 text-muted-foreground truncate">
                    {log.source || log.service || '-'}
                  </div>

                  {/* Hostname */}
                  <div className="flex-shrink-0 w-24 text-muted-foreground truncate">
                    {log.hostname || '-'}
                  </div>

                  {/* Message */}
                  <div className="flex-1 text-foreground break-all">
                    {log.message.length > 200 && expandedLogId !== log.id
                      ? `${log.message.substring(0, 200)}...`
                      : log.message}
                  </div>
                </div>

                {/* Expanded View */}
                {expandedLogId === log.id && (
                  <div className="px-4 py-3 bg-secondary/50 border-t border-border">
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <span className="text-muted-foreground">Timestamp:</span>
                        <span className="text-foreground ml-2">
                          {new Date(log.timestamp).toLocaleString()}
                        </span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Host:</span>
                        <span className="text-foreground ml-2">{log.hostname || log.host_id}</span>
                      </div>
                      {log.filename && (
                        <div>
                          <span className="text-muted-foreground">File:</span>
                          <span className="text-foreground ml-2">
                            {log.filename}
                            {log.line_number && `:${log.line_number}`}
                          </span>
                        </div>
                      )}
                      {log.service && (
                        <div>
                          <span className="text-muted-foreground">Service:</span>
                          <span className="text-foreground ml-2">{log.service}</span>
                        </div>
                      )}
                    </div>

                    {log.tags.length > 0 && (
                      <div className="mt-2">
                        <span className="text-muted-foreground text-sm">Tags:</span>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {log.tags.map((tag, i) => (
                            <span key={i} className="px-2 py-0.5 bg-accent border border-border rounded text-xs text-muted-foreground">
                              {tag}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {Object.keys(log.fields).length > 0 && (
                      <div className="mt-3">
                        <span className="text-muted-foreground text-sm">Fields:</span>
                        <pre className="mt-1 p-2 bg-accent border border-border rounded text-xs text-foreground overflow-auto">
                          {JSON.stringify(log.fields, null, 2)}
                        </pre>
                      </div>
                    )}

                    <div className="mt-3 p-2 bg-accent border border-border rounded">
                      <span className="text-muted-foreground text-xs">Full Message:</span>
                      <pre className="mt-1 text-foreground whitespace-pre-wrap break-all text-sm">
                        {log.message}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>Showing {logs.length} logs</span>
        {liveTail && (
          <span className="flex items-center gap-2 text-emerald-400">
            <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></span>
            Live tail active - refreshing every 3s
          </span>
        )}
      </div>
      </div>
    </div>
  );
}
