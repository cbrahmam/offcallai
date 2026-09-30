// Deployment Timeline - Track deployments with incident correlation
import React, { useCallback, useEffect, useState, useMemo } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { API_URL } from '../config/api';

// Types
interface DeploymentTimelineItem {
  id: string;
  service_name: string;
  version: string;
  environment: string;
  deployed_at: string;
  status: 'in_progress' | 'success' | 'failed' | 'rolling_back' | 'rolled_back';
  deployed_by?: string;
  commit_sha?: string;
  incidents_within_30min: number;
  alerts_within_30min: number;
  has_issues: boolean;
}

interface DeploymentTimeline {
  items: DeploymentTimelineItem[];
  time_range_hours: number;
  total_deployments: number;
  deployments_with_issues: number;
}

interface DeploymentStats {
  total_deployments: number;
  status_breakdown: Record<string, number>;
  deployments_with_incidents: number;
  incident_rate: number;
  top_services: Array<{ service: string; count: number }>;
  daily_counts: Array<{ date: string; count: number }>;
  period_days: number;
}

interface DeploymentCorrelation {
  deployment: DeploymentTimelineItem & {
    commit_message?: string;
    branch?: string;
    repository?: string;
    pull_request_url?: string;
    pull_request_number?: number;
    duration_seconds?: number;
    tags?: Record<string, string>;
    extra_data?: Record<string, unknown>;
    description?: string;
  };
  correlated_incidents: Array<{
    id: string;
    title: string;
    severity: string;
    status: string;
    created_at: string;
  }>;
  correlated_alerts: Array<{
    id: string;
    title: string;
    severity: string;
    status: string;
    created_at: string;
  }>;
  correlation_window_minutes: number;
}

// Status colors
const statusColors = {
  in_progress: { bg: 'bg-blue-500', text: 'text-blue-400', border: 'border-blue-500' },
  success: { bg: 'bg-green-500', text: 'text-green-400', border: 'border-green-500' },
  failed: { bg: 'bg-red-500', text: 'text-red-400', border: 'border-red-500' },
  rolling_back: { bg: 'bg-yellow-500', text: 'text-yellow-400', border: 'border-yellow-500' },
  rolled_back: { bg: 'bg-orange-500', text: 'text-orange-400', border: 'border-orange-500' },
};

const statusLabels = {
  in_progress: 'In Progress',
  success: 'Success',
  failed: 'Failed',
  rolling_back: 'Rolling Back',
  rolled_back: 'Rolled Back',
};

