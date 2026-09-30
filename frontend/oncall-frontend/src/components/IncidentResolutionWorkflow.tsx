import React, { useState, useEffect, useCallback } from 'react';
import {
  AlertTriangle,
  Check,
  Clock,
  Cpu,
  FileText,
  Info,
  MessagesSquare,
  Play,
  RefreshCw,
  ShieldCheck,
  Terminal,
  User,
  X,
  Zap
} from 'lucide-react';
// Magic UI imports removed - using plain HTML/Tailwind equivalents

import { API_URL as API_BASE_URL } from '../config/api';

interface ResolutionStep {
  id: string;
  order: number;
  title: string;
  description: string;
  command?: string;
  expected_result: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  execution_time?: number;
  output?: string;
  ai_generated: boolean;
}

interface Incident {
  id: string;
  title: string;
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  status: 'open' | 'acknowledged' | 'investigating' | 'resolved';
  assigned_to: string;
  created_at: string;
}

interface AIInsights {
  root_cause: string;
  business_impact: string;
  estimated_resolution_time: string;
  confidence_score: number;
  similar_incidents: number;
}

interface IncidentResolutionWorkflowProps {
  incident: Incident;
  onStatusChange: (status: string) => void;
  onResolve: () => void;
}

const IncidentResolutionWorkflow: React.FC<IncidentResolutionWorkflowProps> = ({
  incident,
  onStatusChange,
  onResolve
}) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'steps' | 'timeline' | 'ai'>('overview');
  const [resolutionSteps, setResolutionSteps] = useState<ResolutionStep[]>([]);
  const [aiInsights, setAiInsights] = useState<AIInsights | null>(null);
  const [isGeneratingSteps, setIsGeneratingSteps] = useState(false);
  const [isLoadingInsights, setIsLoadingInsights] = useState(false);
  const [executingStep, setExecutingStep] = useState<string | null>(null);
  const [comments, setComments] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [usingFallback, setUsingFallback] = useState(false);

  // Fetch AI insights from backend or generate fallback
  const fetchAIInsights = useCallback(async () => {
    setIsLoadingInsights(true);
    setError(null);

    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/incidents/${incident.id}/quick-insights`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        setAiInsights({
          root_cause: data.root_cause || 'Analysis in progress...',
          business_impact: data.business_impact || 'Assessing impact...',
          estimated_resolution_time: data.estimated_resolution_time || 'Calculating...',
          confidence_score: data.confidence_score || 0,
          similar_incidents: data.similar_incidents_count || 0
        });
        setUsingFallback(false);
      } else {
        // Generate local fallback based on incident data
        generateFallbackInsights();
      }
    } catch (error) {
      generateFallbackInsights();
    } finally {
      setIsLoadingInsights(false);
    }
  }, [incident.id]);

  const generateFallbackInsights = () => {
    setUsingFallback(true);
    // Generate contextual insights based on incident severity and title
    const severityImpact: Record<string, string> = {
      critical: 'High - Service may be completely unavailable to users',
      high: 'Medium-High - Significant degradation in service quality',
      medium: 'Medium - Some users may experience issues',
      low: 'Low - Minor impact on non-critical functionality'
    };

    setAiInsights({
      root_cause: `Analyzing incident: ${incident.title}`,
      business_impact: severityImpact[incident.severity] || 'Assessing impact...',
      estimated_resolution_time: incident.severity === 'critical' ? '15-30 minutes' : '30-60 minutes',
      confidence_score: 0, // 0 indicates local fallback
      similar_incidents: 0
    });
  };

  // Generate resolution steps from backend or local templates
  const generateAIResolutionSteps = useCallback(async () => {
    setIsGeneratingSteps(true);
    setError(null);

    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/incidents/${incident.id}/resolution-steps`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        if (data.steps && data.steps.length > 0) {
          setResolutionSteps(data.steps.map((step: any, index: number) => ({
            id: step.id || String(index + 1),
            order: index + 1,
            title: step.title,
            description: step.description,
            command: step.command,
            expected_result: step.expected_result || 'Verify step completion',
            status: 'pending',
            ai_generated: true
          })));
          setUsingFallback(false);
          setIsGeneratingSteps(false);
          return;
        }
      }

      // Fall back to local template generation
      generateLocalResolutionSteps();
    } catch (error) {
      generateLocalResolutionSteps();
    }
  }, [incident.id]);

  const generateLocalResolutionSteps = () => {
    setUsingFallback(true);
    // Generate generic resolution steps based on incident type
    const steps: ResolutionStep[] = [
      {
        id: '1',
        order: 1,
        title: 'Initial Assessment',
        description: 'Review incident details and identify affected systems',
        expected_result: 'Clear understanding of scope and impact',
        status: 'pending',
        ai_generated: false
      },
      {
        id: '2',
        order: 2,
        title: 'Gather Diagnostics',
        description: 'Collect relevant logs, metrics, and traces',
        expected_result: 'Diagnostic data available for analysis',
        status: 'pending',
        ai_generated: false
      },
      {
        id: '3',
        order: 3,
        title: 'Identify Root Cause',
        description: 'Analyze diagnostics to determine the root cause',
        expected_result: 'Root cause identified and documented',
        status: 'pending',
        ai_generated: false
      },
      {
        id: '4',
        order: 4,
        title: 'Implement Fix',
        description: 'Apply the appropriate remediation steps',
        expected_result: 'Fix deployed and verified',
        status: 'pending',
        ai_generated: false
      },
      {
        id: '5',
        order: 5,
        title: 'Verify Resolution',
        description: 'Monitor systems to confirm the issue is resolved',
        expected_result: 'All systems operating normally',
        status: 'pending',
        ai_generated: false
      }
    ];

    setResolutionSteps(steps);
    setIsGeneratingSteps(false);
  };

  useEffect(() => {
    generateAIResolutionSteps();
    fetchAIInsights();
  }, [generateAIResolutionSteps, fetchAIInsights]);

  const executeStep = async (stepId: string) => {
    setExecutingStep(stepId);

    const step = resolutionSteps.find(s => s.id === stepId);
    if (!step) return;

    // Update step to running
    setResolutionSteps(prev => prev.map(s =>
      s.id === stepId ? { ...s, status: 'running' } : s
    ));

    try {
      const startTime = Date.now();

      // Running an arbitrary command supplied by the browser would be remote
      // code execution on the backend host, so there is deliberately no
      // endpoint for it. Runbooks have a sanctioned execution path
      // (POST /runbooks/{id}/execute) that is defined server-side and audited.
      // Mark as completed for manual steps (no command)
      setResolutionSteps(prev => prev.map(s =>
        s.id === stepId ? {
          ...s,
          status: 'completed',
          execution_time: Math.round((Date.now() - startTime) / 1000),
          output: step.command
            ? `Run this manually: ${step.command}`
            : 'Manual step marked as completed'
        } : s
      ));
    } catch (error) {
      setResolutionSteps(prev => prev.map(s =>
        s.id === stepId ? {
          ...s,
          status: 'failed',
          output: 'Failed to execute step. Please try manually.'
        } : s
      ));
    }

    setExecutingStep(null);
  };

  const skipStep = (stepId: string) => {
    setResolutionSteps(prev => prev.map(s =>
      s.id === stepId ? { ...s, status: 'skipped' } : s
    ));
  };

  const acknowledgeIncident = () => {
    onStatusChange('acknowledged');
  };

  const startInvestigation = () => {
    onStatusChange('investigating');
  };

  const resolveIncident = () => {
    onStatusChange('resolved');
    onResolve();
  };

  const getSeverityBadgeClasses = (severity: string): string => {
    switch (severity) {
      case 'critical': return 'border-red-500/30 bg-red-500/10 text-red-400';
      case 'high': return 'border-yellow-500/30 bg-yellow-500/10 text-yellow-400';
      case 'medium': return 'border-yellow-500/30 bg-yellow-500/10 text-yellow-400';
      case 'low': return 'border-blue-500/30 bg-blue-500/10 text-blue-400';
      default: return 'border-border bg-secondary text-foreground';
    }
  };

  const getStatusBadgeClasses = (status: string): string => {
    switch (status) {
      case 'open': return 'border-red-500/30 bg-red-500/10 text-red-400';
      case 'acknowledged': return 'border-yellow-500/30 bg-yellow-500/10 text-yellow-400';
      case 'investigating': return 'border-blue-500/30 bg-blue-500/10 text-blue-400';
      case 'resolved': return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400';
      default: return 'border-border bg-secondary text-foreground';
    }
  };

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="border border-border rounded-lg bg-transparent p-6 mb-6">
          <div className="relative overflow-hidden rounded-xl">
            <div className="absolute inset-0 bg-transparent" />
            <div className="relative">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h1 className="text-2xl font-bold text-foreground mb-2">{incident.title}</h1>
                  <p className="text-muted-foreground">{incident.description}</p>
                </div>
                <div className="flex gap-3">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${getSeverityBadgeClasses(incident.severity)}`}>
                    {incident.severity.toUpperCase()}
                  </span>
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${getStatusBadgeClasses(incident.status)}`}>
                    {incident.status.toUpperCase()}
                  </span>
                </div>
              </div>

              {/* Quick Actions */}
              <div className="flex gap-3">
                {incident.status === 'open' && (
                  <button
                    onClick={acknowledgeIncident}
                    className="bg-primary text-primary-foreground hover:bg-white/90 rounded-md px-4 py-1.5 text-sm font-medium"
                  >
                    Acknowledge
                  </button>
                )}
                {incident.status === 'acknowledged' && (
                  <button
                    onClick={startInvestigation}
                    className="bg-primary text-primary-foreground hover:bg-white/90 rounded-md px-4 py-1.5 text-sm font-medium"
                  >
                    Start Investigation
                  </button>
                )}
                {(incident.status === 'investigating' || incident.status === 'acknowledged') && (
                  <button
                    onClick={resolveIncident}
                    className="bg-primary text-primary-foreground hover:bg-white/90 rounded-md px-4 py-1.5 text-sm font-medium"
                  >
                    Mark Resolved
                  </button>
                )}
                <button className="border border-border text-foreground hover:bg-accent rounded-md px-4 py-1.5 text-sm font-medium">
                  Escalate
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex space-x-1 mb-6">
          {[
            { id: 'overview', name: 'Overview', icon: FileText },
            { id: 'steps', name: 'Resolution Steps', icon: Terminal },
            { id: 'ai', name: 'AI Insights', icon: Cpu },
            { id: 'timeline', name: 'Timeline', icon: Clock }
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all duration-300 ${
                activeTab === tab.id
                  ? 'bg-secondary text-foreground border border-border'
                  : 'text-muted-foreground hover:text-foreground hover:bg-accent'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.name}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-2">
            {/* Overview Tab */}
            {activeTab === 'overview' && (
              <div className="space-y-6">
                <div className="border border-border rounded-lg bg-transparent p-6">
                  <h3 className="text-lg font-semibold text-foreground mb-4">Incident Details</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm text-muted-foreground mb-1">Assigned To</label>
                      <p className="text-foreground">{incident.assigned_to}</p>
                    </div>
                    <div>
                      <label className="block text-sm text-muted-foreground mb-1">Created</label>
                      <p className="text-foreground">{new Date(incident.created_at).toLocaleString()}</p>
                    </div>
                  </div>
                </div>

                <div className="border border-border rounded-lg bg-transparent p-6">
                  <h3 className="text-lg font-semibold text-foreground mb-4">Add Comment</h3>
                  <textarea
                    value={comments}
                    onChange={(e) => setComments(e.target.value)}
                    placeholder="Add details about investigation or resolution..."
                    className="w-full px-4 py-3 bg-secondary/50 border border-border/50 rounded-lg text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-transparent resize-none transition-all"
                    rows={4}
                  />
                  <button className="mt-3 bg-primary text-primary-foreground hover:bg-white/90 rounded-md px-4 py-1.5 text-sm font-medium">
                    Add Comment
                  </button>
                </div>
              </div>
            )}

            {/* Resolution Steps Tab */}
            {activeTab === 'steps' && (
              <div className="border border-border rounded-lg bg-transparent p-6">
                <div className="flex items-center justify-between mb-6">
                  <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
                    <span className="text-foreground">Resolution Steps</span>
                    {usingFallback && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border border-yellow-500/30 bg-yellow-500/10 text-yellow-400 ml-2">
                        <Info className="w-3 h-3 mr-1" />
                        Template Steps
                      </span>
                    )}
                  </h3>
                  <button
                    onClick={() => generateAIResolutionSteps()}
                    disabled={isGeneratingSteps}
                    className="bg-primary text-primary-foreground hover:bg-white/90 rounded-md px-4 py-1.5 text-sm font-medium inline-flex items-center gap-2 disabled:opacity-50"
                  >
                    <RefreshCw className={`w-4 h-4 ${isGeneratingSteps ? 'animate-spin' : ''}`} />
                    {usingFallback ? 'Get AI Steps' : 'Regenerate Steps'}
                  </button>
                </div>

                {usingFallback && (
                  <div className="border border-yellow-500/30 rounded-lg bg-transparent mb-4 p-3">
                    <p className="text-yellow-400 text-sm flex items-center gap-2">
                      <Info className="w-4 h-4" />
                      Showing generic resolution template. Click "Get AI Steps" for incident-specific recommendations.
                    </p>
                  </div>
                )}

                {isGeneratingSteps ? (
                  <div className="text-center py-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-400 mx-auto mb-4"></div>
                    <p className="text-muted-foreground">Generating resolution steps...</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {resolutionSteps.map((step, index) => (
                      <div
                        key={step.id}
                        className={`border rounded-lg bg-transparent p-4 ${
                          step.status === 'completed' ? 'border-green-500/50' :
                          step.status === 'running' ? 'border-blue-500/50' :
                          step.status === 'failed' ? 'border-red-500/50' :
                          'border-border'
                        }`}
                      >
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex items-start gap-3">
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold ${
                              step.status === 'completed' ? 'bg-emerald-500/20 text-emerald-400' :
                              step.status === 'running' ? 'bg-blue-500/20 text-blue-400' :
                              step.status === 'failed' ? 'bg-red-500/20 text-red-400' :
                              step.status === 'skipped' ? 'bg-secondary text-muted-foreground' :
                              'bg-accent text-foreground'
                            }`}>
                              {step.status === 'completed' ? <Check className="w-4 h-4" /> :
                               step.status === 'running' ? <RefreshCw className="w-4 h-4 animate-spin" /> :
                               step.status === 'failed' ? <X className="w-4 h-4" /> :
                               step.order}
                            </div>
                            <div>
                              <h4 className="font-semibold text-foreground flex items-center gap-2">
                                {step.title}
                                {step.ai_generated && (
                                  <div className="p-0.5 rounded bg-purple-500/10">
                                    <Zap className="w-3.5 h-3.5 text-purple-400" />
                                  </div>
                                )}
                              </h4>
                              <p className="text-muted-foreground text-sm">{step.description}</p>
                              {step.command && (
                                <code className="mt-2 block p-2 bg-black/50 rounded text-sm text-green-400 font-mono border border-border/30">
                                  {step.command}
                                </code>
                              )}
                              {step.output && (
                                <pre className="mt-2 p-3 bg-black/50 rounded text-sm text-foreground font-mono whitespace-pre-wrap border border-border/30">
                                  {step.output}
                                </pre>
                              )}
                            </div>
                          </div>

                          {step.status === 'pending' && (
                            <div className="flex gap-2">
                              <button
                                onClick={() => executeStep(step.id)}
                                disabled={executingStep !== null}
                                className="bg-primary text-primary-foreground hover:bg-white/90 rounded-md px-4 py-1.5 text-sm font-medium inline-flex items-center gap-1 disabled:opacity-50"
                              >
                                <Play className="w-3 h-3" />
                                Execute
                              </button>
                              <button
                                onClick={() => skipStep(step.id)}
                                className="border border-border text-foreground hover:bg-accent rounded-md px-4 py-1.5 text-sm font-medium"
                              >
                                Skip
                              </button>
                            </div>
                          )}
                        </div>

                        {step.execution_time && (
                          <p className="text-xs text-muted-foreground">
                            Completed in {step.execution_time}s
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* AI Insights Tab */}
            {activeTab === 'ai' && (
              <div className="space-y-6">
                {isLoadingInsights ? (
                  <div className="border border-border rounded-lg bg-transparent p-6">
                    <div className="text-center py-8">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-400 mx-auto mb-4"></div>
                      <p className="text-muted-foreground">AI is analyzing the incident...</p>
                    </div>
                  </div>
                ) : aiInsights ? (
                  <div className="border border-border rounded-lg bg-transparent p-6">
                    <h3 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
                      <div className="p-2 rounded-xl bg-purple-500/10">
                        <Cpu className="w-4 h-4 text-purple-400" />
                      </div>
                      <span className="text-foreground">AI Analysis Results</span>
                      {usingFallback && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border border-yellow-500/30 bg-yellow-500/10 text-yellow-400 ml-2">
                          <Info className="w-3 h-3 mr-1" />
                          Basic Analysis
                        </span>
                      )}
                    </h3>

                    {usingFallback && (
                      <div className="border border-yellow-500/30 rounded-lg bg-transparent mb-4 p-3">
                        <p className="text-yellow-400 text-sm flex items-center gap-2">
                          <Info className="w-4 h-4" />
                          Full AI analysis unavailable. Showing basic assessment based on incident data.
                        </p>
                      </div>
                    )}

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="border border-border rounded-lg bg-transparent p-4">
                        <label className="block text-sm text-muted-foreground mb-2">Confidence Score</label>
                        <div className="flex items-center gap-3">
                          <div className="flex-1 bg-accent rounded-full h-2">
                            <div
                              className={`h-2 rounded-full transition-all ${aiInsights.confidence_score > 0 ? 'bg-emerald-500' : 'bg-muted'}`}
                              style={{ width: `${aiInsights.confidence_score || 5}%` }}
                            />
                          </div>
                          <span className="text-foreground font-medium">
                            {aiInsights.confidence_score > 0 ? `${aiInsights.confidence_score}%` : 'N/A'}
                          </span>
                        </div>
                      </div>

                      <div className="border border-border rounded-lg bg-transparent p-4">
                        <label className="block text-sm text-muted-foreground mb-2">Similar Incidents</label>
                        <p className="text-foreground">
                          {aiInsights.similar_incidents > 0
                            ? <><span className="text-2xl font-bold">{aiInsights.similar_incidents}</span> <span className="text-sm">found in history</span></>
                            : 'Searching...'}
                        </p>
                      </div>
                    </div>

                    <div className="mt-6 space-y-4">
                      <div className="border border-border rounded-lg bg-transparent p-4">
                        <label className="block text-sm text-muted-foreground mb-2">Root Cause Analysis</label>
                        <p className="text-foreground">{aiInsights.root_cause}</p>
                      </div>

                      <div className="border border-border rounded-lg bg-transparent p-4">
                        <label className="block text-sm text-muted-foreground mb-2">Business Impact</label>
                        <p className="text-foreground">{aiInsights.business_impact}</p>
                      </div>

                      <div className="border border-border rounded-lg bg-transparent p-4">
                        <label className="block text-sm text-muted-foreground mb-2">Estimated Resolution Time</label>
                        <p className="text-foreground">{aiInsights.estimated_resolution_time}</p>
                      </div>
                    </div>

                    {usingFallback && (
                      <button
                        onClick={fetchAIInsights}
                        className="mt-4 bg-primary text-primary-foreground hover:bg-white/90 rounded-md px-4 py-1.5 text-sm font-medium inline-flex items-center gap-2"
                      >
                        <RefreshCw className="w-4 h-4" />
                        Retry AI Analysis
                      </button>
                    )}
                  </div>
                ) : (
                  <div className="border border-border rounded-lg bg-transparent p-6 text-center py-8">
                    <div className="p-3 rounded-xl bg-red-500/10 w-fit mx-auto mb-4">
                      <AlertTriangle className="w-10 h-10 text-red-400" />
                    </div>
                    <h3 className="text-lg font-semibold text-muted-foreground mb-2">AI Analysis Unavailable</h3>
                    <p className="text-muted-foreground text-sm mb-4">Unable to generate AI insights for this incident.</p>
                    <button
                      onClick={fetchAIInsights}
                      className="bg-primary text-primary-foreground hover:bg-white/90 rounded-md px-4 py-1.5 text-sm font-medium"
                    >
                      Try Again
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Timeline Tab */}
            {activeTab === 'timeline' && (
              <div className="border border-border rounded-lg bg-transparent p-6">
                <h3 className="text-lg font-semibold text-foreground mb-4">
                  <span className="text-foreground">Incident Timeline</span>
                </h3>
                <div className="space-y-4">
                  <div className="flex gap-3 items-start">
                    <span className="h-2.5 w-2.5 rounded-full bg-blue-500 inline-block mt-1.5 flex-shrink-0" />
                    <div>
                      <p className="text-foreground">Incident created by monitoring alert</p>
                      <p className="text-muted-foreground text-sm">{new Date(incident.created_at).toLocaleString()}</p>
                    </div>
                  </div>
                  <div className="flex gap-3 items-start">
                    <span className="h-2.5 w-2.5 rounded-full bg-yellow-500 inline-block mt-1.5 flex-shrink-0" />
                    <div>
                      <p className="text-foreground">Incident acknowledged by {incident.assigned_to}</p>
                      <p className="text-muted-foreground text-sm">2 minutes ago</p>
                    </div>
                  </div>
                  <div className="flex gap-3 items-start">
                    <span className="h-2.5 w-2.5 rounded-full bg-purple-500 inline-block mt-1.5 flex-shrink-0" />
                    <div>
                      <p className="text-foreground">AI generated resolution steps</p>
                      <p className="text-muted-foreground text-sm">1 minute ago</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Quick Stats */}
            <div className="border border-border rounded-lg bg-transparent p-6">
              <h3 className="text-lg font-semibold text-foreground mb-4">Quick Stats</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Duration</span>
                  <span className="text-foreground font-mono">1h 23m</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Steps Completed</span>
                  <span className="text-foreground">
                    <span className="font-bold">{resolutionSteps.filter(s => s.status === 'completed').length}</span>/{resolutionSteps.length}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Last Update</span>
                  <span className="text-foreground">2 min ago</span>
                </div>
              </div>
            </div>

            {/* Recent Activity */}
            <div className="border border-border rounded-lg bg-transparent p-6">
              <h3 className="text-lg font-semibold text-foreground mb-4">Recent Activity</h3>
              <div className="space-y-3 text-sm">
                <div className="flex items-center gap-2">
                  <div className="p-1 rounded bg-purple-500/10">
                    <Zap className="w-3.5 h-3.5 text-purple-400" />
                  </div>
                  <span className="text-foreground">AI analysis completed</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="p-1 rounded bg-blue-500/10">
                    <User className="w-3.5 h-3.5 text-blue-400" />
                  </div>
                  <span className="text-foreground">Assigned to {incident.assigned_to}</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="p-1 rounded bg-emerald-500/10">
                    <MessagesSquare className="w-3.5 h-3.5 text-green-400" />
                  </div>
                  <span className="text-foreground">Slack notification sent</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default IncidentResolutionWorkflow;
