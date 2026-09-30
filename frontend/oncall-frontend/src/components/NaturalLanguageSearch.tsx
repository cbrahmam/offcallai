// frontend/oncall-frontend/src/components/NaturalLanguageSearch.tsx
import React, { useState, useEffect, useRef } from 'react';
import {
  AlertTriangle,
  BellRing,
  ChevronRight,
  Clock,
  FileText,
  RefreshCw,
  Rocket,
  Search,
  Server,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  TrendingUp,
  X
} from 'lucide-react';
import { Input } from './ui/input';
import { useNotifications } from '../contexts/NotificationContext';

import { API_URL as API_BASE_URL } from '../config/api';

interface QueryResult {
  id: string;
  query_text: string;
  intent: string;
  confidence: number;
  status: string;
  result_count: number;
  result_summary?: string;
  result_data?: {
    hosts?: HostResult[];
    incidents?: IncidentResult[];
    alerts?: AlertResult[];
    logs?: LogResult[];
    traces?: TraceResult[];
    deployments?: DeploymentResult[];
  };
  execution_time_ms?: number;
  error_message?: string;
  feedback_helpful?: boolean;
  created_at: string;
}

interface HostResult {
  id: string;
  hostname: string;
  status: string;
  cpu_percent?: number;
  memory_percent?: number;
  disk_percent?: number;
  last_seen_at?: string;
}

interface IncidentResult {
  id: string;
  title: string;
  severity: string;
  status: string;
  created_at: string;
  resolved_at?: string;
}

interface AlertResult {
  id: string;
  title: string;
  severity: string;
  status: string;
  source: string;
  created_at: string;
}

interface LogResult {
  timestamp: string;
  level: string;
  message: string;
  service_name?: string;
  host_name?: string;
}

interface TraceResult {
  trace_id: string;
  service_name: string;
  operation_name: string;
  duration_ms: number;
  status: string;
  timestamp: string;
}

interface DeploymentResult {
  id: string;
  service_name: string;
  version: string;
  status: string;
  deployed_at: string;
  deployed_by?: string;
}

interface SuggestedQuery {
  query: string;
  description: string;
  intent: string;
}

interface NaturalLanguageSearchProps {
  onNavigateToHost?: (hostId: string) => void;
  onNavigateToIncident?: (incidentId: string) => void;
  onNavigateToAlert?: (alertId: string) => void;
  onNavigateToTrace?: (traceId: string) => void;
  onNavigateToDeployment?: (deploymentId: string) => void;
  isDemoMode?: boolean;
}

