// frontend/oncall-frontend/src/components/AIInsightsHeroCard.tsx
import React, { useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  ExternalLink,
  FileText,
  Gauge,
  Lightbulb,
  MessageSquare,
  RefreshCw,
  Search,
  Sparkles,
  Target,
  Zap,
} from 'lucide-react';
import { Button } from './ui/button';

import { API_URL as API_BASE_URL } from '../config/api';

// TypeScript Interfaces
interface CorrelatedTrace {
  trace_id: string;
  service_name: string;
  operation_name: string | null;
  duration_ms: number;
  status_code: string;
  timestamp: string;
  relevance_score: number;
  relevance_reason: string | null;
}

interface CorrelatedLog {
  timestamp: string;
  service: string;
  level: string;
  message: string;
  relevance_score: number;
  relevance_reason: string | null;
}

interface AICorrelationResult {
  root_cause_hypothesis: string;
  confidence: number;
  analysis_summary: string;
  recommended_actions: string[] | null;
}

interface CorrelatedTelemetryResponse {
  incident_id: string;
  ai_analysis: AICorrelationResult;
  traces: CorrelatedTrace[];
  logs: CorrelatedLog[];
  analysis_time_ms: number;
  total_traces_analyzed: number;
  total_logs_analyzed: number;
}

interface AIInsightsHeroCardProps {
  incidentId: string;
  incidentTitle: string;
  onViewFullAnalysis: () => void;
  onAnalysisComplete?: (data: CorrelatedTelemetryResponse) => void;
}

type CardState = 'idle' | 'loading' | 'success' | 'error';

