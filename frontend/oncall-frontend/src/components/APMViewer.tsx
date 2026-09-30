// frontend/oncall-frontend/src/components/APMViewer.tsx
import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Box,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Clock,
  Filter,
  Layers,
  RefreshCw,
  Search,
  Server,
  XCircle,
  Zap
} from 'lucide-react';

import { API_URL as API_BASE_URL } from '../config/api';

interface TraceSummary {
  id: string;
  trace_id: string;
  root_service: string | null;
  root_operation: string | null;
  start_time: string;
  duration_ms: number | null;
  span_count: number;
  error_count: number;
  has_error: boolean;
  services: string[];
}

interface Span {
  id: string;
  trace_id: string;
  span_id: string;
  parent_span_id: string | null;
  service_name: string;
  operation_name: string;
  span_kind: string;
  start_time: string;
  end_time: string | null;
  duration_ms: number | null;
  status: string;
  status_message: string | null;
  resource_attributes: Record<string, any>;
  attributes: Record<string, any>;
  events: any[];
  links: any[];
}

interface TraceDetail {
  id: string;
  trace_id: string;
  root_service: string | null;
  root_operation: string | null;
  start_time: string;
  end_time: string | null;
  duration_ms: number | null;
  span_count: number;
  service_count: number;
  error_count: number;
  has_error: boolean;
  services: string[];
  spans: Span[];
  tags: Record<string, any>;
}

interface ServiceSummary {
  service_name: string;
  request_count: number;
  error_count: number;
  error_rate: number;
  latency_avg: number;
  latency_p50: number;
  latency_p95: number;
  latency_p99: number;
  requests_per_second: number;
  upstream_services: string[];
  downstream_services: string[];
}

interface ServiceNode {
  service_name: string;
  request_count: number;
  error_rate: number;
  latency_avg: number;
}

interface ServiceEdge {
  source: string;
  target: string;
  request_count: number;
  error_rate: number;
  latency_avg: number;
}

interface ServiceMap {
  nodes: ServiceNode[];
  edges: ServiceEdge[];
}

type TabType = 'traces' | 'services' | 'service-map';

interface APMViewerProps {
  isDemoMode?: boolean;
}

