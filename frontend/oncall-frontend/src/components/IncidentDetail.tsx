// frontend/oncall-frontend/src/components/IncidentDetail.tsx - Refactored with shadcn/ui

import React, { useState, useEffect, useCallback } from 'react';
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle,
  Clock,
  Database,
  Filter,
  MessageSquare,
  Paperclip,
  Search,
  Settings2,
  Sparkles,
  User,
  UserPlus,
  X
} from 'lucide-react';
import { useNotifications } from '../contexts/NotificationContext';
import IncidentAIChat from './IncidentAIChat';
import RunbookSuggestions from './RunbookSuggestions';
import RunbookExecutionMonitor from './RunbookExecutionMonitor';
import AIRootCausePanel from './AIRootCausePanel';
import AIInsightsHeroCard from './AIInsightsHeroCard';
import { Button } from './ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from './ui/tabs';

import { API_URL as API_BASE_URL } from '../config/api';

interface IncidentDetailProps {
  incidentId: string;
  onBack: () => void;
  onShowAIAnalysis?: (incidentId: string, analysisData: any) => void;
  onNavigateToIncident?: (id: string) => void;
  onNavigateToAlert?: (id: string) => void;
}

interface Incident {
  id: string;
  title: string;
  description?: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  status: 'open' | 'acknowledged' | 'resolved' | 'closed';
  assigned_to_id?: string;
  assigned_to_name?: string;
  created_by_name?: string;
  tags?: string[];
  created_at?: string;
  updated_at?: string;
  resolved_at?: string;
  acknowledged_at?: string;
}

interface QuickInsights {
  suggested_action: string;
  risk_assessment: string;
  similar_incidents_count: number;
  avg_resolution_time_minutes: number | null;
}

interface SimilarIncident {
  id: string;
  title: string;
  severity: string;
  status: string;
  resolved_at: string | null;
  resolution_time_minutes: number | null;
  match_score: number;
  match_reasons: string[];
}

interface TeamMember {
  id: string;
  email: string;
  full_name: string;
  role: string;
}