const AIInsightsHeroCard: React.FC<AIInsightsHeroCardProps> = ({
  incidentId,
  incidentTitle,
  onViewFullAnalysis,
  onAnalysisComplete,
}) => {
  const [state, setState] = useState<CardState>('idle');
  const [data, setData] = useState<CorrelatedTelemetryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showEvidence, setShowEvidence] = useState(false);
  const [showActions, setShowActions] = useState(true);

  const fetchAnalysis = async () => {
    setState('loading');
    setError(null);

    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(
        `${API_BASE_URL}/incidents/${incidentId}/correlated-telemetry?window_hours=1`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (response.ok) {
        const result = await response.json();
        setData(result);
        setState('success');
        onAnalysisComplete?.(result);
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to analyze telemetry');
      }
    } catch (err: any) {
      console.error('Error fetching correlated telemetry:', err);
      setError(err.message || 'Failed to connect to server');
      setState('error');
    }
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30';
    if (confidence >= 0.6) return 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30';
    return 'text-orange-400 bg-orange-500/10 border-orange-500/30';
  };

  const getConfidenceLabel = (confidence: number) => {
    if (confidence >= 0.8) return 'High Confidence';
    if (confidence >= 0.6) return 'Medium Confidence';
    return 'Low Confidence';
  };

  const getStatusBadgeClass = (status: string) => {
    if (status === 'ERROR' || status === 'error') {
      return 'text-red-400 bg-red-500/10 border border-red-500/20';
    }
    return 'text-emerald-400 bg-emerald-500/10 border border-emerald-500/20';
  };

  const getLogLevelClass = (level: string) => {
    const upperLevel = level.toUpperCase();
    if (['ERROR', 'FATAL', 'CRITICAL'].includes(upperLevel)) {
      return 'text-red-400 bg-red-500/10 border border-red-500/20';
    }
    if (upperLevel === 'WARN' || upperLevel === 'WARNING') {
      return 'text-yellow-400 bg-yellow-500/10 border border-yellow-500/20';
    }
    return 'text-muted-foreground bg-accent border border-border';
  };

  const getActionPriorityStyle = (action: string) => {
    if (action.startsWith('IMMEDIATE:')) {
      return { icon: Zap, color: 'text-red-400', bg: 'bg-red-500/10', label: 'Immediate' };
    }
    if (action.startsWith('SHORT-TERM:')) {
      return { icon: Clock, color: 'text-yellow-400', bg: 'bg-yellow-500/10', label: 'Short-term' };
    }
    if (action.startsWith('LONG-TERM:')) {
      return { icon: Target, color: 'text-blue-400', bg: 'bg-blue-500/10', label: 'Long-term' };
    }
    return { icon: CheckCircle2, color: 'text-muted-foreground', bg: 'bg-secondary', label: 'Action' };
  };

  const formatActionText = (action: string) => {
    return action.replace(/^(IMMEDIATE|SHORT-TERM|LONG-TERM):\s*/i, '');
  };

  // Idle State
  if (state === 'idle') {
    return (
      <div className="mb-6 bg-transparent border border-purple-500/30 rounded-xl p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-purple-500/10 rounded-lg flex items-center justify-center">
              <FileText className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-foreground">AI Root Cause Analysis</h3>
              <p className="text-sm text-muted-foreground">
                Generate a professional RCA report with correlated telemetry
              </p>
            </div>
          </div>
          <Button
            onClick={fetchAnalysis}
            className="bg-purple-500/10 text-purple-400 border border-purple-500/30 hover:bg-purple-500/20"
          >
            <Sparkles className="w-4 h-4 mr-2" />
            Generate Report
          </Button>
        </div>
      </div>
    );
  }

  // Loading State
  if (state === 'loading') {
    return (
      <div className="mb-6 bg-transparent border border-purple-500/30 rounded-xl p-6">
        <div className="flex flex-col items-center justify-center py-8">
          <div className="relative w-16 h-16 mb-4">
            <div className="absolute inset-0 rounded-full border-4 border-purple-500/20"></div>
            <div className="absolute inset-0 rounded-full border-4 border-purple-500 border-t-transparent animate-spin"></div>
            <Sparkles className="absolute inset-3 w-10 h-10 text-purple-400" />
          </div>
          <p className="text-base font-medium text-foreground mb-1">Generating RCA Report...</p>
          <p className="text-sm text-muted-foreground text-center max-w-md">
            Analyzing distributed traces, logs, and system metrics to identify root cause
          </p>
        </div>
      </div>
    );
  }

  // Error State
  if (state === 'error') {
    return (
      <div className="mb-6 bg-transparent border border-red-500/30 rounded-xl p-6">
        <div className="flex flex-col items-center justify-center py-6">
          <AlertTriangle className="w-12 h-12 text-red-400 mb-3" />
          <p className="text-base font-medium text-foreground mb-1">Analysis Failed</p>
          <p className="text-sm text-muted-foreground mb-4">{error}</p>
          <Button
            onClick={fetchAnalysis}
            variant="outline"
            className="border-red-500/30 text-red-400 hover:bg-red-500/10"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Retry Analysis
          </Button>
        </div>
      </div>
    );
  }

  // Success State - Professional Report Format
  if (state === 'success' && data) {
    const confidence = data.ai_analysis?.confidence || 0;
    const confidencePercent = Math.round(confidence * 100);
    const topTraces = data.traces?.filter(t => t.relevance_score > 0.5).slice(0, 5) || [];
    const topLogs = data.logs?.filter(l => l.relevance_score > 0.5).slice(0, 5) || [];
    const actions = data.ai_analysis?.recommended_actions || [];

    return (
      <div className="mb-6 bg-transparent border border-purple-500/30 rounded-xl overflow-hidden">
        {/* Report Header */}
        <div className="p-4 border-b border-purple-500/20 bg-purple-500/5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-purple-500/10 rounded-lg flex items-center justify-center">
                <FileText className="w-4 h-4 text-purple-400" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-foreground">Root Cause Analysis Report</h3>
                <p className="text-xs text-muted-foreground">
                  Generated {new Date().toLocaleString()}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border ${getConfidenceColor(confidence)}`}>
                <Gauge className="w-3 h-3" />
                {confidencePercent}% - {getConfidenceLabel(confidence)}
              </div>
            </div>
          </div>
        </div>

        {/* Section 1: Root Cause Statement */}
        <div className="p-4 border-b border-border">
          <div className="flex items-start gap-3 mb-3">
            <div className="w-6 h-6 rounded bg-red-500/10 flex items-center justify-center flex-shrink-0 mt-0.5">
              <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-foreground uppercase tracking-wide mb-2">
                Root Cause Determination
              </h4>
              <p className="text-sm text-foreground leading-relaxed">
                {data.ai_analysis?.root_cause_hypothesis || 'Unable to determine root cause from available telemetry.'}
              </p>
            </div>
          </div>
        </div>

        {/* Section 2: Recommended Actions */}
        {actions.length > 0 && (
          <div className="p-4 border-b border-border">
            <button
              onClick={() => setShowActions(!showActions)}
              className="flex items-center gap-3 w-full text-left mb-3"
            >
              <div className="w-6 h-6 rounded bg-emerald-500/10 flex items-center justify-center flex-shrink-0">
                <Lightbulb className="w-3.5 h-3.5 text-emerald-400" />
              </div>
              <h4 className="text-sm font-semibold text-foreground uppercase tracking-wide flex-1">
                Recommended Actions ({actions.length})
              </h4>
              {showActions ? (
                <ChevronUp className="w-4 h-4 text-muted-foreground" />
              ) : (
                <ChevronDown className="w-4 h-4 text-muted-foreground" />
              )}
            </button>
            {showActions && (
              <div className="space-y-2 ml-9">
                {actions.map((action, index) => {
                  const style = getActionPriorityStyle(action);
                  const Icon = style.icon;
                  return (
                    <div
                      key={index}
                      className={`flex items-start gap-3 p-3 rounded-lg ${style.bg} border border-border`}
                    >
                      <div className={`w-5 h-5 rounded flex items-center justify-center flex-shrink-0 ${style.bg}`}>
                        <Icon className={`w-3 h-3 ${style.color}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <span className={`text-xs font-medium ${style.color} uppercase tracking-wide`}>
                          {style.label}
                        </span>
                        <p className="text-sm text-foreground mt-0.5">
                          {formatActionText(action)}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Section 3: Supporting Evidence */}
        {(topTraces.length > 0 || topLogs.length > 0) && (
          <div className="p-4 border-b border-border">
            <button
              onClick={() => setShowEvidence(!showEvidence)}
              className="flex items-center gap-3 w-full text-left"
            >
              <div className="w-6 h-6 rounded bg-blue-500/10 flex items-center justify-center flex-shrink-0">
                <Search className="w-3.5 h-3.5 text-blue-400" />
              </div>
              <h4 className="text-sm font-semibold text-foreground uppercase tracking-wide flex-1">
                Supporting Evidence ({topTraces.length} traces, {topLogs.length} logs)
              </h4>
              {showEvidence ? (
                <ChevronUp className="w-4 h-4 text-muted-foreground" />
              ) : (
                <ChevronDown className="w-4 h-4 text-muted-foreground" />
              )}
            </button>

            {showEvidence && (
              <div className="mt-3 ml-9 space-y-4">
                {/* Traces */}
                {topTraces.length > 0 && (
                  <div>
                    <h5 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 flex items-center gap-2">
                      <Search className="w-3 h-3" />
                      Correlated Traces
                    </h5>
                    <div className="space-y-1.5">
                      {topTraces.map((trace, index) => (
                        <div
                          key={trace.trace_id || index}
                          className="flex items-center gap-2 p-2 bg-secondary/50 rounded border border-border text-xs"
                        >
                          <span className={`px-1.5 py-0.5 rounded font-medium ${getStatusBadgeClass(trace.status_code)}`}>
                            {trace.status_code}
                          </span>
                          <span className="text-foreground font-medium">{trace.service_name}</span>
                          <span className="text-muted-foreground">{trace.operation_name || '-'}</span>
                          <span className="text-muted-foreground ml-auto">{trace.duration_ms?.toFixed(0)}ms</span>
                          <span className="text-purple-400 font-medium">{Math.round(trace.relevance_score * 100)}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Logs */}
                {topLogs.length > 0 && (
                  <div>
                    <h5 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 flex items-center gap-2">
                      <MessageSquare className="w-3 h-3" />
                      Correlated Logs
                    </h5>
                    <div className="space-y-1.5">
                      {topLogs.map((log, index) => (
                        <div
                          key={index}
                          className="flex items-start gap-2 p-2 bg-secondary/50 rounded border border-border text-xs"
                        >
                          <span className={`px-1.5 py-0.5 rounded font-medium flex-shrink-0 ${getLogLevelClass(log.level)}`}>
                            {log.level}
                          </span>
                          <span className="text-muted-foreground flex-shrink-0">{log.service}</span>
                          <span className="text-foreground flex-1 truncate">{log.message?.slice(0, 80)}</span>
                          <span className="text-purple-400 font-medium flex-shrink-0">{Math.round(log.relevance_score * 100)}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Report Footer */}
        <div className="p-4 flex items-center justify-between bg-secondary/20">
          <div className="text-xs text-muted-foreground">
            <span className="font-medium">{data.total_traces_analyzed || 0}</span> traces and{' '}
            <span className="font-medium">{data.total_logs_analyzed || 0}</span> logs analyzed in{' '}
            <span className="font-medium">{(data.analysis_time_ms / 1000).toFixed(1)}s</span>
          </div>
          <Button
            onClick={onViewFullAnalysis}
            variant="ghost"
            size="sm"
            className="text-purple-400 hover:text-purple-300 hover:bg-purple-500/10"
          >
            View Full Analysis
            <ExternalLink className="w-4 h-4 ml-1" />
          </Button>
        </div>
      </div>
    );
  }

  return null;
};

export default AIInsightsHeroCard;