const DeploymentTimeline: React.FC = () => {
  const { token } = useAuth();
  const [timeline, setTimeline] = useState<DeploymentTimeline | null>(null);
  const [stats, setStats] = useState<DeploymentStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState(24);
  const [selectedDeployment, setSelectedDeployment] = useState<string | null>(null);
  const [correlation, setCorrelation] = useState<DeploymentCorrelation | null>(null);
  const [correlationLoading, setCorrelationLoading] = useState(false);
  const [serviceFilter, setServiceFilter] = useState<string>('');
  const [environmentFilter, setEnvironmentFilter] = useState<string>('');

  // Fetch timeline data
  const fetchTimeline = useCallback(async () => {
    if (!token) {
      setTimeline(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({ hours: String(timeRange) });
      if (serviceFilter) params.append('service_name', serviceFilter);
      if (environmentFilter) params.append('environment', environmentFilter);

      const response = await fetch(
        `${API_URL}/deployments/timeline?${params}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch timeline: ${response.status}`);
      }

      const data: DeploymentTimeline = await response.json();
      setTimeline(data);
    } catch (err) {
      console.error('Failed to fetch timeline:', err);
      setTimeline(null);
      setError('Failed to fetch deployment timeline');
    } finally {
      setLoading(false);
    }
  }, [token, timeRange, serviceFilter, environmentFilter]);

  // Fetch stats
  const fetchStats = useCallback(async () => {
    if (!token) {
      setStats(null);
      return;
    }

    try {
      const response = await fetch(`${API_URL}/deployments/stats?days=30`, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        setStats(null);
        return;
      }

      const data: DeploymentStats = await response.json();
      setStats(data);
    } catch {
      console.log('Failed to fetch stats');
      setStats(null);
    }
  }, [token]);

  // Fetch correlation details
  const fetchCorrelation = useCallback(
    async (deploymentId: string) => {
      if (!token) {
        setCorrelation(null);
        return;
      }

      setCorrelationLoading(true);

      try {
        const response = await fetch(
          `${API_URL}/deployments/${deploymentId}/correlation`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
          }
        );

        if (!response.ok) {
          throw new Error(`Failed to fetch correlation: ${response.status}`);
        }

        const data: DeploymentCorrelation = await response.json();
        setCorrelation(data);
      } catch (err) {
        console.error('Failed to fetch correlation:', err);
        setCorrelation(null);
      } finally {
        setCorrelationLoading(false);
      }
    },
    [token]
  );

  useEffect(() => {
    fetchTimeline();
    fetchStats();
  }, [fetchTimeline, fetchStats]);

  useEffect(() => {
    if (selectedDeployment) {
      fetchCorrelation(selectedDeployment);
    } else {
      setCorrelation(null);
    }
  }, [selectedDeployment, fetchCorrelation]);

  // Get unique services and environments for filters
  const { services, environments } = useMemo(() => {
    if (!timeline) return { services: [], environments: [] };

    const serviceSet = new Set(timeline.items.map((d) => d.service_name));
    const envSet = new Set(timeline.items.map((d) => d.environment));

    return {
      services: Array.from(serviceSet).sort(),
      environments: Array.from(envSet).sort(),
    };
  }, [timeline]);

  // Format date for display
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Format relative time
  const formatRelativeTime = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  if (loading) {
    return (
      <div className="bg-muted rounded-xl p-8 flex items-center justify-center min-h-[600px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
          <p className="text-muted-foreground mt-4">Loading deployment timeline...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-muted rounded-xl p-8 min-h-[600px]">
        <div className="text-center text-red-400">
          <svg
            className="h-12 w-12 mx-auto mb-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
          <p>{error}</p>
          <button
            onClick={fetchTimeline}
            className="mt-4 px-4 py-2 bg-blue-600 text-foreground rounded-lg hover:bg-blue-700 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="relative overflow-hidden border-b border-border">
        <div className="relative max-w-7xl mx-auto px-6 py-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-teal-500/10">
                <svg className="w-6 h-6 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>
              <div>
                <h1 className="text-base font-medium text-foreground">Deployments</h1>
                <p className="text-muted-foreground text-sm">Track deployments and correlate with incidents</p>
              </div>
            </div>
            <button
              onClick={fetchTimeline}
              className="flex items-center gap-2 px-4 py-2 bg-muted hover:bg-muted/80 rounded-lg text-sm"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Refresh
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* Stats Overview */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-muted/50 border border-border rounded-xl p-4">
            <div className="text-sm text-muted-foreground">Total Deployments (30d)</div>
            <div className="text-2xl font-bold text-foreground mt-1">
              {stats.total_deployments}
            </div>
          </div>
          <div className="bg-muted/50 border border-border rounded-xl p-4">
            <div className="text-sm text-muted-foreground">Success Rate</div>
            <div className="text-2xl font-bold text-green-400 mt-1">
              {stats.total_deployments > 0
                ? Math.round(
                    ((stats.status_breakdown.success || 0) / stats.total_deployments) * 100
                  )
                : 0}
              %
            </div>
          </div>
          <div className="bg-muted/50 border border-border rounded-xl p-4">
            <div className="text-sm text-muted-foreground">With Incidents</div>
            <div className="text-2xl font-bold text-red-400 mt-1">
              {stats.deployments_with_incidents}
            </div>
          </div>
          <div className="bg-muted/50 border border-border rounded-xl p-4">
            <div className="text-sm text-muted-foreground">Incident Rate</div>
            <div className="text-2xl font-bold text-yellow-400 mt-1">
              {stats.incident_rate}%
            </div>
          </div>
        </div>
      )}

      {/* Main Timeline */}
      <div className="bg-muted rounded-xl overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b border-border">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-bold text-foreground">Deployment Timeline</h2>
              <p className="text-sm text-muted-foreground mt-1">
                {timeline?.total_deployments || 0} deployments,{' '}
                {timeline?.deployments_with_issues || 0} with issues
              </p>
            </div>

            {/* Filters */}
            <div className="flex flex-wrap items-center gap-3">
              <select
                value={serviceFilter}
                onChange={(e) => setServiceFilter(e.target.value)}
                className="bg-muted text-foreground px-3 py-2 rounded-lg border border-border text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All Services</option>
                {services.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>

              <select
                value={environmentFilter}
                onChange={(e) => setEnvironmentFilter(e.target.value)}
                className="bg-muted text-foreground px-3 py-2 rounded-lg border border-border text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All Environments</option>
                {environments.map((e) => (
                  <option key={e} value={e}>
                    {e}
                  </option>
                ))}
              </select>

              <select
                value={timeRange}
                onChange={(e) => setTimeRange(Number(e.target.value))}
                className="bg-muted text-foreground px-3 py-2 rounded-lg border border-border text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value={6}>Last 6 hours</option>
                <option value={24}>Last 24 hours</option>
                <option value={72}>Last 3 days</option>
                <option value={168}>Last 7 days</option>
              </select>

              <button
                onClick={fetchTimeline}
                className="p-2 text-muted-foreground hover:text-foreground transition-colors"
                title="Refresh"
              >
                <svg
                  className="h-5 w-5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                  />
                </svg>
              </button>
            </div>
          </div>
        </div>

        {/* Timeline Content */}
        <div className="flex">
          {/* Left: Timeline List */}
          <div
            className={`flex-1 ${
              selectedDeployment ? 'border-r border-border' : ''
            }`}
          >
            {!timeline || timeline.items.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground">
                <svg
                  className="h-16 w-16 mx-auto mb-4 text-muted-foreground"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  />
                </svg>
                <h3 className="text-lg font-medium text-foreground">No Deployments</h3>
                <p className="mt-2 text-sm">
                  No deployments found in the selected time range.
                  <br />
                  Integrate your CI/CD to start tracking deployments.
                </p>
              </div>
            ) : (
              <div className="divide-y divide-border max-h-[600px] overflow-y-auto">
                {timeline.items.map((deployment) => {
                  const colors = statusColors[deployment.status] || statusColors.success;
                  const isSelected = selectedDeployment === deployment.id;

                  return (
                    <div
                      key={deployment.id}
                      onClick={() =>
                        setSelectedDeployment(isSelected ? null : deployment.id)
                      }
                      className={`p-4 cursor-pointer transition-colors ${
                        isSelected
                          ? 'bg-accent border-l-4 border-blue-500'
                          : 'hover:bg-accent border-l-4 border-transparent'
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-start gap-3">
                          {/* Status indicator */}
                          <div
                            className={`w-3 h-3 rounded-full mt-1.5 ${colors.bg}`}
                          ></div>

                          <div>
                            {/* Service and version */}
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-foreground">
                                {deployment.service_name}
                              </span>
                              <span className="text-sm text-muted-foreground">
                                v{deployment.version}
                              </span>
                              <span
                                className={`text-xs px-2 py-0.5 rounded ${
                                  deployment.environment === 'production'
                                    ? 'bg-red-500/20 text-red-400'
                                    : 'bg-muted text-muted-foreground'
                                }`}
                              >
                                {deployment.environment}
                              </span>
                            </div>

                            {/* Metadata */}
                            <div className="flex items-center gap-4 mt-1 text-sm text-muted-foreground">
                              <span>{formatDate(deployment.deployed_at)}</span>
                              {deployment.deployed_by && (
                                <span>by {deployment.deployed_by}</span>
                              )}
                              {deployment.commit_sha && (
                                <span className="font-mono text-xs">
                                  {deployment.commit_sha.substring(0, 7)}
                                </span>
                              )}
                            </div>

                            {/* Issues badge */}
                            {deployment.has_issues && (
                              <div className="flex items-center gap-2 mt-2">
                                {deployment.incidents_within_30min > 0 && (
                                  <span className="text-xs bg-red-500/20 text-red-400 px-2 py-0.5 rounded">
                                    {deployment.incidents_within_30min} incident
                                    {deployment.incidents_within_30min !== 1 ? 's' : ''}
                                  </span>
                                )}
                                {deployment.alerts_within_30min > 0 && (
                                  <span className="text-xs bg-yellow-500/20 text-yellow-400 px-2 py-0.5 rounded">
                                    {deployment.alerts_within_30min} alert
                                    {deployment.alerts_within_30min !== 1 ? 's' : ''}
                                  </span>
                                )}
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Status badge */}
                        <span className={`text-sm ${colors.text}`}>
                          {statusLabels[deployment.status]}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Right: Correlation Details */}
          {selectedDeployment && (
            <div className="w-96 p-4 bg-muted/30">
              {correlationLoading ? (
                <div className="flex items-center justify-center h-48">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                </div>
              ) : correlation ? (
                <div className="space-y-4">
                  <div>
                    <h3 className="text-lg font-semibold text-foreground">
                      Deployment Details
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      {formatRelativeTime(correlation.deployment.deployed_at)}
                    </p>
                  </div>

                  {/* Commit info */}
                  {correlation.deployment.commit_sha && (
                    <div className="bg-muted/50 rounded-lg p-3">
                      <div className="text-sm font-medium text-foreground">
                        Commit
                      </div>
                      <div className="mt-1">
                        <div className="font-mono text-sm text-blue-400">
                          {correlation.deployment.commit_sha.substring(0, 7)}
                        </div>
                        {correlation.deployment.commit_message && (
                          <div className="text-sm text-muted-foreground mt-1 line-clamp-2">
                            {correlation.deployment.commit_message}
                          </div>
                        )}
                        {correlation.deployment.branch && (
                          <div className="text-xs text-muted-foreground mt-1">
                            Branch: {correlation.deployment.branch}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Correlated Incidents */}
                  <div>
                    <h4 className="text-sm font-medium text-foreground mb-2">
                      Incidents within {correlation.correlation_window_minutes} min
                    </h4>
                    {correlation.correlated_incidents.length > 0 ? (
                      <div className="space-y-2">
                        {correlation.correlated_incidents.map((incident) => (
                          <div
                            key={incident.id}
                            className="bg-red-500/10 border border-red-500/30 rounded-lg p-2"
                          >
                            <div className="text-sm font-medium text-red-400">
                              {incident.title}
                            </div>
                            <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                              <span
                                className={`px-1.5 py-0.5 rounded ${
                                  incident.severity === 'critical'
                                    ? 'bg-red-500/30 text-red-300'
                                    : incident.severity === 'high'
                                    ? 'bg-orange-500/30 text-orange-300'
                                    : 'bg-yellow-500/30 text-yellow-300'
                                }`}
                              >
                                {incident.severity}
                              </span>
                              <span>{incident.status}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-sm text-muted-foreground bg-muted/30 rounded-lg p-3">
                        No incidents correlated with this deployment
                      </div>
                    )}
                  </div>

                  {/* Correlated Alerts */}
                  <div>
                    <h4 className="text-sm font-medium text-foreground mb-2">
                      Alerts within {correlation.correlation_window_minutes} min
                    </h4>
                    {correlation.correlated_alerts.length > 0 ? (
                      <div className="space-y-2">
                        {correlation.correlated_alerts.map((alert) => (
                          <div
                            key={alert.id}
                            className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-2"
                          >
                            <div className="text-sm font-medium text-yellow-400">
                              {alert.title}
                            </div>
                            <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                              <span
                                className={`px-1.5 py-0.5 rounded ${
                                  alert.severity === 'critical'
                                    ? 'bg-red-500/30 text-red-300'
                                    : alert.severity === 'high'
                                    ? 'bg-orange-500/30 text-orange-300'
                                    : 'bg-yellow-500/30 text-yellow-300'
                                }`}
                              >
                                {alert.severity}
                              </span>
                              <span>{alert.status}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-sm text-muted-foreground bg-muted/30 rounded-lg p-3">
                        No alerts correlated with this deployment
                      </div>
                    )}
                  </div>

                  {/* Close button */}
                  <button
                    onClick={() => setSelectedDeployment(null)}
                    className="w-full mt-4 px-4 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                  >
                    Close Details
                  </button>
                </div>
              ) : (
                <div className="text-center text-muted-foreground py-8">
                  Failed to load deployment details
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* CI/CD Integration Instructions */}
      {timeline && timeline.items.length === 0 && (
        <div className="bg-muted/50 border border-border rounded-xl p-6">
          <h3 className="text-lg font-semibold text-foreground mb-4">
            Integrate Your CI/CD
          </h3>
          <p className="text-muted-foreground mb-4">
            Track deployments and correlate them with incidents by adding a webhook
            to your CI/CD pipeline.
          </p>

          <div className="bg-muted rounded-lg p-4 font-mono text-sm">
            <div className="text-muted-foreground mb-2"># GitHub Actions Example</div>
            <pre className="text-green-400 overflow-x-auto">
{`- name: Notify OffCall AI
  run: |
    curl -X POST ${API_URL}/deployments/notify \\
      -H "Authorization: Bearer \${{ secrets.OFFCALL_API_KEY }}" \\
      -H "Content-Type: application/json" \\
      -d '{
        "service_name": "my-service",
        "version": "\${{ github.sha }}",
        "environment": "production",
        "commit_sha": "\${{ github.sha }}",
        "branch": "\${{ github.ref_name }}",
        "deployed_by": "\${{ github.actor }}"
      }'`}
            </pre>
          </div>
        </div>
      )}
      </div>
    </div>
  );
};

export default DeploymentTimeline;
