// frontend/src/components/AlertEnrichmentPanel.tsx
import React, { useState, useEffect } from 'react';
import {
  Activity,
  AlertCircle,
  ExternalLink,
  FileText,
  GitBranch,
  Info,
  TrendingUp,
  Zap
} from 'lucide-react';
import { API_URL } from '../config/api';

interface AlertEnrichment {
  alert_id: string;
  related_metrics: {
    [key: string]: {
      average: number;
      max: number;
      unit: string;
    };
  };
  related_logs: Array<{
    timestamp: string;
    message: string;
    level: string;
    host: string;
  }>;
  related_traces: Array<{
    resource: string;
    status_code: number;
    count: number;
  }>;
  dashboard_url?: string;
  logs_url?: string;
  traces_url?: string;
  runbook_url?: string;
  correlated_alerts: string[];
  correlation_score: number;
  correlation_reason: string;
  ai_severity_score: number;
  severity_confidence: number;
  original_severity: string;
  adjusted_severity: string;
  severity_factors: {
    [key: string]: {
      weight: number;
      value: number;
      description: string;
    };
  };
  processing_time_ms: number;
  enriched_at: string;
}

interface AlertEnrichmentPanelProps {
  alertId: string;
  onClose?: () => void;
}

export const AlertEnrichmentPanel: React.FC<AlertEnrichmentPanelProps> = ({
  alertId,
  onClose
}) => {
  const [enrichment, setEnrichment] = useState<AlertEnrichment | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'metrics' | 'logs' | 'traces' | 'correlation'>('metrics');

  useEffect(() => {
    fetchEnrichment();
  }, [alertId]);

  const fetchEnrichment = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_URL}/alerts/${alertId}/enrichment`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });

      if (!response.ok) {
        // Try to enrich if data doesn't exist
        const enrichResponse = await fetch(`${API_URL}/alerts/${alertId}/enrich`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
          }
        });

        if (enrichResponse.ok) {
          const data = await enrichResponse.json();
          setEnrichment(data);
        } else {
          throw new Error('Failed to fetch enrichment');
        }
      } else {
        const data = await response.json();
        setEnrichment(data);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const getSeverityBadgeColor = (severity: string) => {
    const colors: Record<string, string> = {
      critical: 'bg-red-500/10 text-red-400 border border-red-500/20',
      high: 'bg-orange-500/10 text-orange-400 border border-orange-500/20',
      warning: 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20',
      info: 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
    };
    return colors[severity] || 'bg-blue-500/10 text-blue-400 border border-blue-500/20';
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-emerald-400';
    if (confidence >= 0.6) return 'text-yellow-400';
    return 'text-orange-400';
  };

  if (loading) {
    return (
      <div className="bg-transparent border border-border rounded-xl p-6 animate-pulse">
        <div className="h-8 bg-secondary rounded w-1/3 mb-4"></div>
        <div className="space-y-3">
          <div className="h-4 bg-secondary rounded"></div>
          <div className="h-4 bg-secondary rounded w-5/6"></div>
          <div className="h-4 bg-secondary rounded w-4/6"></div>
        </div>
      </div>
    );
  }

  if (error || !enrichment) {
    return (
      <div className="bg-transparent border border-border rounded-xl p-6">
        <div className="flex items-center gap-2 text-red-400">
          <AlertCircle size={20} />
          <span className="text-sm">Failed to load enrichment data: {error}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-transparent border border-border rounded-xl overflow-hidden">
      {/* Header with Severity Score */}
      <div className="p-6 border-b border-border">
        <div className="mb-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-medium text-foreground flex items-center gap-2">
              <div className="p-2 rounded-xl bg-secondary">
                <Zap className="text-foreground" size={20} />
              </div>
              Alert Enrichment
            </h3>
            {onClose && (
              <button
                onClick={onClose}
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                ✕
              </button>
            )}
          </div>
        </div>

        {/* AI Severity Analysis */}
        <div className="bg-transparent border border-border rounded-xl p-4 mb-4">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-2">
                <span className="text-sm text-muted-foreground">AI Severity Score:</span>
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${getSeverityBadgeColor(enrichment.adjusted_severity)}`}>
                    {enrichment.adjusted_severity.toUpperCase()}
                  </span>
                  <span className="text-2xl font-bold text-foreground">
                    {enrichment.ai_severity_score}/100
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-2 mb-3">
                <span className="text-sm text-muted-foreground">Confidence:</span>
                <span className={`text-sm font-semibold ${getConfidenceColor(enrichment.severity_confidence)}`}>
                  {(enrichment.severity_confidence * 100).toFixed(0)}%
                </span>
                <div className="flex-1 bg-secondary rounded-full h-2">
                  <div
                    className="h-2 rounded-full bg-white/20 transition-all"
                    style={{ width: `${enrichment.severity_confidence * 100}%` }}
                  ></div>
                </div>
              </div>

              {enrichment.original_severity !== enrichment.adjusted_severity && (
                <div className="text-sm text-muted-foreground flex items-center gap-1">
                  <TrendingUp size={14} />
                  Adjusted from <span className={`mx-1 text-xs px-2 py-0.5 rounded-full ${getSeverityBadgeColor(enrichment.original_severity)}`}>
                    {enrichment.original_severity}
                  </span> to <span className={`mx-1 text-xs px-2 py-0.5 rounded-full ${getSeverityBadgeColor(enrichment.adjusted_severity)}`}>
                    {enrichment.adjusted_severity}
                  </span>
                </div>
              )}
            </div>

            {/* Severity Factors Tooltip */}
            <div className="relative group">
              <Info size={20} className="text-muted-foreground cursor-help" />
              <div className="absolute right-0 top-8 w-80 bg-background backdrop-blur-xl border border-border rounded-xl p-4 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none group-hover:pointer-events-auto z-10">
                <h4 className="text-sm font-medium text-foreground mb-2">Severity Factors:</h4>
                <div className="space-y-2">
                  {Object.entries(enrichment.severity_factors).map(([key, factor]) => (
                    <div key={key} className="text-xs">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-foreground">{factor.description}</span>
                        <span className="text-muted-foreground font-semibold">+{factor.value}</span>
                      </div>
                      <div className="bg-secondary rounded-full h-1">
                        <div
                          className="bg-white/20 h-1 rounded-full"
                          style={{ width: `${(factor.value / 20) * 100}%` }}
                        ></div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Drill-Down Links */}
        <div className="flex flex-wrap gap-2">
          {enrichment.dashboard_url && (
            <a
              href={enrichment.dashboard_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 px-3 py-1.5 bg-blue-500/10 text-blue-400 rounded-lg hover:bg-blue-500/20 transition-colors text-sm border border-blue-500/20"
            >
              <Activity size={16} />
              Dashboard
              <ExternalLink size={12} />
            </a>
          )}
          {enrichment.logs_url && (
            <a
              href={enrichment.logs_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 px-3 py-1.5 bg-emerald-500/10 text-emerald-400 rounded-lg hover:bg-emerald-500/20 transition-colors text-sm border border-emerald-500/20"
            >
              <FileText size={16} />
              Logs
              <ExternalLink size={12} />
            </a>
          )}
          {enrichment.traces_url && (
            <a
              href={enrichment.traces_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 px-3 py-1.5 bg-violet-500/10 text-violet-400 rounded-lg hover:bg-violet-500/20 transition-colors text-sm border border-violet-500/20"
            >
              <GitBranch size={16} />
              Traces
              <ExternalLink size={12} />
            </a>
          )}
          {enrichment.runbook_url && (
            <a
              href={enrichment.runbook_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 px-3 py-1.5 bg-yellow-500/10 text-yellow-400 rounded-lg hover:bg-yellow-500/20 transition-colors text-sm border border-yellow-500/20"
            >
              <FileText size={16} />
              Runbook
              <ExternalLink size={12} />
            </a>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border">
        {[
          { key: 'metrics', label: 'Metrics', icon: Activity },
          { key: 'logs', label: 'Logs', icon: FileText },
          { key: 'traces', label: 'Traces', icon: GitBranch },
          { key: 'correlation', label: 'Correlated Alerts', icon: AlertCircle, badge: enrichment.correlated_alerts.length }
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as any)}
            className={`flex items-center gap-2 px-6 py-3 text-sm font-medium transition-colors relative ${
              activeTab === tab.key
                ? 'text-foreground bg-secondary border-b-2 border-white'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            <tab.icon size={18} />
            {tab.label}
            {tab.badge && tab.badge > 0 && (
              <span className="text-xs px-1.5 py-0.5 rounded-full bg-secondary text-foreground">
                {tab.badge}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="p-6">
        {activeTab === 'metrics' && (
          <div className="space-y-4">
            {Object.keys(enrichment.related_metrics).length === 0 ? (
              <div className="text-center text-muted-foreground py-8 text-sm">
                No metrics data available
              </div>
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {Object.entries(enrichment.related_metrics).map(([key, metric]) => (
                  typeof metric === 'object' && 'average' in metric && (
                    <div key={key} className="bg-transparent border border-border rounded-xl p-4">
                      <div className="text-xs uppercase tracking-wider text-muted-foreground mb-1">
                        {key.replace(/_/g, ' ')}
                      </div>
                      <div className="text-2xl font-bold text-foreground mb-1">
                        {metric.average.toFixed(2)}
                        <span className="text-sm text-muted-foreground ml-1">{metric.unit}</span>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Max: {metric.max.toFixed(2)} {metric.unit}
                      </div>
                    </div>
                  )
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'logs' && (
          <div className="space-y-2">
            {enrichment.related_logs.length === 0 ? (
              <div className="text-center text-muted-foreground py-8 text-sm">
                No logs available
              </div>
            ) : (
              enrichment.related_logs.map((log, idx) => (
                <div key={idx} className="bg-transparent border border-border rounded-xl p-3 font-mono text-sm">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs text-muted-foreground">{new Date(log.timestamp).toLocaleString()}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                      log.level === 'error' ? 'bg-red-500/10 text-red-400' :
                      log.level === 'warn' ? 'bg-yellow-500/10 text-yellow-400' :
                      'bg-blue-500/10 text-blue-400'
                    }`}>
                      {log.level}
                    </span>
                    <span className="text-xs text-muted-foreground">{log.host}</span>
                  </div>
                  <div className="text-foreground">{log.message}</div>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'traces' && (
          <div className="space-y-2">
            {enrichment.related_traces.length === 0 ? (
              <div className="text-center text-muted-foreground py-8 text-sm">
                No traces available
              </div>
            ) : (
              enrichment.related_traces.map((trace, idx) => (
                <div key={idx} className="bg-transparent border border-border rounded-xl p-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-base font-medium text-foreground">{trace.resource}</div>
                      <div className="text-sm text-muted-foreground">Count: {trace.count}</div>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      trace.status_code >= 500 ? 'bg-red-500/10 text-red-400' :
                      trace.status_code >= 400 ? 'bg-yellow-500/10 text-yellow-400' :
                      'bg-emerald-500/10 text-emerald-400'
                    }`}>
                      {trace.status_code}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'correlation' && (
          <div className="space-y-4">
            {enrichment.correlated_alerts.length === 0 ? (
              <div className="text-center text-muted-foreground py-8 text-sm">
                No correlated alerts found
              </div>
            ) : (
              <>
                <div className="bg-transparent border border-border rounded-xl p-4 mb-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs uppercase tracking-wider text-muted-foreground mb-1">Correlation Score</div>
                      <div className="text-2xl font-bold text-foreground">
                        {(enrichment.correlation_score * 100).toFixed(0)}%
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs uppercase tracking-wider text-muted-foreground mb-1">Reason</div>
                      <div className="text-sm text-muted-foreground">{enrichment.correlation_reason}</div>
                    </div>
                  </div>
                </div>

                <CorrelatedAlertsList alertIds={enrichment.correlated_alerts} />
              </>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-6 py-3 border-t border-border text-xs text-muted-foreground flex items-center justify-between">
        <span className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
          Enriched {new Date(enrichment.enriched_at).toLocaleString()}
        </span>
        <span>Processing time: {enrichment.processing_time_ms.toFixed(0)}ms</span>
      </div>
    </div>
  );
};

// Correlated Alerts List Component
const CorrelatedAlertsList: React.FC<{ alertIds: string[] }> = ({ alertIds }) => {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchCorrelatedAlerts();
  }, [alertIds]);

  const fetchCorrelatedAlerts = async () => {
    try {
      // Fetch details for each correlated alert
      const promises = alertIds.map(id =>
        fetch(`${API_URL}/alerts/${id}`, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
          }
        }).then(r => r.json())
      );

      const results = await Promise.all(promises);
      setAlerts(results);
    } catch (err) {
      console.error('Failed to fetch correlated alerts:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="text-muted-foreground text-center py-4 text-sm">Loading correlated alerts...</div>;
  }

  return (
    <div className="space-y-2">
      {alerts.map(alert => (
        <div key={alert.id} className="bg-transparent border border-border rounded-xl p-3 cursor-pointer hover:bg-accent transition-colors">
          <div className="flex items-center justify-between mb-2">
            <span className="text-base font-medium text-foreground">{alert.title}</span>
            <span className={`text-xs px-2 py-0.5 rounded-full ${
              alert.severity === 'critical' ? 'bg-red-500/10 text-red-400' :
              alert.severity === 'high' ? 'bg-orange-500/10 text-orange-400' :
              alert.severity === 'warning' ? 'bg-yellow-500/10 text-yellow-400' :
              'bg-blue-500/10 text-blue-400'
            }`}>
              {alert.severity}
            </span>
          </div>
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span>{alert.service_name || 'Unknown service'}</span>
            <span>{alert.host || 'Unknown host'}</span>
            <span>{new Date(alert.started_at).toLocaleString()}</span>
          </div>
        </div>
      ))}
    </div>
  );
};

export default AlertEnrichmentPanel;
