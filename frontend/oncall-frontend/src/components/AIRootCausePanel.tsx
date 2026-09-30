// frontend/oncall-frontend/src/components/AIRootCausePanel.tsx
import React, { useState, useEffect, useCallback } from 'react';
import {
  AlertTriangle,
  Bug,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Clock,
  Cloud,
  Cpu,
  Database,
  FlaskConical,
  Globe,
  HelpCircle,
  Lightbulb,
  RefreshCw,
  Rocket,
  Server,
  Settings,
  ShieldAlert,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Wrench
} from 'lucide-react';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { useNotifications } from '../contexts/NotificationContext';

import { API_URL as API_BASE_URL } from '../config/api';

interface TimelineEvent {
  timestamp: string;
  event_type: string;
  title: string;
  description?: string;
  service?: string;
  severity?: string;
  data?: Record<string, any>;
}

interface RecommendedAction {
  priority: number;
  action: string;
  description: string;
  category: string;
  estimated_effort?: string;
  runbook_id?: string;
}

interface AnalysisResponse {
  id: string;
  incident_id: string;
  status: 'pending' | 'analyzing' | 'completed' | 'failed';
  requested_at: string;
  requested_by_name?: string;
  root_cause?: string;
  root_cause_confidence?: number;
  root_cause_category?: string;
  contributing_factors: string[];
  affected_services: string[];
  timeline_of_events: TimelineEvent[];
  recommended_actions: RecommendedAction[];
  similar_incidents: any[];
  provider?: string;
  model?: string;
  tokens_used?: number;
  analysis_duration_ms?: number;
  error_message?: string;
  feedback_helpful?: boolean;
  feedback_comment?: string;
  completed_at?: string;
  created_at: string;
}

interface AIRootCausePanelProps {
  incidentId: string;
  incidentTitle?: string;
  onClose?: () => void;
  isExpanded?: boolean;
}