export default function APMViewer({ isDemoMode = false }: APMViewerProps) {
  const [activeTab, setActiveTab] = useState<TabType>('traces');
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [selectedTrace, setSelectedTrace] = useState<TraceDetail | null>(null);
  const [services, setServices] = useState<ServiceSummary[]>([]);
  const [serviceMap, setServiceMap] = useState<ServiceMap | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [serviceFilter, setServiceFilter] = useState('');
  const [operationFilter, setOperationFilter] = useState('');
  const [minDuration, setMinDuration] = useState('');
  const [hasError, setHasError] = useState<boolean | null>(null);
  const [timeRange, setTimeRange] = useState('1h');

  // Pagination
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const getAuthHeaders = useCallback(() => {
    const token = localStorage.getItem('access_token');
    return {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  }, []);

  const getTimeRange = useCallback(() => {
    const now = new Date();
    const hours = parseInt(timeRange.replace('h', '').replace('d', '')) * (timeRange.includes('d') ? 24 : 1);
    const start = new Date(now.getTime() - hours * 60 * 60 * 1000);
    return { start: start.toISOString(), end: now.toISOString() };
  }, [timeRange]);

  const fetchWithTimeout = useCallback(async (url: string, options: RequestInit = {}) => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch(url, { ...options, signal: controller.signal });
      return response;
    } finally {
      clearTimeout(timeoutId);
    }
  }, []);

  const fetchTraces = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const { start, end } = getTimeRange();
      const params = new URLSearchParams({
        start_time: start,
        end_time: end,
        limit: limit.toString(),
        offset: offset.toString(),
      });

      if (serviceFilter) params.append('service', serviceFilter);
      if (operationFilter) params.append('operation', operationFilter);
      if (minDuration) params.append('min_duration_ms', minDuration);
      if (hasError !== null) params.append('has_error', hasError.toString());

      const response = await fetchWithTimeout(`${API_BASE_URL}/traces/search?${params}`, {
        headers: getAuthHeaders(),
      });

      if (!response.ok) throw new Error('Failed to fetch traces');

      const data = await response.json();
      setTraces(data.traces || []);
      setTotal(data.total || 0);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        setError(null);
      } else {
        setError(err instanceof Error ? err.message : 'Failed to fetch traces');
      }
    } finally {
      setLoading(false);
    }
  }, [getAuthHeaders, getTimeRange, fetchWithTimeout, serviceFilter, operationFilter, minDuration, hasError, offset]);

  const fetchTraceDetail = useCallback(async (traceId: string) => {
    setLoading(true);
    try {
      const response = await fetchWithTimeout(`${API_BASE_URL}/traces/${traceId}`, {
        headers: getAuthHeaders(),
      });

      if (!response.ok) throw new Error('Failed to fetch trace detail');

      const data = await response.json();
      setSelectedTrace(data);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        setError(null);
      } else {
        setError(err instanceof Error ? err.message : 'Failed to fetch trace');
      }
    } finally {
      setLoading(false);
    }
  }, [getAuthHeaders, fetchWithTimeout]);

  const fetchServices = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const hours = parseInt(timeRange.replace('h', '').replace('d', '')) * (timeRange.includes('d') ? 24 : 1);
      const response = await fetchWithTimeout(`${API_BASE_URL}/traces/services/list?hours=${hours}`, {
        headers: getAuthHeaders(),
      });

      if (!response.ok) throw new Error('Failed to fetch services');

      const data = await response.json();
      setServices(data.services || []);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        setError(null);
      } else {
        setError(err instanceof Error ? err.message : 'Failed to fetch services');
      }
    } finally {
      setLoading(false);
    }
  }, [getAuthHeaders, fetchWithTimeout, timeRange]);

  const fetchServiceMap = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const hours = parseInt(timeRange.replace('h', '').replace('d', '')) * (timeRange.includes('d') ? 24 : 1);
      const response = await fetchWithTimeout(`${API_BASE_URL}/traces/services/map?hours=${hours}`, {
        headers: getAuthHeaders(),
      });

      if (!response.ok) throw new Error('Failed to fetch service map');

      const data = await response.json();
      setServiceMap(data);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        setError(null);
      } else {
        setError(err instanceof Error ? err.message : 'Failed to fetch service map');
      }
    } finally {
      setLoading(false);
    }
  }, [getAuthHeaders, fetchWithTimeout, timeRange]);

  useEffect(() => {
    if (activeTab === 'traces') {
      fetchTraces();
    } else if (activeTab === 'services') {
      fetchServices();
    } else if (activeTab === 'service-map') {
      fetchServiceMap();
    }
  }, [activeTab, fetchTraces, fetchServices, fetchServiceMap]);

  const formatDuration = (ms: number | null) => {
    if (ms === null) return '-';
    if (ms < 1) return `${(ms * 1000).toFixed(0)}us`;
    if (ms < 1000) return `${ms.toFixed(1)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const formatTime = (dateStr: string) => {
    return new Date(dateStr).toLocaleTimeString();
  };

  const renderTraceList = () => (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-3 p-4 bg-secondary/50 rounded-lg border border-border">
        <div className="flex-1 min-w-[200px]">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Filter by service..."
              value={serviceFilter}
              onChange={(e) => setServiceFilter(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-accent border border-border rounded-lg text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
            />
          </div>
        </div>
        <div className="flex-1 min-w-[200px]">
          <input
            type="text"
            placeholder="Filter by operation..."
            value={operationFilter}
            onChange={(e) => setOperationFilter(e.target.value)}
            className="w-full px-4 py-2 bg-accent border border-border rounded-lg text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
          />
        </div>
        <div className="w-32">
          <input
            type="number"
            placeholder="Min ms"
            value={minDuration}
            onChange={(e) => setMinDuration(e.target.value)}
            className="w-full px-4 py-2 bg-accent border border-border rounded-lg text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
          />
        </div>
        <select
          value={hasError === null ? '' : hasError.toString()}
          onChange={(e) => setHasError(e.target.value === '' ? null : e.target.value === 'true')}
          className="px-4 py-2 bg-accent border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
        >
          <option value="">All Status</option>
          <option value="true">Errors Only</option>
          <option value="false">Success Only</option>
        </select>
        <select
          value={timeRange}
          onChange={(e) => setTimeRange(e.target.value)}
          className="px-4 py-2 bg-accent border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
        >
          <option value="1h">Last 1 hour</option>
          <option value="6h">Last 6 hours</option>
          <option value="24h">Last 24 hours</option>
          <option value="7d">Last 7 days</option>
        </select>
        <button
          onClick={fetchTraces}
          className="px-4 py-2 bg-primary text-primary-foreground hover:bg-white/90 rounded-lg text-sm flex items-center gap-2"
        >
          <RefreshCw className="h-4 w-4" />
          Search
        </button>
      </div>

      {/* Trace list */}
      <div className="bg-transparent rounded-lg border border-border overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Trace</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Service</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Operation</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Duration</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Spans</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Status</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Time</th>
            </tr>
          </thead>
          <tbody>
            {traces.map((trace) => (
              <tr
                key={trace.id}
                onClick={() => fetchTraceDetail(trace.trace_id)}
                className="hover:bg-accent/50 cursor-pointer transition-colors border-b border-secondary/30"
              >
                <td className="px-4 py-3">
                  <span className="font-mono text-xs text-blue-400">{trace.trace_id.slice(0, 16)}...</span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Server className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm text-foreground">{trace.root_service || '-'}</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-sm text-muted-foreground">{trace.root_operation || '-'}</td>
                <td className="px-4 py-3 text-sm font-mono text-foreground">
                  {formatDuration(trace.duration_ms)}
                </td>
                <td className="px-4 py-3 text-sm text-muted-foreground">{trace.span_count}</td>
                <td className="px-4 py-3">
                  {trace.has_error ? (
                    <span className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs bg-red-500/10 text-red-400 border border-red-500/20">
                      <XCircle className="h-3 w-3" />
                      {trace.error_count} errors
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      <CheckCircle className="h-3 w-3" />
                      OK
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-sm text-muted-foreground">{formatTime(trace.start_time)}</td>
              </tr>
            ))}
          </tbody>
        </table>

        {traces.length === 0 && !loading && (
          <div className="py-12 text-center text-muted-foreground">
            <Activity className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p className="text-sm">No traces found</p>
            <p className="text-sm mt-1">Traces will appear here once your applications start sending spans</p>
          </div>
        )}
      </div>

      {/* Pagination */}
      {total > limit && (
        <div className="flex items-center justify-between px-4">
          <span className="text-sm text-muted-foreground">
            Showing {offset + 1}-{Math.min(offset + limit, total)} of {total} traces
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setOffset(Math.max(0, offset - limit))}
              disabled={offset === 0}
              className="px-3 py-1 bg-accent border border-border rounded text-sm text-foreground disabled:opacity-50 hover:bg-secondary"
            >
              Previous
            </button>
            <button
              onClick={() => setOffset(offset + limit)}
              disabled={offset + limit >= total}
              className="px-3 py-1 bg-accent border border-border rounded text-sm text-foreground disabled:opacity-50 hover:bg-secondary"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );

  const renderTraceDetail = () => {
    if (!selectedTrace) return null;

    // Build span tree
    const spanMap = new Map<string, Span>();
    const rootSpans: Span[] = [];

    selectedTrace.spans.forEach(span => {
      spanMap.set(span.span_id, span);
    });

    selectedTrace.spans.forEach(span => {
      if (!span.parent_span_id || !spanMap.has(span.parent_span_id)) {
        rootSpans.push(span);
      }
    });

    // Calculate timeline
    const traceStart = new Date(selectedTrace.start_time).getTime();
    const traceDuration = selectedTrace.duration_ms || 1;

    const SpanRow = ({ span, depth = 0 }: { span: Span; depth?: number }) => {
      const [expanded, setExpanded] = useState(true);
      const children = selectedTrace.spans.filter(s => s.parent_span_id === span.span_id);
      const hasChildren = children.length > 0;

      const spanStart = new Date(span.start_time).getTime();
      const offsetPercent = ((spanStart - traceStart) / traceDuration) * 100;
      const widthPercent = ((span.duration_ms || 0) / traceDuration) * 100;

      return (
        <>
          <tr className="hover:bg-accent/50">
            <td className="px-4 py-2" style={{ paddingLeft: `${depth * 20 + 16}px` }}>
              <div className="flex items-center gap-2">
                {hasChildren && (
                  <button onClick={() => setExpanded(!expanded)} className="p-0.5">
                    {expanded ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
                  </button>
                )}
                {!hasChildren && <div className="w-5" />}
                <span className={`text-xs px-2 py-0.5 rounded ${
                  span.span_kind === 'server' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' :
                  span.span_kind === 'client' ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20' :
                  'bg-accent text-muted-foreground border border-border'
                }`}>
                  {span.span_kind}
                </span>
                <span className="text-sm text-foreground truncate max-w-[200px]">{span.operation_name}</span>
              </div>
            </td>
            <td className="px-4 py-2 text-sm text-muted-foreground">{span.service_name}</td>
            <td className="px-4 py-2">
              <div className="relative h-4 bg-accent rounded overflow-hidden">
                <div
                  className={`absolute h-full rounded ${
                    span.status === 'error' ? 'bg-red-500' : 'bg-blue-500'
                  }`}
                  style={{
                    left: `${Math.min(offsetPercent, 100)}%`,
                    width: `${Math.max(widthPercent, 1)}%`
                  }}
                />
              </div>
            </td>
            <td className="px-4 py-2 text-sm font-mono text-foreground text-right">
              {formatDuration(span.duration_ms)}
            </td>
            <td className="px-4 py-2">
              {span.status === 'error' ? (
                <XCircle className="h-4 w-4 text-red-400" />
              ) : span.status === 'ok' ? (
                <CheckCircle className="h-4 w-4 text-emerald-400" />
              ) : (
                <div className="h-4 w-4 rounded-full bg-muted" />
              )}
            </td>
          </tr>
          {expanded && children.map(child => (
            <SpanRow key={child.span_id} span={child} depth={depth + 1} />
          ))}
        </>
      );
    };

    return (
      <div className="space-y-4">
        <button
          onClick={() => setSelectedTrace(null)}
          className="text-sm text-muted-foreground hover:text-foreground flex items-center gap-1"
        >
          <ChevronRight className="h-4 w-4 rotate-180" />
          Back to traces
        </button>

        {/* Trace header */}
        <div className="p-4 bg-secondary/50 rounded-lg border border-border">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-medium text-foreground">{selectedTrace.root_operation}</h3>
              <p className="text-sm text-muted-foreground font-mono">{selectedTrace.trace_id}</p>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-center">
                <p className="text-2xl font-bold text-foreground">{formatDuration(selectedTrace.duration_ms)}</p>
                <p className="text-xs uppercase tracking-wider text-muted-foreground">Duration</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-foreground">{selectedTrace.span_count}</p>
                <p className="text-xs uppercase tracking-wider text-muted-foreground">Spans</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-foreground">{selectedTrace.service_count}</p>
                <p className="text-xs uppercase tracking-wider text-muted-foreground">Services</p>
              </div>
              <div className="text-center">
                <p className={`text-2xl font-bold ${selectedTrace.error_count > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                  {selectedTrace.error_count}
                </p>
                <p className="text-xs uppercase tracking-wider text-muted-foreground">Errors</p>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {selectedTrace.services.map(svc => (
              <span key={svc} className="px-2 py-1 bg-accent border border-border rounded text-xs text-muted-foreground">
                {svc}
              </span>
            ))}
          </div>
        </div>

        {/* Span waterfall */}
        <div className="bg-transparent rounded-lg border border-border overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider w-1/4">Operation</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider w-1/6">Service</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Timeline</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider w-24">Duration</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-muted-foreground uppercase tracking-wider w-16">Status</th>
              </tr>
            </thead>
            <tbody>
              {rootSpans.map(span => (
                <SpanRow key={span.span_id} span={span} />
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  const renderServices = () => (
    <div className="space-y-4">
      {/* Time range selector */}
      <div className="flex justify-between items-center">
        <h3 className="text-base font-medium text-foreground">Service Metrics</h3>
        <div className="flex items-center gap-3">
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            className="px-4 py-2 bg-accent border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
          >
            <option value="1h">Last 1 hour</option>
            <option value="6h">Last 6 hours</option>
            <option value="24h">Last 24 hours</option>
            <option value="7d">Last 7 days</option>
          </select>
          <button
            onClick={fetchServices}
            className="p-2 bg-accent border border-border hover:bg-secondary rounded-lg"
          >
            <RefreshCw className="h-4 w-4 text-muted-foreground" />
          </button>
        </div>
      </div>

      {/* Services grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {services.map((service) => (
          <div key={service.service_name} className="p-4 bg-transparent rounded-lg border border-border">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Box className="h-5 w-5 text-muted-foreground" />
                <h4 className="text-sm font-medium text-foreground">{service.service_name}</h4>
              </div>
              {service.error_rate > 5 && (
                <AlertTriangle className="h-5 w-5 text-yellow-400" />
              )}
            </div>

            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-muted-foreground">Requests</p>
                <p className="text-xl font-semibold text-foreground">{service.request_count.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Error Rate</p>
                <p className={`text-xl font-semibold ${service.error_rate > 5 ? 'text-red-400' : 'text-emerald-400'}`}>
                  {service.error_rate.toFixed(2)}%
                </p>
              </div>
              <div>
                <p className="text-muted-foreground">Avg Latency</p>
                <p className="text-xl font-semibold text-foreground">{formatDuration(service.latency_avg)}</p>
              </div>
              <div>
                <p className="text-muted-foreground">P95 Latency</p>
                <p className="text-xl font-semibold text-foreground">{formatDuration(service.latency_p95)}</p>
              </div>
            </div>

            <div className="mt-3 pt-3 border-t border-border">
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>P50: {formatDuration(service.latency_p50)}</span>
                <span>P99: {formatDuration(service.latency_p99)}</span>
                <span>{service.requests_per_second.toFixed(2)} req/s</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {services.length === 0 && !loading && (
        <div className="py-12 text-center text-muted-foreground">
          <Layers className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p className="text-sm">No services found</p>
          <p className="text-sm mt-1">Services will appear here once traces are ingested</p>
        </div>
      )}
    </div>
  );

  const renderServiceMap = () => (
    <div className="space-y-4">
      {/* Time range selector */}
      <div className="flex justify-between items-center">
        <h3 className="text-base font-medium text-foreground">Service Dependency Map</h3>
        <div className="flex items-center gap-3">
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            className="px-4 py-2 bg-accent border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
          >
            <option value="1h">Last 1 hour</option>
            <option value="6h">Last 6 hours</option>
            <option value="24h">Last 24 hours</option>
            <option value="7d">Last 7 days</option>
          </select>
          <button
            onClick={fetchServiceMap}
            className="p-2 bg-accent border border-border hover:bg-secondary rounded-lg"
          >
            <RefreshCw className="h-4 w-4 text-muted-foreground" />
          </button>
        </div>
      </div>

      {/* Simple service map visualization */}
      <div className="p-6 bg-secondary/50 rounded-lg border border-border min-h-[400px]">
        {serviceMap && serviceMap.nodes.length > 0 ? (
          <div className="space-y-6">
            {/* Nodes */}
            <div className="flex flex-wrap gap-4 justify-center">
              {serviceMap.nodes.map((node) => (
                <div
                  key={node.service_name}
                  className={`p-4 rounded-lg border ${
                    node.error_rate > 5 ? 'border-red-500/20 bg-red-500/5' : 'border-border bg-secondary/50'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <Server className="h-5 w-5 text-muted-foreground" />
                    <span className="text-sm font-medium text-foreground">{node.service_name}</span>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    <p>{node.request_count.toLocaleString()} requests</p>
                    <p className={node.error_rate > 5 ? 'text-red-400' : ''}>
                      {node.error_rate.toFixed(2)}% errors
                    </p>
                    <p>Avg: {formatDuration(node.latency_avg)}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Edges list */}
            {serviceMap.edges.length > 0 && (
              <div className="mt-6">
                <h4 className="text-xs uppercase tracking-wider text-muted-foreground mb-3">Dependencies</h4>
                <div className="space-y-2">
                  {serviceMap.edges.map((edge, idx) => (
                    <div
                      key={idx}
                      className="flex items-center gap-3 p-3 bg-secondary/50 border border-border rounded-lg"
                    >
                      <span className="text-sm text-foreground">{edge.source}</span>
                      <ArrowRight className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm text-foreground">{edge.target}</span>
                      <span className="ml-auto text-xs text-muted-foreground">
                        {edge.request_count.toLocaleString()} calls
                      </span>
                      <span className={`text-xs ${edge.error_rate > 5 ? 'text-red-400' : 'text-muted-foreground'}`}>
                        {edge.error_rate.toFixed(2)}% errors
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {formatDuration(edge.latency_avg)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
            <Zap className="h-12 w-12 mb-4 opacity-50" />
            <p className="text-sm">No service dependencies found</p>
            <p className="text-sm mt-1">Dependencies will appear here once traces show cross-service calls</p>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl bg-pink-500/10">
              <Activity className="w-6 h-6 text-pink-400" />
            </div>
            <div>
              <h1 className="text-base font-medium text-foreground">APM / Distributed Tracing</h1>
              <p className="text-muted-foreground text-sm">Monitor application performance and trace requests</p>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">

      {/* Tabs */}
      <div className="flex border-b border-border mb-6">
        <button
          onClick={() => { setActiveTab('traces'); setSelectedTrace(null); }}
          className={`px-4 py-2 font-medium text-sm border-b-2 transition-colors ${
            activeTab === 'traces'
              ? 'border-white text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <Activity className="h-4 w-4 inline mr-2" />
          Traces
        </button>
        <button
          onClick={() => setActiveTab('services')}
          className={`px-4 py-2 font-medium text-sm border-b-2 transition-colors ${
            activeTab === 'services'
              ? 'border-white text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <Layers className="h-4 w-4 inline mr-2" />
          Services
        </button>
        <button
          onClick={() => setActiveTab('service-map')}
          className={`px-4 py-2 font-medium text-sm border-b-2 transition-colors ${
            activeTab === 'service-map'
              ? 'border-white text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <Zap className="h-4 w-4 inline mr-2" />
          Service Map
        </button>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 mb-4 text-sm">
          {error}
        </div>
      )}

      {/* Content */}
      {!loading && !error && (
        <>
          {selectedTrace ? renderTraceDetail() : (
            <>
              {activeTab === 'traces' && renderTraceList()}
              {activeTab === 'services' && renderServices()}
              {activeTab === 'service-map' && renderServiceMap()}
            </>
          )}
        </>
      )}
      </div>
    </div>
  );
}