const IncidentDetail: React.FC<IncidentDetailProps> = ({
  incidentId,
  onBack,
  onShowAIAnalysis,
  onNavigateToAlert
}) => {
  const { showToast } = useNotifications();
  const [incident, setIncident] = useState<Incident | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<string>('timeline');
  const [isEditing, setIsEditing] = useState(false);
  const [relatedAlerts, setRelatedAlerts] = useState<any[]>([]);
  const [activeExecutionId, setActiveExecutionId] = useState<string | null>(null);
  const [quickInsights, setQuickInsights] = useState<QuickInsights | null>(null);
  const [similarIncidents, setSimilarIncidents] = useState<SimilarIncident[]>([]);
  const [loadingInsights, setLoadingInsights] = useState(true);
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [showAssignDropdown, setShowAssignDropdown] = useState(false);
  const [isAssigning, setIsAssigning] = useState(false);
  const [showResolveModal, setShowResolveModal] = useState(false);
  const [resolutionNotes, setResolutionNotes] = useState('');
  const [isResolving, setIsResolving] = useState(false);
  const [correlatedTelemetry, setCorrelatedTelemetry] = useState<any>(null);
  const [loadingTelemetry, setLoadingTelemetry] = useState(false);
  const [telemetryError, setTelemetryError] = useState<string | null>(null);

  // Log filtering state
  const [logSearchQuery, setLogSearchQuery] = useState('');
  const [logLevelFilter, setLogLevelFilter] = useState<string[]>([]);
  const [logServiceFilter, setLogServiceFilter] = useState<string>('');

  // Use ref to track if we've already fetched to prevent duplicate calls
  const hasFetchedRef = React.useRef(false);
  const currentIncidentIdRef = React.useRef(incidentId);

  const fetchIncident = useCallback(async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/incidents/${incidentId}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch incident');
      }

      const data = await response.json();
      setIncident(data);

      // Fetch related alerts
      try {
        const alertsRes = await fetch(`${API_BASE_URL}/incidents/${incidentId}/alerts`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });
        if (alertsRes.ok) {
          const alertsData = await alertsRes.json();
          setRelatedAlerts(alertsData.alerts || []);
        }
      } catch (err) {
        console.log('No related alerts found');
      }

    } catch (error) {
      console.error('Error fetching incident:', error);
    } finally {
      setIsLoading(false);
    }
  }, [incidentId]);

  const fetchInsightsAndSimilar = useCallback(async () => {
    try {
      setLoadingInsights(true);
      const token = localStorage.getItem('access_token');

      // Fetch quick insights and similar incidents in parallel
      const [insightsRes, similarRes] = await Promise.all([
        fetch(`${API_BASE_URL}/incidents/${incidentId}/quick-insights`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }),
        fetch(`${API_BASE_URL}/incidents/${incidentId}/similar?limit=3`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        })
      ]);

      if (insightsRes.ok) {
        const insightsData = await insightsRes.json();
        setQuickInsights(insightsData);
      }

      if (similarRes.ok) {
        const similarData = await similarRes.json();
        setSimilarIncidents(similarData.similar_incidents || []);
      }
    } catch (error) {
      console.error('Error fetching insights:', error);
    } finally {
      setLoadingInsights(false);
    }
  }, [incidentId]);

  const fetchTeamMembers = useCallback(async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/organizations/me/members`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        setTeamMembers(data.members || []);
      }
    } catch (error) {
      console.error('Error fetching team members:', error);
    }
  }, []);

  const fetchCorrelatedTelemetry = useCallback(async () => {
    if (loadingTelemetry || correlatedTelemetry) return; // Prevent duplicate calls

    setLoadingTelemetry(true);
    setTelemetryError(null);
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/incidents/${incidentId}/correlated-telemetry?window_hours=1`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        setCorrelatedTelemetry(data);
      } else {
        const error = await response.json();
        setTelemetryError(error.detail || 'Failed to load telemetry');
      }
    } catch (error) {
      console.error('Error fetching correlated telemetry:', error);
      setTelemetryError('Failed to connect to server');
    } finally {
      setLoadingTelemetry(false);
    }
  }, [incidentId, loadingTelemetry, correlatedTelemetry]);

  const assignIncident = async (userId: string, userName: string) => {
    setIsAssigning(true);
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/incidents/${incidentId}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ assigned_to_id: userId }),
      });

      if (!response.ok) {
        throw new Error('Failed to assign incident');
      }

      const data = await response.json();
      setIncident(data);
      setShowAssignDropdown(false);

      showToast({
        type: 'success',
        title: 'Incident Assigned',
        message: `Incident assigned to ${userName}`,
        autoClose: true
      });
    } catch (error) {
      console.error('Error assigning incident:', error);
      showToast({
        type: 'error',
        title: 'Assignment Failed',
        message: 'Failed to assign incident',
        autoClose: true
      });
    } finally {
      setIsAssigning(false);
    }
  };

  const resolveWithNotes = async () => {
    setIsResolving(true);
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/incidents/${incidentId}/resolve`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ resolution_notes: resolutionNotes }),
      });

      if (!response.ok) {
        throw new Error('Failed to resolve incident');
      }

      const data = await response.json();
      setIncident(data);
      setShowResolveModal(false);
      setResolutionNotes('');

      showToast({
        type: 'success',
        title: 'Incident Resolved',
        message: 'Incident has been marked as resolved',
        autoClose: true
      });
    } catch (error) {
      console.error('Error resolving incident:', error);
      showToast({
        type: 'error',
        title: 'Resolution Failed',
        message: 'Failed to resolve incident',
        autoClose: true
      });
    } finally {
      setIsResolving(false);
    }
  };

  useEffect(() => {
    // Only fetch once per incident ID, or if the incident ID changed
    if (hasFetchedRef.current && currentIncidentIdRef.current === incidentId) {
      return;
    }

    hasFetchedRef.current = true;
    currentIncidentIdRef.current = incidentId;

    fetchIncident();
    fetchInsightsAndSimilar();
    fetchTeamMembers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [incidentId]);

  const updateIncidentStatus = async (newStatus: Incident['status']) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/incidents/${incidentId}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ status: newStatus }),
      });

      if (!response.ok) {
        throw new Error('Failed to update incident');
      }

      const data = await response.json();
      setIncident(data);

      showToast({
        type: 'success',
        title: 'Status Updated',
        message: `Incident marked as ${newStatus}`,
        autoClose: true
      });
    } catch (error) {
      console.error('Error updating incident:', error);
      showToast({
        type: 'error',
        title: 'Update Failed',
        message: 'Failed to update incident status',
        autoClose: true
      });
    }
  };

  const handleRequestAIAnalysis = () => {
    if (onShowAIAnalysis && incident) {
      onShowAIAnalysis(incident.id, {
        title: incident.title,
        severity: incident.severity,
        status: incident.status
      });
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'text-red-400 bg-red-500/10 border border-red-500/20';
      case 'high':
        return 'text-red-400 bg-red-500/10 border border-red-500/20';
      case 'medium':
        return 'text-yellow-400 bg-yellow-500/10 border border-yellow-500/20';
      case 'low':
        return 'text-blue-400 bg-blue-500/10 border border-blue-500/20';
      default:
        return 'text-muted-foreground bg-accent border border-border';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'open':
        return 'text-red-400 bg-red-500/10 border border-red-500/20';
      case 'acknowledged':
        return 'text-yellow-400 bg-yellow-500/10 border border-yellow-500/20';
      case 'resolved':
        return 'text-emerald-400 bg-emerald-500/10 border border-emerald-500/20';
      case 'closed':
        return 'text-muted-foreground bg-accent border border-border';
      default:
        return 'text-muted-foreground bg-accent border border-border';
    }
  };

  const formatDateTime = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    let relative = '';
    if (diffMins < 1) relative = 'Just now';
    else if (diffMins < 60) relative = `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`;
    else if (diffHours < 24) relative = `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
    else relative = `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;

    return {
      date: date.toLocaleDateString(),
      time: date.toLocaleTimeString(),
      relative
    };
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white"></div>
      </div>
    );
  }

  if (!incident) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <AlertTriangle className="w-16 h-16 text-red-400 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-foreground mb-2">Incident Not Found</h2>
          <p className="text-muted-foreground mb-6">The incident you're looking for doesn't exist or you don't have access to it.</p>
          <Button onClick={onBack} className="bg-primary text-primary-foreground hover:bg-white/90">
            Go Back
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex items-center justify-between">
            <button
              onClick={onBack}
              className="flex items-center space-x-2 text-muted-foreground hover:text-foreground transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
              <span className="text-sm">Back to Dashboard</span>
            </button>

            <div className="flex items-center space-x-3">
              <Button
                onClick={handleRequestAIAnalysis}
                className="bg-primary text-primary-foreground hover:bg-white/90 text-sm"
              >
                <Sparkles className="w-4 h-4 mr-2" />
                Get AI Analysis
              </Button>

              <Button
                variant="outline"
                onClick={() => setIsEditing(!isEditing)}
                className="border border-border text-foreground hover:bg-accent text-sm"
              >
                <Settings2 className="w-4 h-4 mr-2" />
                Edit
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6">
        {/* AI Insights Hero Card */}
        <AIInsightsHeroCard
          incidentId={incident.id}
          incidentTitle={incident.title}
          onViewFullAnalysis={() => {
            setActiveTab('telemetry');
            // Trigger telemetry fetch if not already loaded
            if (!correlatedTelemetry && !loadingTelemetry) {
              fetchCorrelatedTelemetry();
            }
          }}
          onAnalysisComplete={(data) => {
            setCorrelatedTelemetry(data);
          }}
        />

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Main Details */}
          <div className="lg:col-span-2 space-y-6">
            {/* Incident Header */}
            <div className="bg-transparent border border-border rounded-xl">
              <div className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium ${getSeverityColor(incident.severity)}`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${
                        incident.severity === 'critical' || incident.severity === 'high' ? 'bg-red-400' :
                        incident.severity === 'medium' ? 'bg-yellow-400' : 'bg-blue-400'
                      }`} />
                      {incident.severity.toUpperCase()}
                    </span>
                    <span className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium ${getStatusColor(incident.status)}`}>
                      {incident.status.toUpperCase()}
                    </span>
                  </div>
                  <div className="text-right text-sm text-muted-foreground">
                    <p>Created {incident.created_at ? formatDateTime(incident.created_at).relative : 'Unknown'}</p>
                  </div>
                </div>

                <div className="flex items-center space-x-3 mb-4">
                  <div className="w-1.5 h-1.5 bg-foreground rounded-full"></div>
                  <div>
                    <p className="text-sm text-foreground">Incident created</p>
                    <p className="text-sm text-muted-foreground">
                      {incident.created_at ? formatDateTime(incident.created_at).relative : 'Unknown'}</p>
                  </div>
                </div>

                <h1 className="text-[20px] font-semibold text-foreground mb-4">
                  {incident.title}
                </h1>

                {incident.description && (
                  <p className="text-sm text-muted-foreground leading-relaxed">{incident.description}</p>
                )}

                {incident.tags && incident.tags.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-4">
                    {incident.tags.map((tag, index) => (
                      <span key={index} className="inline-flex items-center px-2.5 py-1 rounded-md text-xs text-muted-foreground bg-accent border border-border">
                        #{tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex space-x-4">
              {incident.status === 'open' && (
                <Button
                  onClick={() => updateIncidentStatus('acknowledged')}
                  className="bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 hover:bg-yellow-500/20 text-sm"
                >
                  <CheckCircle className="w-4 h-4 mr-2" />
                  Acknowledge
                </Button>
              )}

              {(incident.status === 'open' || incident.status === 'acknowledged') && (
                <Button
                  onClick={() => setShowResolveModal(true)}
                  className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 text-sm"
                >
                  <CheckCircle className="w-4 h-4 mr-2" />
                  Resolve
                </Button>
              )}
            </div>

            {/* Tabs */}
            <div className="bg-transparent border border-border rounded-xl">
              <Tabs value={activeTab} onValueChange={setActiveTab}>
                <div className="p-6 pb-0">
                  <TabsList className="w-full justify-start bg-accent border border-border">
                    <TabsTrigger value="timeline" className="flex items-center gap-2 text-sm">
                      <Clock className="w-4 h-4" />
                      Timeline
                    </TabsTrigger>
                    <TabsTrigger value="comments" className="flex items-center gap-2 text-sm">
                      <MessageSquare className="w-4 h-4" />
                      Comments
                    </TabsTrigger>
                    <TabsTrigger value="attachments" className="flex items-center gap-2 text-sm">
                      <Paperclip className="w-4 h-4" />
                      Attachments
                    </TabsTrigger>
                    <TabsTrigger value="alerts" className="flex items-center gap-2 text-sm">
                      <AlertTriangle className="w-4 h-4" />
                      Related Alerts
                    </TabsTrigger>
                    <TabsTrigger
                      value="telemetry"
                      className="flex items-center gap-2 text-sm"
                      onClick={() => fetchCorrelatedTelemetry()}
                    >
                      <Database className="w-4 h-4" />
                      Related Telemetry
                      <Sparkles className="w-3 h-3 text-muted-foreground" />
                    </TabsTrigger>
                  </TabsList>
                </div>

                <div className="p-6">
                  {/* Timeline Tab */}
                  <TabsContent value="timeline">
                    <div className="space-y-4">
                      <div className="flex items-center space-x-3">
                        <span className="w-2 h-2 rounded-full bg-blue-400" />
                        <div>
                          <p className="text-sm text-foreground">Incident created</p>
                          <p className="text-sm text-muted-foreground">
                            {incident.created_at ? formatDateTime(incident.created_at).date : 'Unknown'} at {incident.created_at ? formatDateTime(incident.created_at).time : 'Unknown'}</p>
                          <p className="text-sm text-muted-foreground">{incident.created_at ? formatDateTime(incident.created_at).relative : 'Unknown'}</p>
                        </div>
                      </div>

                      {incident.resolved_at && (
                        <div className="flex items-center space-x-3">
                          <span className="w-2 h-2 rounded-full bg-emerald-400" />
                          <div>
                            <p className="text-sm text-foreground">Resolved</p>
                            <p className="text-sm text-muted-foreground">{formatDateTime(incident.resolved_at).date}</p>
                            <p className="text-sm text-muted-foreground">{formatDateTime(incident.resolved_at).relative}</p>
                          </div>
                        </div>
                      )}
                    </div>
                  </TabsContent>

                  {/* Comments Tab */}
                  <TabsContent value="comments">
                    <div className="space-y-4">
                      <p className="text-muted-foreground text-center py-8 text-sm">Comments feature temporarily disabled</p>
                    </div>
                  </TabsContent>

                  {/* Attachments Tab */}
                  <TabsContent value="attachments">
                    <div className="text-center py-8 text-muted-foreground">
                      <Paperclip className="w-12 h-12 mx-auto mb-3 opacity-50" />
                      <p className="text-sm">No attachments</p>
                    </div>
                  </TabsContent>

                  {/* Alerts Tab */}
                  <TabsContent value="alerts">
                    <div className="space-y-4">
                      {relatedAlerts && relatedAlerts.length > 0 ? (
                        relatedAlerts.map((alert: any) => (
                          <div
                            key={alert.id}
                            className="bg-transparent border border-border rounded-xl cursor-pointer hover:bg-accent/50 transition-colors"
                          >
                            <div
                              onClick={() => onNavigateToAlert?.(alert.id)}
                              className="p-4"
                            >
                              <div className="flex items-center justify-between">
                                <div className="flex-1">
                                  <h4 className="text-sm text-foreground font-medium mb-1">{alert.title}</h4>
                                  <p className="text-muted-foreground text-sm mb-2">{alert.description || 'No description'}</p>
                                  <div className="flex items-center gap-2">
                                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs ${getSeverityColor(alert.severity)}`}>
                                      {alert.severity}
                                    </span>
                                    <span className="text-muted-foreground text-xs">Source: {alert.source}</span>
                                    {alert.service_name && (
                                      <span className="text-muted-foreground text-xs">Service: {alert.service_name}</span>
                                    )}
                                  </div>
                                </div>
                                <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground text-sm">
                                  View Details
                                  <ArrowLeft className="w-4 h-4 ml-1 transform rotate-180" />
                                </Button>
                              </div>
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="text-center py-8 text-muted-foreground">
                          <AlertTriangle className="w-12 h-12 mx-auto mb-3 opacity-50" />
                          <p className="text-sm">No related alerts for this incident</p>
                        </div>
                      )}
                    </div>
                  </TabsContent>

                  {/* Correlated Telemetry Tab */}
                  <TabsContent value="telemetry">
                    <div className="space-y-6">
                      {loadingTelemetry ? (
                        <div className="flex flex-col items-center justify-center py-12">
                          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white mb-4"></div>
                          <p className="text-muted-foreground text-sm">Analyzing telemetry with AI...</p>
                        </div>
                      ) : telemetryError ? (
                        <div className="text-center py-8">
                          <AlertTriangle className="w-12 h-12 mx-auto mb-3 text-yellow-500 opacity-75" />
                          <p className="text-muted-foreground text-sm">{telemetryError}</p>
                          <Button
                            variant="outline"
                            size="sm"
                            className="mt-4 border border-border text-foreground hover:bg-accent text-sm"
                            onClick={() => {
                              setCorrelatedTelemetry(null);
                              setTelemetryError(null);
                              fetchCorrelatedTelemetry();
                            }}
                          >
                            Retry
                          </Button>
                        </div>
                      ) : correlatedTelemetry ? (
                        <div className="space-y-6">
                          {/* AI Analysis Card */}
                          <div className="bg-transparent border border-border rounded-xl">
                            <div className="p-4">
                              <div className="flex items-center gap-3 mb-3">
                                <div className="w-6 h-6 bg-secondary rounded flex items-center justify-center">
                                  <Sparkles className="w-4 h-4 text-muted-foreground" />
                                </div>
                                <div>
                                  <h4 className="text-sm text-foreground font-medium mb-1">AI Root Cause Analysis</h4>
                                  <p className="text-sm text-muted-foreground">
                                    {correlatedTelemetry.ai_analysis?.root_cause_hypothesis || 'No hypothesis available'}
                                  </p>
                                </div>
                              </div>
                              <div className="flex items-center gap-4 text-xs text-muted-foreground mt-3 pt-3 border-t border-border">
                                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs text-blue-400 bg-blue-500/10 border border-blue-500/20">
                                  Confidence: {Math.round((correlatedTelemetry.ai_analysis?.confidence || 0) * 100)}%
                                </span>
                                <span>Analyzed in: {correlatedTelemetry.analysis_time_ms?.toFixed(0)}ms</span>
                                <span>{correlatedTelemetry.total_traces_analyzed} traces, {correlatedTelemetry.total_logs_analyzed} logs analyzed</span>
                              </div>

                              {correlatedTelemetry.ai_analysis?.recommended_actions && (
                                <div className="mt-4 pt-3 border-t border-border">
                                  <h5 className="text-sm font-medium text-foreground mb-2">Recommended Actions</h5>
                                  <ul className="space-y-1">
                                    {correlatedTelemetry.ai_analysis.recommended_actions.map((action: string, i: number) => (
                                      <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                                        <span className="text-muted-foreground">&#8226;</span>
                                        {action}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                            </div>
                          </div>

                          {/* Related Traces */}
                          {correlatedTelemetry.traces && correlatedTelemetry.traces.length > 0 && (
                            <div>
                              <h4 className="text-base text-foreground font-medium mb-3 flex items-center gap-2">
                                <Search className="w-4 h-4" />
                                Related Traces ({correlatedTelemetry.traces.length})
                              </h4>
                              <div className="space-y-2 max-h-60 overflow-y-auto">
                                {correlatedTelemetry.traces.slice(0, 10).map((trace: any, i: number) => (
                                  <div key={i} className="p-3 bg-secondary/50 rounded-lg border border-border text-sm">
                                    <div className="flex items-center justify-between mb-1">
                                      <span className="font-mono text-xs text-muted-foreground">{trace.trace_id?.slice(0, 16)}...</span>
                                      <div className="flex items-center gap-2">
                                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs ${trace.status_code === 'ERROR' ? 'text-red-400 bg-red-500/10 border border-red-500/20' : 'text-muted-foreground bg-accent border border-border'}`}>
                                          {trace.status_code}
                                        </span>
                                        {trace.relevance_score > 0.5 && (
                                          <span className="text-muted-foreground text-xs">{Math.round(trace.relevance_score * 100)}% relevant</span>
                                        )}
                                      </div>
                                    </div>
                                    <p className="text-foreground text-sm">{trace.service_name} / {trace.operation_name || 'unknown'}</p>
                                    <p className="text-muted-foreground text-xs mt-1">
                                      {trace.duration_ms?.toFixed(0)}ms -- {new Date(trace.timestamp).toLocaleTimeString()}
                                    </p>
                                    {trace.relevance_reason && (
                                      <p className="text-muted-foreground text-xs mt-1">{trace.relevance_reason}</p>
                                    )}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Related Logs */}
                          {correlatedTelemetry.logs && correlatedTelemetry.logs.length > 0 && (
                            <div>
                              <div className="flex items-center justify-between mb-3">
                                <h4 className="text-base text-foreground font-medium flex items-center gap-2">
                                  <MessageSquare className="w-4 h-4" />
                                  Related Logs ({correlatedTelemetry.logs.length})
                                </h4>
                              </div>

                              {/* Log Filters */}
                              <div className="mb-4 p-3 bg-secondary/30 rounded-lg border border-border">
                                <div className="flex flex-wrap items-center gap-3">
                                  {/* Search */}
                                  <div className="flex-1 min-w-[200px] relative">
                                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                                    <input
                                      type="text"
                                      value={logSearchQuery}
                                      onChange={(e) => setLogSearchQuery(e.target.value)}
                                      placeholder="Search logs..."
                                      className="w-full pl-9 pr-3 py-1.5 bg-accent border border-border rounded text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
                                    />
                                    {logSearchQuery && (
                                      <button
                                        onClick={() => setLogSearchQuery('')}
                                        className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                                      >
                                        <X className="h-3 w-3" />
                                      </button>
                                    )}
                                  </div>

                                  {/* Level Filters */}
                                  <div className="flex items-center gap-1">
                                    {['ERROR', 'WARN', 'INFO'].map((level) => (
                                      <button
                                        key={level}
                                        onClick={() => {
                                          setLogLevelFilter(prev =>
                                            prev.includes(level)
                                              ? prev.filter(l => l !== level)
                                              : [...prev, level]
                                          );
                                        }}
                                        className={`px-2 py-1 rounded text-xs transition-colors ${
                                          logLevelFilter.includes(level)
                                            ? level === 'ERROR' ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                                            : level === 'WARN' ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
                                            : 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                                            : 'bg-accent text-muted-foreground border border-border hover:bg-secondary'
                                        }`}
                                      >
                                        {level}
                                      </button>
                                    ))}
                                  </div>

                                  {/* Service Filter */}
                                  <select
                                    value={logServiceFilter}
                                    onChange={(e) => setLogServiceFilter(e.target.value)}
                                    className="px-2 py-1.5 bg-accent border border-border rounded text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
                                  >
                                    <option value="">All Services</option>
                                    {Array.from(new Set(correlatedTelemetry.logs.map((log: any) => log.service).filter(Boolean))).map((service: any) => (
                                      <option key={service} value={service}>{service}</option>
                                    ))}
                                  </select>

                                  {/* Clear All Filters */}
                                  {(logSearchQuery || logLevelFilter.length > 0 || logServiceFilter) && (
                                    <button
                                      onClick={() => {
                                        setLogSearchQuery('');
                                        setLogLevelFilter([]);
                                        setLogServiceFilter('');
                                      }}
                                      className="px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
                                    >
                                      Clear filters
                                    </button>
                                  )}
                                </div>
                              </div>

                              {/* Filtered Logs */}
                              {(() => {
                                const filteredLogs = correlatedTelemetry.logs.filter((log: any) => {
                                  const matchesSearch = !logSearchQuery ||
                                    log.message?.toLowerCase().includes(logSearchQuery.toLowerCase()) ||
                                    log.service?.toLowerCase().includes(logSearchQuery.toLowerCase());
                                  const matchesLevel = logLevelFilter.length === 0 || logLevelFilter.includes(log.level);
                                  const matchesService = !logServiceFilter || log.service === logServiceFilter;
                                  return matchesSearch && matchesLevel && matchesService;
                                });

                                return (
                                  <>
                                    <div className="text-xs text-muted-foreground mb-2">
                                      Showing {filteredLogs.length} of {correlatedTelemetry.logs.length} logs
                                    </div>
                                    <div className="space-y-2 max-h-80 overflow-y-auto">
                                      {filteredLogs.length === 0 ? (
                                        <div className="text-center py-6 text-muted-foreground">
                                          <Filter className="w-8 h-8 mx-auto mb-2 opacity-50" />
                                          <p className="text-sm">No logs match your filters</p>
                                        </div>
                                      ) : (
                                        filteredLogs.slice(0, 50).map((log: any, i: number) => (
                                          <div key={i} className="p-3 bg-secondary/50 rounded-lg border border-border text-sm">
                                            <div className="flex items-center justify-between mb-1">
                                              <div className="flex items-center gap-2">
                                                <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs ${
                                                  ['ERROR', 'FATAL', 'CRITICAL'].includes(log.level) ? 'text-red-400 bg-red-500/10 border border-red-500/20' :
                                                  log.level === 'WARN' ? 'text-yellow-400 bg-yellow-500/10 border border-yellow-500/20' : 'text-muted-foreground bg-accent border border-border'
                                                }`}>
                                                  {log.level}
                                                </span>
                                                <span className="text-muted-foreground text-xs">{log.service}</span>
                                              </div>
                                              {log.relevance_score > 0.5 && (
                                                <span className="text-muted-foreground text-xs">{Math.round(log.relevance_score * 100)}% relevant</span>
                                              )}
                                            </div>
                                            <p className="text-foreground text-sm break-words">{log.message?.slice(0, 200)}{log.message?.length > 200 ? '...' : ''}</p>
                                            <p className="text-muted-foreground text-xs mt-1">
                                              {new Date(log.timestamp).toLocaleString()}
                                            </p>
                                          </div>
                                        ))
                                      )}
                                    </div>
                                  </>
                                );
                              })()}
                            </div>
                          )}

                          {/* No data state */}
                          {(!correlatedTelemetry.traces || correlatedTelemetry.traces.length === 0) &&
                           (!correlatedTelemetry.logs || correlatedTelemetry.logs.length === 0) && (
                            <div className="text-center py-8 text-muted-foreground">
                              <Database className="w-12 h-12 mx-auto mb-3 opacity-50" />
                              <p className="text-sm">No telemetry data found in the time window</p>
                              <p className="text-sm mt-2">Make sure your agent is sending traces and logs</p>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="text-center py-12">
                          <Database className="w-12 h-12 mx-auto mb-3 text-muted-foreground opacity-50" />
                          <p className="text-muted-foreground mb-2 text-sm">Click to analyze related traces and logs</p>
                          <p className="text-sm text-muted-foreground mb-4">
                            AI will identify telemetry correlated with this incident
                          </p>
                          <Button
                            onClick={fetchCorrelatedTelemetry}
                            className="bg-primary text-primary-foreground hover:bg-white/90 text-sm"
                          >
                            <Sparkles className="w-4 h-4 mr-2" />
                            Analyze Telemetry
                          </Button>
                        </div>
                      )}
                    </div>
                  </TabsContent>
                </div>
              </Tabs>
            </div>

            {/* AI Chat Section */}
            <IncidentAIChat
              incidentId={incident.id}
              incidentContext={{
                title: incident.title,
                description: incident.description,
                severity: incident.severity,
                status: incident.status,
                tags: incident.tags || []
              }}
            />
          </div>

          {/* Right Column - Metadata & Insights */}
          <div className="space-y-6">
            {/* Incident Metadata */}
            <div className="bg-transparent border border-border rounded-xl">
              <div className="p-6">
                <h3 className="text-base font-medium text-foreground">Details</h3>
              </div>
              <div className="p-6 pt-0 space-y-4">
                <div>
                  <p className="text-xs uppercase tracking-wider text-muted-foreground mb-1">Created</p>
                  <p className="text-sm text-foreground">{incident.created_at ? formatDateTime(incident.created_at).date : 'Unknown'} at {incident.created_at ? formatDateTime(incident.created_at).time : 'Unknown'}</p>
                  <p className="text-sm text-muted-foreground">{incident.created_at ? formatDateTime(incident.created_at).relative : 'Unknown'}</p>
                </div>

                {incident.resolved_at && (
                  <div>
                    <p className="text-xs uppercase tracking-wider text-muted-foreground mb-1">Resolved</p>
                    <p className="text-sm text-foreground">{formatDateTime(incident.resolved_at).date}</p>
                    <p className="text-sm text-muted-foreground">{formatDateTime(incident.resolved_at).relative}</p>
                  </div>
                )}

                {/* Assign To Section */}
                <div className="relative">
                  <p className="text-xs uppercase tracking-wider text-muted-foreground mb-2">Assigned to</p>
                  {incident.assigned_to_name ? (
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <div className="w-8 h-8 bg-secondary rounded-full flex items-center justify-center">
                          <span className="text-foreground text-sm font-medium">
                            {incident.assigned_to_name.split(' ').map(n => n[0]).join('').toUpperCase()}
                          </span>
                        </div>
                        <span className="text-sm text-foreground">{incident.assigned_to_name}</span>
                      </div>
                      <button
                        onClick={() => setShowAssignDropdown(!showAssignDropdown)}
                        className="text-xs text-muted-foreground hover:text-foreground"
                      >
                        Change
                      </button>
                    </div>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setShowAssignDropdown(!showAssignDropdown)}
                      className="w-full border-dashed border-border text-muted-foreground hover:bg-accent text-sm"
                    >
                      <UserPlus className="w-4 h-4 mr-2" />
                      Assign to someone
                    </Button>
                  )}

                  {/* Dropdown Menu */}
                  {showAssignDropdown && (
                    <div className="absolute top-full left-0 right-0 mt-2 bg-card border border-border rounded-lg z-50 max-h-64 overflow-y-auto">
                      <div className="p-2">
                        <p className="text-xs uppercase tracking-wider text-muted-foreground px-2 py-1 mb-1">Team Members</p>
                        {teamMembers.length === 0 ? (
                          <p className="text-sm text-muted-foreground px-2 py-2">No team members found</p>
                        ) : (
                          teamMembers.map((member) => (
                            <button
                              key={member.id}
                              onClick={() => assignIncident(member.id, member.full_name)}
                              disabled={isAssigning}
                              className="w-full flex items-center gap-3 px-2 py-2 hover:bg-accent rounded-md transition-colors disabled:opacity-50"
                            >
                              <div className="w-8 h-8 bg-secondary rounded-full flex items-center justify-center flex-shrink-0">
                                <span className="text-foreground text-sm font-medium">
                                  {member.full_name.split(' ').map(n => n[0]).join('').toUpperCase()}
                                </span>
                              </div>
                              <div className="flex-1 text-left">
                                <p className="text-sm text-foreground">{member.full_name}</p>
                                <p className="text-xs text-muted-foreground">{member.email}</p>
                              </div>
                              {incident.assigned_to_id === member.id && (
                                <CheckCircle className="w-4 h-4 text-emerald-400" />
                              )}
                            </button>
                          ))
                        )}
                      </div>
                    </div>
                  )}
                </div>

                {incident.created_by_name && (
                  <div>
                    <p className="text-xs uppercase tracking-wider text-muted-foreground mb-1">Created by</p>
                    <p className="text-sm text-foreground">{incident.created_by_name}</p>
                  </div>
                )}
              </div>
            </div>

            {/* AI Insights */}
            <div className="bg-transparent border border-border rounded-xl">
              <div className="p-6">
                <h3 className="text-base font-medium text-foreground flex items-center">
                  <div className="w-6 h-6 bg-secondary rounded text-muted-foreground text-xs flex items-center justify-center mr-2">
                    <Sparkles className="w-4 h-4" />
                  </div>
                  AI Insights
                </h3>
              </div>
              <div className="p-6 pt-0 space-y-3">
                {loadingInsights ? (
                  <div className="flex items-center justify-center py-4">
                    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-white"></div>
                  </div>
                ) : quickInsights ? (
                  <>
                    <div className="bg-secondary/50 border border-border rounded-lg p-3">
                      <p className="text-sm text-muted-foreground">
                        <strong className="text-foreground">Suggested Action:</strong> {quickInsights.suggested_action}
                      </p>
                    </div>
                    <div className="bg-secondary/50 border border-border rounded-lg p-3">
                      <p className="text-sm text-muted-foreground">
                        <strong className="text-foreground">Similar Incidents:</strong> {quickInsights.similar_incidents_count} similar incidents
                        {quickInsights.avg_resolution_time_minutes && (
                          <> resolved in avg {quickInsights.avg_resolution_time_minutes} minutes</>
                        )}
                      </p>
                    </div>
                    <div className="bg-secondary/50 border border-border rounded-lg p-3">
                      <p className="text-sm text-muted-foreground">
                        <strong className="text-foreground">Risk Assessment:</strong> {quickInsights.risk_assessment}
                      </p>
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground text-center py-4">
                    Unable to load insights
                  </p>
                )}
              </div>
            </div>

            {/* AI Root Cause Analysis Panel */}
            <AIRootCausePanel
              incidentId={incident.id}
              incidentTitle={incident.title}
              isExpanded={false}
            />

            {/* Similar Past Incidents */}
            {similarIncidents.length > 0 && (
              <div className="bg-transparent border border-border rounded-xl">
                <div className="p-6">
                  <h3 className="text-base font-medium text-foreground flex items-center">
                    <div className="w-6 h-6 bg-secondary rounded flex items-center justify-center mr-2">
                      <Clock className="w-4 h-4 text-muted-foreground" />
                    </div>
                    Similar Past Incidents
                  </h3>
                </div>
                <div className="p-6 pt-0 space-y-3">
                  {similarIncidents.map((similar) => (
                    <div
                      key={similar.id}
                      className="p-3 bg-secondary/50 rounded-lg border border-border hover:bg-accent cursor-pointer transition-colors"
                      onClick={() => {
                        // Navigate to similar incident
                        window.location.href = `/incidents/${similar.id}`;
                      }}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <h4 className="text-sm font-medium text-foreground mb-1 line-clamp-2">
                            {similar.title}
                          </h4>
                          <div className="flex items-center gap-2 text-xs">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs ${getSeverityColor(similar.severity)}`}>
                              {similar.severity}
                            </span>
                            {similar.resolution_time_minutes && (
                              <span className="text-emerald-400">
                                Resolved in {similar.resolution_time_minutes}m
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-muted-foreground mt-1">
                            {similar.match_reasons.join(' -- ')}
                          </p>
                        </div>
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs text-blue-400 bg-blue-500/10 border border-blue-500/20">
                          {similar.match_score}% match
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Runbook Suggestions */}
            <RunbookSuggestions
              incidentId={incident.id}
              onExecutionStarted={(executionId) => setActiveExecutionId(executionId)}
            />

            {/* Runbook Execution Monitor */}
            {activeExecutionId && (
              <RunbookExecutionMonitor
                executionId={activeExecutionId}
                onClose={() => setActiveExecutionId(null)}
                onCompleted={(success) => {
                  if (success) {
                    showToast({
                      type: 'success',
                      title: 'Runbook Completed',
                      message: 'The runbook executed successfully',
                      autoClose: true
                    });
                    fetchIncident();
                  }
                }}
              />
            )}
          </div>
        </div>
      </div>

      {/* Resolve Modal */}
      {showResolveModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-card border border-border rounded-xl w-full max-w-md mx-4">
            <div className="p-6">
              <div className="flex items-center mb-4">
                <div className="p-2 rounded-lg bg-emerald-500/10 mr-3">
                  <CheckCircle className="w-5 h-5 text-emerald-400" />
                </div>
                <h3 className="text-base font-medium text-foreground">Resolve Incident</h3>
              </div>

              <p className="text-muted-foreground text-sm mb-4">
                Add resolution notes to document how this incident was resolved. This helps with future troubleshooting.
              </p>

              <div className="space-y-4">
                <div>
                  <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-2">
                    Resolution Notes (optional)
                  </label>
                  <textarea
                    value={resolutionNotes}
                    onChange={(e) => setResolutionNotes(e.target.value)}
                    placeholder="Describe how this incident was resolved..."
                    rows={4}
                    className="w-full px-4 py-3 bg-accent border border-border rounded-xl text-foreground placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-white/20 resize-none text-sm"
                    disabled={isResolving}
                  />
                </div>
              </div>

              <div className="flex justify-end gap-3 mt-6">
                <Button
                  variant="ghost"
                  onClick={() => {
                    setShowResolveModal(false);
                    setResolutionNotes('');
                  }}
                  disabled={isResolving}
                  className="text-muted-foreground hover:text-foreground hover:bg-accent text-sm"
                >
                  Cancel
                </Button>
                <Button
                  onClick={resolveWithNotes}
                  disabled={isResolving}
                  className="bg-primary text-primary-foreground hover:bg-white/90 text-sm"
                >
                  {isResolving ? (
                    <>
                      <div className="w-4 h-4 border-2 border-black/30 border-t-black rounded-full animate-spin mr-2" />
                      Resolving...
                    </>
                  ) : (
                    <>
                      <CheckCircle className="w-4 h-4 mr-2" />
                      Resolve Incident
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default IncidentDetail;