const AIRootCausePanel: React.FC<AIRootCausePanelProps> = ({
  incidentId,
  incidentTitle,
  onClose,
  isExpanded: initialExpanded = true,
}) => {
  const { showToast } = useNotifications();
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isExpanded, setIsExpanded] = useState(initialExpanded);
  const [showTimeline, setShowTimeline] = useState(false);
  const [showActions, setShowActions] = useState(true);
  const [feedbackComment, setFeedbackComment] = useState('');
  const [showFeedbackInput, setShowFeedbackInput] = useState(false);
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null);

  const getCategoryIcon = (category?: string) => {
    switch (category) {
      case 'deployment':
        return <Rocket className="w-5 h-5" />;
      case 'config_change':
        return <Settings className="w-5 h-5" />;
      case 'capacity':
        return <Cpu className="w-5 h-5" />;
      case 'dependency':
        return <Cloud className="w-5 h-5" />;
      case 'code_bug':
        return <Bug className="w-5 h-5" />;
      case 'infrastructure':
        return <Server className="w-5 h-5" />;
      case 'network':
        return <Globe className="w-5 h-5" />;
      case 'database':
        return <Database className="w-5 h-5" />;
      case 'security':
        return <ShieldAlert className="w-5 h-5" />;
      default:
        return <HelpCircle className="w-5 h-5" />;
    }
  };

  const getCategoryColor = (category?: string) => {
    switch (category) {
      case 'deployment':
        return 'text-blue-500 bg-blue-500/10 border-blue-500/30';
      case 'config_change':
        return 'text-purple-500 bg-purple-500/10 border-purple-500/30';
      case 'capacity':
        return 'text-orange-500 bg-orange-500/10 border-orange-500/30';
      case 'dependency':
        return 'text-cyan-500 bg-cyan-500/10 border-cyan-500/30';
      case 'code_bug':
        return 'text-red-500 bg-red-500/10 border-red-500/30';
      case 'infrastructure':
        return 'text-yellow-500 bg-yellow-500/10 border-yellow-500/30';
      case 'network':
        return 'text-indigo-500 bg-indigo-500/10 border-indigo-500/30';
      case 'database':
        return 'text-emerald-500 bg-emerald-500/10 border-emerald-500/30';
      case 'security':
        return 'text-rose-500 bg-rose-500/10 border-rose-500/30';
      default:
        return 'text-muted-foreground bg-secondary border-border';
    }
  };

  const fetchAnalysis = useCallback(async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/incidents/${incidentId}/analysis`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        setAnalysis(data);

        // Stop polling if analysis is complete
        if (data.status === 'completed' || data.status === 'failed') {
          setIsAnalyzing(false);
          if (pollingInterval) {
            clearInterval(pollingInterval);
            setPollingInterval(null);
          }
        }
      } else if (response.status === 404) {
        setAnalysis(null);
      }
    } catch (error) {
      console.error('Error fetching analysis:', error);
    } finally {
      setIsLoading(false);
    }
  }, [incidentId, pollingInterval]);

  useEffect(() => {
    setIsLoading(true);
    fetchAnalysis();
  }, [incidentId]);

  useEffect(() => {
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
    };
  }, [pollingInterval]);

  const triggerAnalysis = async () => {
    try {
      setIsAnalyzing(true);
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/incidents/${incidentId}/analyze`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          include_metrics: true,
          include_logs: true,
          include_traces: true,
          include_deployments: true,
          time_window_minutes: 60,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        showToast({
          type: 'info',
          title: 'Analysis Started',
          message: 'AI is analyzing the incident. This may take a minute.',
          autoClose: true,
        });

        // Start polling for results
        const interval = setInterval(fetchAnalysis, 3000);
        setPollingInterval(interval);
      } else if (response.status === 409) {
        showToast({
          type: 'warning',
          title: 'Analysis in Progress',
          message: 'An analysis is already running for this incident.',
          autoClose: true,
        });
        // Still start polling in case it completes
        const interval = setInterval(fetchAnalysis, 3000);
        setPollingInterval(interval);
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to start analysis');
      }
    } catch (error: any) {
      console.error('Error triggering analysis:', error);
      showToast({
        type: 'error',
        title: 'Analysis Failed',
        message: error.message || 'Failed to start AI analysis',
        autoClose: true,
      });
      setIsAnalyzing(false);
    }
  };

  const submitFeedback = async (helpful: boolean) => {
    if (!analysis) return;

    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(
        `${API_BASE_URL}/incidents/${incidentId}/analysis/${analysis.id}/feedback`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            helpful,
            comment: feedbackComment || null,
          }),
        }
      );

      if (response.ok) {
        const data = await response.json();
        setAnalysis(data);
        showToast({
          type: 'success',
          title: 'Feedback Submitted',
          message: 'Thank you for your feedback!',
          autoClose: true,
        });
        setShowFeedbackInput(false);
        setFeedbackComment('');
      }
    } catch (error) {
      console.error('Error submitting feedback:', error);
      showToast({
        type: 'error',
        title: 'Failed',
        message: 'Could not submit feedback',
        autoClose: true,
      });
    }
  };

  const formatDuration = (ms?: number) => {
    if (!ms) return 'N/A';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  const formatTimestamp = (ts: string) => {
    const date = new Date(ts);
    return date.toLocaleString();
  };

  const getConfidenceColor = (confidence?: number) => {
    if (!confidence) return 'bg-muted';
    if (confidence >= 0.8) return 'bg-emerald-500';
    if (confidence >= 0.6) return 'bg-yellow-500';
    if (confidence >= 0.4) return 'bg-orange-500';
    return 'bg-red-500';
  };

  const getEffortBadge = (effort?: string) => {
    switch (effort) {
      case 'quick_fix':
        return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">Quick Fix</span>;
      case 'hours':
        return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border border-yellow-500/30 bg-yellow-500/10 text-yellow-400">Hours</span>;
      case 'days':
        return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border border-red-500/30 bg-red-500/10 text-red-400">Days</span>;
      default:
        return null;
    }
  };

  if (isLoading) {
    return (
      <div className="border border-purple-500/30 rounded-lg bg-transparent">
        <div className="p-6">
          <div className="flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500"></div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="border border-purple-500/30 rounded-lg bg-transparent">
      <div className="p-6 pb-3">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold flex items-center text-base">
            <div className="w-7 h-7 bg-purple-500/10 rounded-lg text-purple-400 flex items-center justify-center mr-2">
              <FlaskConical className="w-4 h-4" />
            </div>
            AI Root Cause Analysis
          </h3>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
          >
            {isExpanded ? (
              <ChevronUp className="w-5 h-5" />
            ) : (
              <ChevronDown className="w-5 h-5" />
            )}
          </Button>
        </div>
      </div>

      {isExpanded && (
        <div className="p-6 pt-0 space-y-4">
          {/* No analysis yet */}
          {!analysis && !isAnalyzing && (
            <div className="text-center py-6">
              <Sparkles className="w-12 h-12 mx-auto text-purple-500/50 mb-3" />
              <p className="text-muted-foreground mb-4">
                Use AI to automatically identify the root cause of this incident
              </p>
              <Button
                onClick={triggerAnalysis}
                className="bg-primary text-primary-foreground hover:bg-white/90"
              >
                <Sparkles className="w-5 h-5 mr-2" />
                Analyze Incident
              </Button>
            </div>
          )}

          {/* Analysis in progress */}
          {(isAnalyzing || analysis?.status === 'pending' || analysis?.status === 'analyzing') && (
            <div className="text-center py-6">
              <div className="relative w-16 h-16 mx-auto mb-4">
                <div className="absolute inset-0 rounded-full border-4 border-purple-500/20"></div>
                <div className="absolute inset-0 rounded-full border-4 border-purple-500 border-t-transparent animate-spin"></div>
                <Sparkles className="absolute inset-3 w-10 h-10 text-purple-500" />
              </div>
              <p className="text-lg font-medium text-foreground mb-2">
                Analyzing Incident...
              </p>
              <p className="text-sm text-muted-foreground">
                Gathering context from metrics, logs, traces, and deployments
              </p>
            </div>
          )}

          {/* Analysis failed */}
          {analysis?.status === 'failed' && (
            <div className="text-center py-6">
              <AlertTriangle className="w-12 h-12 mx-auto text-red-500 mb-3" />
              <p className="text-lg font-medium text-foreground mb-2">Analysis Failed</p>
              <p className="text-sm text-muted-foreground mb-4">
                {analysis.error_message || 'An error occurred during analysis'}
              </p>
              <Button onClick={triggerAnalysis} variant="outline">
                <RefreshCw className="w-4 h-4 mr-2" />
                Retry Analysis
              </Button>
            </div>
          )}

          {/* Analysis completed */}
          {analysis?.status === 'completed' && (
            <>
              {/* Root Cause Section */}
              <div className={`p-4 rounded-lg border ${getCategoryColor(analysis.root_cause_category)}`}>
                <div className="flex items-start gap-3">
                  <div className={`p-2 rounded-lg ${getCategoryColor(analysis.root_cause_category)}`}>
                    {getCategoryIcon(analysis.root_cause_category)}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border border-border bg-secondary text-foreground capitalize">
                        {analysis.root_cause_category?.replace('_', ' ') || 'Unknown'}
                      </span>
                      {analysis.root_cause_confidence && (
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-muted-foreground">Confidence</span>
                          <div className="w-24 h-2 bg-accent rounded-full overflow-hidden">
                            <div
                              className={`h-full ${getConfidenceColor(analysis.root_cause_confidence)}`}
                              style={{ width: `${(analysis.root_cause_confidence || 0) * 100}%` }}
                            />
                          </div>
                          <span className="text-xs font-medium">
                            {Math.round((analysis.root_cause_confidence || 0) * 100)}%
                          </span>
                        </div>
                      )}
                    </div>
                    <p className="text-foreground leading-relaxed">{analysis.root_cause}</p>
                  </div>
                </div>
              </div>

              {/* Contributing Factors */}
              {analysis.contributing_factors && analysis.contributing_factors.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-muted-foreground">Contributing Factors</h4>
                  <div className="space-y-2">
                    {analysis.contributing_factors.map((factor, index) => (
                      <div
                        key={index}
                        className="flex items-start gap-2 p-2 bg-secondary/50 rounded-lg"
                      >
                        <div className="w-5 h-5 rounded-full bg-yellow-500/20 text-yellow-500 flex items-center justify-center text-xs font-medium">
                          {index + 1}
                        </div>
                        <p className="text-sm text-foreground">{factor}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Affected Services */}
              {analysis.affected_services && analysis.affected_services.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-muted-foreground">Affected Services</h4>
                  <div className="flex flex-wrap gap-2">
                    {analysis.affected_services.map((service, index) => (
                      <span key={index} className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border border-border bg-secondary/50 text-foreground">
                        <Server className="w-3 h-3 mr-1" />
                        {service}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Timeline of Events */}
              {analysis.timeline_of_events && analysis.timeline_of_events.length > 0 && (
                <div className="space-y-2">
                  <button
                    onClick={() => setShowTimeline(!showTimeline)}
                    className="flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <Clock className="w-4 h-4" />
                    Timeline of Events ({analysis.timeline_of_events.length})
                    {showTimeline ? (
                      <ChevronUp className="w-4 h-4 ml-auto" />
                    ) : (
                      <ChevronDown className="w-4 h-4 ml-auto" />
                    )}
                  </button>

                  {showTimeline && (
                    <div className="space-y-3 pl-2 border-l-2 border-muted">
                      {analysis.timeline_of_events.map((event, index) => (
                        <div key={index} className="relative pl-4">
                          <div className="absolute -left-[9px] top-1 w-4 h-4 rounded-full bg-background border-2 border-muted flex items-center justify-center">
                            <div className="w-2 h-2 rounded-full bg-accent-foreground" />
                          </div>
                          <div className="p-3 bg-secondary/50 rounded-lg">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border border-border bg-secondary text-foreground capitalize">
                                {event.event_type.replace('_', ' ')}
                              </span>
                              {event.service && (
                                <span className="text-xs text-muted-foreground">
                                  {event.service}
                                </span>
                              )}
                            </div>
                            <p className="text-sm font-medium text-foreground">{event.title}</p>
                            {event.description && (
                              <p className="text-xs text-muted-foreground mt-1">{event.description}</p>
                            )}
                            <p className="text-xs text-muted-foreground mt-2">
                              {formatTimestamp(event.timestamp)}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Recommended Actions */}
              {analysis.recommended_actions && analysis.recommended_actions.length > 0 && (
                <div className="space-y-2">
                  <button
                    onClick={() => setShowActions(!showActions)}
                    className="flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors w-full"
                  >
                    <Lightbulb className="w-4 h-4" />
                    Recommended Actions ({analysis.recommended_actions.length})
                    {showActions ? (
                      <ChevronUp className="w-4 h-4 ml-auto" />
                    ) : (
                      <ChevronDown className="w-4 h-4 ml-auto" />
                    )}
                  </button>

                  {showActions && (
                    <div className="space-y-2">
                      {analysis.recommended_actions
                        .sort((a, b) => a.priority - b.priority)
                        .map((action, index) => (
                          <div
                            key={index}
                            className="p-3 bg-secondary/50 rounded-lg border border-border hover:border-border transition-colors"
                          >
                            <div className="flex items-start gap-3">
                              <div className="w-6 h-6 rounded-full bg-secondary text-foreground flex items-center justify-center text-xs font-bold">
                                {action.priority}
                              </div>
                              <div className="flex-1">
                                <div className="flex items-center gap-2 mb-1">
                                  <h5 className="text-sm font-medium text-foreground">{action.action}</h5>
                                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border border-border bg-secondary text-foreground capitalize">
                                    {action.category.replace('_', ' ')}
                                  </span>
                                  {getEffortBadge(action.estimated_effort)}
                                </div>
                                <p className="text-xs text-muted-foreground">{action.description}</p>
                                {action.runbook_id && (
                                  <Button variant="link" size="sm" className="text-xs p-0 h-auto mt-2">
                                    <Wrench className="w-3 h-3 mr-1" />
                                    View Runbook
                                  </Button>
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                    </div>
                  )}
                </div>
              )}

              {/* Analysis Metadata */}
              <div className="pt-3 border-t border-border">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <div className="flex items-center gap-4">
                    {analysis.provider && (
                      <span>Provider: {analysis.provider}</span>
                    )}
                    {analysis.model && (
                      <span>Model: {analysis.model}</span>
                    )}
                    {analysis.analysis_duration_ms && (
                      <span>Duration: {formatDuration(analysis.analysis_duration_ms)}</span>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={triggerAnalysis}
                    className="text-xs"
                  >
                    <RefreshCw className="w-3 h-3 mr-1" />
                    Re-analyze
                  </Button>
                </div>
              </div>

              {/* Feedback Section */}
              <div className="pt-3 border-t border-border">
                {analysis.feedback_helpful === undefined ? (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Was this analysis helpful?</span>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => submitFeedback(true)}
                        className="text-green-500 hover:text-green-600 hover:border-green-500"
                      >
                        <ThumbsUp className="w-4 h-4 mr-1" />
                        Yes
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setShowFeedbackInput(true);
                        }}
                        className="text-red-500 hover:text-red-600 hover:border-red-500"
                      >
                        <ThumbsDown className="w-4 h-4 mr-1" />
                        No
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-sm">
                    {analysis.feedback_helpful ? (
                      <>
                        <CheckCircle className="w-4 h-4 text-green-500" />
                        <span className="text-muted-foreground">Thank you for your feedback!</span>
                      </>
                    ) : (
                      <>
                        <AlertTriangle className="w-4 h-4 text-yellow-500" />
                        <span className="text-muted-foreground">
                          Thanks for the feedback. We'll work on improving.
                        </span>
                      </>
                    )}
                  </div>
                )}

                {showFeedbackInput && (
                  <div className="mt-3 space-y-2">
                    <Textarea
                      placeholder="What could be improved? (optional)"
                      value={feedbackComment}
                      onChange={(e) => setFeedbackComment(e.target.value)}
                      rows={2}
                    />
                    <div className="flex justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setShowFeedbackInput(false)}
                      >
                        Cancel
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => submitFeedback(false)}
                      >
                        Submit Feedback
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default AIRootCausePanel;