const NaturalLanguageSearch: React.FC<NaturalLanguageSearchProps> = ({
  onNavigateToHost,
  onNavigateToIncident,
  onNavigateToAlert,
  onNavigateToTrace,
  onNavigateToDeployment,
  isDemoMode = false,
}) => {
  const { showToast } = useNotifications();
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [suggestions, setSuggestions] = useState<SuggestedQuery[]>([]);
  const [recentQueries, setRecentQueries] = useState<QueryResult[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(true);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchSuggestions();
    fetchRecentQueries();
  }, []);

  const fetchSuggestions = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/query/suggestions`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      if (response.ok) {
        const data = await response.json();
        setSuggestions(data);
      }
    } catch (error) {
      console.error('Error fetching suggestions:', error);
    }
  };

  const fetchRecentQueries = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/query/history?limit=5`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      if (response.ok) {
        const data = await response.json();
        setRecentQueries(data);
      }
    } catch (error) {
      console.error('Error fetching recent queries:', error);
    }
  };

  const executeQuery = async (queryText: string) => {
    if (!queryText.trim()) return;

    setIsLoading(true);
    setShowSuggestions(false);

    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/query`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: queryText }),
      });

      if (response.ok) {
        const data = await response.json();
        setResult(data);
        fetchRecentQueries(); // Refresh recent queries
      } else {
        const error = await response.json();
        showToast({
          type: 'error',
          title: 'Query Failed',
          message: error.detail || 'Failed to process query',
          autoClose: true,
        });
      }
    } catch (error) {
      console.error('Error executing query:', error);
      showToast({
        type: 'error',
        title: 'Query Failed',
        message: 'Failed to process query',
        autoClose: true,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    executeQuery(query);
  };

  const handleSuggestionClick = (suggestion: SuggestedQuery) => {
    setQuery(suggestion.query);
    executeQuery(suggestion.query);
  };

  const handleRecentQueryClick = (recent: QueryResult) => {
    setQuery(recent.query_text);
    executeQuery(recent.query_text);
  };

  const submitFeedback = async (helpful: boolean) => {
    if (!result) return;

    try {
      const token = localStorage.getItem('access_token');
      await fetch(`${API_BASE_URL}/query/${result.id}/feedback`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ helpful }),
      });

      setResult({ ...result, feedback_helpful: helpful });
      showToast({
        type: 'success',
        title: 'Feedback Submitted',
        message: 'Thank you for your feedback!',
        autoClose: true,
      });
    } catch (error) {
      console.error('Error submitting feedback:', error);
    }
  };

  const getIntentIcon = (intent: string) => {
    switch (intent) {
      case 'host_status':
        return <Server className="w-5 h-5" />;
      case 'incident_lookup':
        return <AlertTriangle className="w-5 h-5" />;
      case 'alert_search':
        return <BellRing className="w-5 h-5" />;
      case 'log_search':
        return <FileText className="w-5 h-5" />;
      case 'trace_search':
        return <TrendingUp className="w-5 h-5" />;
      case 'deployment_lookup':
        return <Rocket className="w-5 h-5" />;
      default:
        return <Search className="w-5 h-5" />;
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical':
        return 'bg-red-500/10 text-red-400 border-red-500/20';
      case 'high':
        return 'bg-orange-500/10 text-orange-400 border-orange-500/20';
      case 'medium':
        return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20';
      case 'low':
        return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
      default:
        return 'bg-secondary text-muted-foreground border-border';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'active':
      case 'open':
      case 'success':
        return 'bg-emerald-500/10 text-emerald-400';
      case 'inactive':
      case 'resolved':
      case 'closed':
        return 'bg-secondary text-muted-foreground';
      case 'acknowledged':
      case 'in_progress':
        return 'bg-yellow-500/10 text-yellow-400';
      case 'failed':
        return 'bg-red-500/10 text-red-400';
      default:
        return 'bg-secondary text-muted-foreground';
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  const clearResults = () => {
    setResult(null);
    setShowSuggestions(true);
    setQuery('');
    inputRef.current?.focus();
  };

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-3 mb-4">
            <div className="w-12 h-12 bg-secondary rounded-xl flex items-center justify-center">
              <Sparkles className="w-7 h-7 text-foreground" />
            </div>
            <h1 className="text-2xl font-semibold text-foreground">AI Search</h1>
          </div>
          <p className="text-sm text-muted-foreground">
            Ask questions about your infrastructure in plain English
          </p>
        </div>

        {/* Search Input */}
        <div className="bg-transparent border border-border rounded-xl mb-6">
          <div className="p-4">
            <form onSubmit={handleSubmit} className="flex gap-3">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <Input
                  ref={inputRef}
                  type="text"
                  placeholder="Ask anything... e.g., 'Show me hosts with high memory usage'"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="pl-10 pr-4 h-12 text-base bg-secondary/30 border-border"
                />
              </div>
              <button
                type="submit"
                disabled={isLoading || !query.trim()}
                className="h-12 px-6 bg-primary text-primary-foreground font-medium rounded-lg hover:bg-white/90 transition-colors disabled:opacity-50 text-sm inline-flex items-center"
              >
                {isLoading ? (
                  <RefreshCw className="w-5 h-5 animate-spin" />
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 mr-2" />
                    Search
                  </>
                )}
              </button>
            </form>
          </div>
        </div>

        {/* Suggestions & Recent Queries */}
        {showSuggestions && !result && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            {/* Suggested Queries */}
            <div className="bg-transparent border border-border rounded-xl">
              <div className="p-6 pb-3">
                <h3 className="text-sm font-medium text-foreground flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-muted-foreground" />
                  Suggested Queries
                </h3>
              </div>
              <div className="p-6 pt-0 space-y-2">
                {suggestions.map((suggestion, index) => (
                  <button
                    key={index}
                    onClick={() => handleSuggestionClick(suggestion)}
                    className="w-full text-left p-3 rounded-lg bg-transparent hover:bg-accent transition-colors border border-transparent hover:border-border"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-muted-foreground">{getIntentIcon(suggestion.intent)}</span>
                      <span className="text-sm font-medium text-foreground">
                        {suggestion.query}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1 ml-7">
                      {suggestion.description}
                    </p>
                  </button>
                ))}
              </div>
            </div>

            {/* Recent Queries */}
            <div className="bg-transparent border border-border rounded-xl">
              <div className="p-6 pb-3">
                <h3 className="text-sm font-medium text-foreground flex items-center gap-2">
                  <Clock className="w-4 h-4 text-muted-foreground" />
                  Recent Queries
                </h3>
              </div>
              <div className="p-6 pt-0 space-y-2">
                {recentQueries.length > 0 ? (
                  recentQueries.map((recent, index) => (
                    <button
                      key={index}
                      onClick={() => handleRecentQueryClick(recent)}
                      className="w-full text-left p-3 rounded-lg bg-transparent hover:bg-accent transition-colors border border-transparent hover:border-border"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-muted-foreground">{getIntentIcon(recent.intent)}</span>
                          <span className="text-sm font-medium text-foreground line-clamp-1">
                            {recent.query_text}
                          </span>
                        </div>
                        <span className="text-xs px-2 py-0.5 rounded-full bg-secondary text-muted-foreground">
                          {recent.result_count} results
                        </span>
                      </div>
                    </button>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground text-center py-4">
                    No recent queries
                  </p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Results */}
        {result && (
          <div className="bg-transparent border border-border rounded-xl">
            <div className="p-6 pb-3">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-medium text-foreground flex items-center gap-2">
                  <span className="text-muted-foreground">{getIntentIcon(result.intent)}</span>
                  Results
                  <span className="text-xs px-2 py-0.5 rounded-full bg-secondary text-muted-foreground ml-2">
                    {result.result_count} found
                  </span>
                  {result.execution_time_ms && (
                    <span className="text-xs text-muted-foreground font-normal">
                      ({result.execution_time_ms}ms)
                    </span>
                  )}
                </h3>
                <button
                  onClick={clearResults}
                  className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              {result.result_summary && (
                <p className="text-sm text-muted-foreground mt-2">
                  {result.result_summary}
                </p>
              )}
            </div>

            <div className="p-6 pt-0 space-y-4">
              {/* Host Results */}
              {result.result_data?.hosts && result.result_data.hosts.length > 0 && (
                <div className="space-y-2">
                  {result.result_data.hosts.map((host) => (
                    <div
                      key={host.id}
                      onClick={() => onNavigateToHost?.(host.id)}
                      className="p-4 bg-transparent rounded-lg hover:bg-accent cursor-pointer transition-colors border border-border"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <Server className="w-5 h-5 text-muted-foreground" />
                          <div>
                            <h4 className="text-sm font-medium text-foreground">{host.hostname}</h4>
                            <span className={`text-xs px-2 py-0.5 rounded-full ${getStatusColor(host.status)}`}>
                              {host.status}
                            </span>
                          </div>
                        </div>
                        <div className="flex items-center gap-4 text-sm">
                          {host.cpu_percent !== undefined && (
                            <div>
                              <span className="text-muted-foreground">CPU:</span>
                              <span className={`ml-1 ${host.cpu_percent > 80 ? 'text-red-400' : 'text-foreground'}`}>
                                {host.cpu_percent.toFixed(1)}%
                              </span>
                            </div>
                          )}
                          {host.memory_percent !== undefined && (
                            <div>
                              <span className="text-muted-foreground">Memory:</span>
                              <span className={`ml-1 ${host.memory_percent > 80 ? 'text-red-400' : 'text-foreground'}`}>
                                {host.memory_percent.toFixed(1)}%
                              </span>
                            </div>
                          )}
                          {host.disk_percent !== undefined && (
                            <div>
                              <span className="text-muted-foreground">Disk:</span>
                              <span className={`ml-1 ${host.disk_percent > 80 ? 'text-red-400' : 'text-foreground'}`}>
                                {host.disk_percent.toFixed(1)}%
                              </span>
                            </div>
                          )}
                          <ChevronRight className="w-4 h-4 text-muted-foreground" />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Incident Results */}
              {result.result_data?.incidents && result.result_data.incidents.length > 0 && (
                <div className="space-y-2">
                  {result.result_data.incidents.map((incident) => (
                    <div
                      key={incident.id}
                      onClick={() => onNavigateToIncident?.(incident.id)}
                      className="p-4 bg-transparent rounded-lg hover:bg-accent cursor-pointer transition-colors border border-border"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <h4 className="text-sm font-medium text-foreground">{incident.title}</h4>
                          <div className="flex items-center gap-2 mt-1">
                            <span className={`text-xs px-2 py-0.5 rounded-full border ${getSeverityColor(incident.severity)}`}>
                              {incident.severity}
                            </span>
                            <span className={`text-xs px-2 py-0.5 rounded-full ${getStatusColor(incident.status)}`}>
                              {incident.status}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              {formatDate(incident.created_at)}
                            </span>
                          </div>
                        </div>
                        <ChevronRight className="w-4 h-4 text-muted-foreground" />
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Alert Results */}
              {result.result_data?.alerts && result.result_data.alerts.length > 0 && (
                <div className="space-y-2">
                  {result.result_data.alerts.map((alert) => (
                    <div
                      key={alert.id}
                      onClick={() => onNavigateToAlert?.(alert.id)}
                      className="p-4 bg-transparent rounded-lg hover:bg-accent cursor-pointer transition-colors border border-border"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <h4 className="text-sm font-medium text-foreground">{alert.title}</h4>
                          <div className="flex items-center gap-2 mt-1">
                            <span className={`text-xs px-2 py-0.5 rounded-full border ${getSeverityColor(alert.severity)}`}>
                              {alert.severity}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              Source: {alert.source}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              {formatDate(alert.created_at)}
                            </span>
                          </div>
                        </div>
                        <ChevronRight className="w-4 h-4 text-muted-foreground" />
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Log Results */}
              {result.result_data?.logs && result.result_data.logs.length > 0 && (
                <div className="space-y-2">
                  {result.result_data.logs.slice(0, 20).map((log, index) => (
                    <div
                      key={index}
                      className="p-3 bg-secondary/30 border border-border rounded-lg font-mono text-sm"
                    >
                      <div className="flex items-start gap-2">
                        <span
                          className={`text-xs px-2 py-0.5 rounded-full ${
                            log.level === 'ERROR' ? 'bg-red-500/10 text-red-400' :
                            log.level === 'WARN' || log.level === 'WARNING' ? 'bg-yellow-500/10 text-yellow-400' :
                            'bg-blue-500/10 text-blue-400'
                          }`}
                        >
                          {log.level}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {formatDate(log.timestamp)}
                        </span>
                        {log.service_name && (
                          <span className="text-xs text-muted-foreground">
                            [{log.service_name}]
                          </span>
                        )}
                      </div>
                      <p className="text-foreground mt-1 break-all">{log.message}</p>
                    </div>
                  ))}
                  {result.result_data.logs.length > 20 && (
                    <p className="text-sm text-muted-foreground text-center">
                      Showing 20 of {result.result_data.logs.length} logs
                    </p>
                  )}
                </div>
              )}

              {/* Trace Results */}
              {result.result_data?.traces && result.result_data.traces.length > 0 && (
                <div className="space-y-2">
                  {result.result_data.traces.map((trace) => (
                    <div
                      key={trace.trace_id}
                      onClick={() => onNavigateToTrace?.(trace.trace_id)}
                      className="p-4 bg-transparent rounded-lg hover:bg-accent cursor-pointer transition-colors border border-border"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <h4 className="text-sm font-medium text-foreground">{trace.operation_name}</h4>
                            <span className="text-xs px-2 py-0.5 rounded-full bg-secondary text-muted-foreground">
                              {trace.service_name}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 mt-1">
                            <span className={`text-sm font-medium ${trace.duration_ms > 1000 ? 'text-red-400' : trace.duration_ms > 500 ? 'text-yellow-400' : 'text-emerald-400'}`}>
                              {trace.duration_ms.toFixed(0)}ms
                            </span>
                            <span className="text-xs text-muted-foreground">
                              {formatDate(trace.timestamp)}
                            </span>
                          </div>
                        </div>
                        <ChevronRight className="w-4 h-4 text-muted-foreground" />
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Deployment Results */}
              {result.result_data?.deployments && result.result_data.deployments.length > 0 && (
                <div className="space-y-2">
                  {result.result_data.deployments.map((deployment) => (
                    <div
                      key={deployment.id}
                      onClick={() => onNavigateToDeployment?.(deployment.id)}
                      className="p-4 bg-transparent rounded-lg hover:bg-accent cursor-pointer transition-colors border border-border"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <Rocket className="w-5 h-5 text-blue-400" />
                          <div>
                            <h4 className="text-sm font-medium text-foreground">
                              {deployment.service_name}
                              <span className="text-muted-foreground ml-2">v{deployment.version}</span>
                            </h4>
                            <div className="flex items-center gap-2 mt-1">
                              <span className={`text-xs px-2 py-0.5 rounded-full ${getStatusColor(deployment.status)}`}>
                                {deployment.status}
                              </span>
                              {deployment.deployed_by && (
                                <span className="text-xs text-muted-foreground">
                                  by {deployment.deployed_by}
                                </span>
                              )}
                              <span className="text-xs text-muted-foreground">
                                {formatDate(deployment.deployed_at)}
                              </span>
                            </div>
                          </div>
                        </div>
                        <ChevronRight className="w-4 h-4 text-muted-foreground" />
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* No Results */}
              {result.result_count === 0 && (
                <div className="text-center py-8">
                  <Search className="w-12 h-12 mx-auto text-muted-foreground mb-3" />
                  <p className="text-sm text-muted-foreground">No results found</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Try adjusting your query or time range
                  </p>
                </div>
              )}

              {/* Error State */}
              {result.status === 'failed' && result.error_message && (
                <div className="text-center py-8">
                  <AlertTriangle className="w-12 h-12 mx-auto text-red-400 mb-3" />
                  <p className="text-sm text-red-400">{result.error_message}</p>
                </div>
              )}

              {/* Feedback Section */}
              {result.result_count > 0 && result.feedback_helpful === undefined && (
                <div className="flex items-center justify-center gap-4 pt-4 border-t border-border">
                  <span className="text-sm text-muted-foreground">Were these results helpful?</span>
                  <button
                    onClick={() => submitFeedback(true)}
                    className="px-3 py-1.5 border border-border rounded-lg text-emerald-400 hover:bg-emerald-500/10 transition-colors text-sm inline-flex items-center"
                  >
                    <ThumbsUp className="w-4 h-4 mr-1" />
                    Yes
                  </button>
                  <button
                    onClick={() => submitFeedback(false)}
                    className="px-3 py-1.5 border border-border rounded-lg text-red-400 hover:bg-red-500/10 transition-colors text-sm inline-flex items-center"
                  >
                    <ThumbsDown className="w-4 h-4 mr-1" />
                    No
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default NaturalLanguageSearch;
