// Cost Attribution Dashboard - Analyze operational burden by service/team
import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  BarChart3,
  DollarSign,
  RefreshCw,
  Volume2,
  Zap
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { API_URL } from '../config/api';

// Types
interface AlertsByService {
  service_name: string;
  total_alerts: number;
  resolved: number;
  acknowledged: number;
  severity_breakdown: {
    critical: number;
    high: number;
    error: number;
    warning: number;
  };
}

interface AlertsByTeam {
  team: string;
  total_alerts: number;
  critical: number;
  high: number;
  error: number;
  warning: number;
  info: number;
}

interface OncallBurden {
  user_id: string;
  name: string;
  email: string;
  oncall_hours: number;
  incidents_handled: number;
  critical_incidents: number;
  avg_resolution_minutes: number | null;
  burden_score: number;
}

interface NoisyService {
  service: string;
  total_alerts: number;
  non_incident_alerts: number;
  noise_ratio: number;
}

interface NoiseAnalysis {
  total_alerts: number;
  alerts_became_incidents: number;
  noise_alerts: number;
  noise_ratio_percent: number;
  auto_resolved_count: number;
  auto_resolved_percent: number;
  flapping_alert_count: number;
  flapping_fingerprints: number;
  noisiest_services: NoisyService[];
  period_days: number;
  recommendation: string;
}

interface CostAttributionData {
  alerts_by_service: AlertsByService[];
  alerts_by_team: AlertsByTeam[];
  oncall_burden: OncallBurden[];
  noise_analysis: NoiseAnalysis;
  period_days: number;
  generated_at: string;
}

const CostAttributionDashboard: React.FC = () => {
  const { token } = useAuth();
  const [data, setData] = useState<CostAttributionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);
  const [activeTab, setActiveTab] = useState<'services' | 'teams' | 'burden' | 'noise'>('services');

  const fetchData = useCallback(async () => {
    if (!token) {
      setData(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${API_URL}/analytics/cost-attribution?days=${days}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        if (response.status === 403) {
          console.log('Cost Attribution requires premium subscription');
          setData(null);
          setError('Cost Attribution requires a premium subscription');
          return;
        }
        throw new Error(`Failed to fetch data: ${response.status}`);
      }

      const result: CostAttributionData = await response.json();
      setData(result);
    } catch (err) {
      console.error('Failed to fetch cost attribution data:', err);
      setData(null);
      setError(err instanceof Error ? err.message : 'Failed to fetch data');
    } finally {
      setLoading(false);
    }
  }, [token, days]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) {
    return (
      <div className="min-h-screen bg-background">
        {/* Header */}
        <div className="relative overflow-hidden border-b border-border">
          <div className="relative max-w-7xl mx-auto px-6 py-6">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className="p-3 rounded-xl bg-secondary">
                  <DollarSign className="w-8 h-8 text-foreground" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold text-foreground">Cost Attribution</h1>
                  <p className="text-muted-foreground text-sm">Analyze which services and teams generate the most operational burden</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
          <div className="flex items-center justify-center h-64">
            <RefreshCw className="h-8 w-8 animate-spin text-blue-500" />
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-background">
        {/* Header */}
        <div className="relative overflow-hidden border-b border-border">
          <div className="relative max-w-7xl mx-auto px-6 py-6">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className="p-3 rounded-xl bg-secondary">
                  <DollarSign className="w-8 h-8 text-foreground" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold text-foreground">Cost Attribution</h1>
                  <p className="text-muted-foreground text-sm">Analyze which services and teams generate the most operational burden</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
          <div className="bg-muted rounded-lg border border-border p-8">
            <div className="text-center text-red-400">
              <svg className="h-12 w-12 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <p>{error}</p>
              <button
                onClick={fetchData}
                className="mt-4 px-4 py-2 bg-blue-600 text-foreground rounded-lg hover:bg-blue-700 transition-colors"
              >
                Retry
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const tabs = [
    { id: 'services', label: 'By Service', icon: '🔧' },
    { id: 'teams', label: 'By Team', icon: '👥' },
    { id: 'burden', label: 'On-Call Burden', icon: '⏰' },
    { id: 'noise', label: 'Noise Analysis', icon: '📊' },
  ];

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="relative overflow-hidden border-b border-border">
        <div className="relative max-w-7xl mx-auto px-6 py-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-lime-500/10">
                <DollarSign className="w-6 h-6 text-lime-400" />
              </div>
              <div>
                <h1 className="text-base font-medium text-foreground">Cost Attribution</h1>
                <p className="text-muted-foreground text-sm">Analyze which services and teams generate the most operational burden</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <select
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                className="bg-muted text-foreground px-3 py-2 rounded-lg border border-border text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value={7}>Last 7 days</option>
                <option value={30}>Last 30 days</option>
                <option value={60}>Last 60 days</option>
                <option value={90}>Last 90 days</option>
              </select>

              <button
                onClick={fetchData}
                className="flex items-center gap-2 px-4 py-2 bg-muted hover:bg-muted/80 rounded-lg"
                title="Refresh"
              >
                <RefreshCw className="h-4 w-4" />
                Refresh
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-muted/50 border border-border rounded-xl">
          <div className="p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-muted-foreground">Total Alerts</span>
              <div className="p-2.5 rounded-xl bg-blue-500/10">
                <BarChart3 className="w-4 h-4 text-blue-400" />
              </div>
            </div>
            <div className="text-2xl font-bold text-foreground">
              {data.noise_analysis.total_alerts.toLocaleString()}
            </div>
          </div>
        </div>
        <div className="bg-muted/50 border border-border rounded-xl">
          <div className="p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-muted-foreground">Noise Ratio</span>
              <div className="p-2.5 rounded-xl bg-red-500/10">
                <Volume2 className="w-4 h-4 text-red-400" />
              </div>
            </div>
            <div className={`text-2xl font-bold ${
              data.noise_analysis.noise_ratio_percent > 50 ? 'text-red-400' :
              data.noise_analysis.noise_ratio_percent > 30 ? 'text-yellow-400' : 'text-green-400'
            }`}>
              {data.noise_analysis.noise_ratio_percent}%
            </div>
          </div>
        </div>
        <div className="bg-muted/50 border border-border rounded-xl">
          <div className="p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-muted-foreground">Flapping Alerts</span>
              <div className="p-2.5 rounded-xl bg-orange-500/10">
                <AlertTriangle className="w-4 h-4 text-orange-400" />
              </div>
            </div>
            <div className="text-2xl font-bold text-orange-400">
              {data.noise_analysis.flapping_alert_count}
            </div>
          </div>
        </div>
        <div className="bg-muted/50 border border-border rounded-xl">
          <div className="p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-muted-foreground">Auto-Resolved</span>
              <div className="p-2.5 rounded-xl bg-green-500/10">
                <Zap className="w-4 h-4 text-green-400" />
              </div>
            </div>
            <div className="text-2xl font-bold text-blue-400">
              {data.noise_analysis.auto_resolved_percent}%
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-muted rounded-xl overflow-hidden">
        <div className="flex border-b border-border">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'text-foreground bg-muted border-b-2 border-blue-500'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
              }`}
            >
              <span className="mr-2">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>

        <div className="p-4">
          {/* By Service Tab */}
          {activeTab === 'services' && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-foreground">Alerts by Service</h3>
              <p className="text-sm text-muted-foreground">Which services generate the most alerts?</p>

              {data.alerts_by_service.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="text-left text-sm text-muted-foreground border-b border-border">
                        <th className="pb-3 font-medium">Service</th>
                        <th className="pb-3 font-medium text-right">Total</th>
                        <th className="pb-3 font-medium text-right">Critical</th>
                        <th className="pb-3 font-medium text-right">High</th>
                        <th className="pb-3 font-medium text-right">Error</th>
                        <th className="pb-3 font-medium text-right">Warning</th>
                        <th className="pb-3 font-medium text-right">Resolved</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {data.alerts_by_service.map((service, idx) => (
                        <tr key={idx} className="text-sm">
                          <td className="py-3 text-foreground font-medium">{service.service_name}</td>
                          <td className="py-3 text-right text-foreground">{service.total_alerts}</td>
                          <td className="py-3 text-right text-red-400">{service.severity_breakdown.critical}</td>
                          <td className="py-3 text-right text-orange-400">{service.severity_breakdown.high}</td>
                          <td className="py-3 text-right text-yellow-400">{service.severity_breakdown.error}</td>
                          <td className="py-3 text-right text-muted-foreground">{service.severity_breakdown.warning}</td>
                          <td className="py-3 text-right text-green-400">{service.resolved}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center text-muted-foreground py-8">
                  No service data available for this period
                </div>
              )}
            </div>
          )}

          {/* By Team Tab */}
          {activeTab === 'teams' && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-foreground">Alerts by Team</h3>
              <p className="text-sm text-muted-foreground">Which teams handle the most alerts?</p>

              {data.alerts_by_team.length > 0 ? (
                <div className="grid gap-4">
                  {data.alerts_by_team.map((team, idx) => (
                    <div key={idx} className="bg-muted/50 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-3">
                        <div className="font-medium text-foreground">{team.team}</div>
                        <div className="text-lg font-bold text-foreground">{team.total_alerts} alerts</div>
                      </div>
                      <div className="flex gap-4 text-sm">
                        <div className="flex items-center gap-1">
                          <div className="w-2 h-2 rounded-full bg-red-500"></div>
                          <span className="text-muted-foreground">{team.critical} critical</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <div className="w-2 h-2 rounded-full bg-orange-500"></div>
                          <span className="text-muted-foreground">{team.high} high</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <div className="w-2 h-2 rounded-full bg-yellow-500"></div>
                          <span className="text-muted-foreground">{team.error} error</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <div className="w-2 h-2 rounded-full bg-muted"></div>
                          <span className="text-muted-foreground">{team.warning} warning</span>
                        </div>
                      </div>
                      {/* Bar visualization */}
                      <div className="mt-3 h-2 bg-muted rounded-full overflow-hidden flex">
                        <div className="bg-red-500" style={{ width: `${(team.critical / team.total_alerts) * 100}%` }}></div>
                        <div className="bg-orange-500" style={{ width: `${(team.high / team.total_alerts) * 100}%` }}></div>
                        <div className="bg-yellow-500" style={{ width: `${(team.error / team.total_alerts) * 100}%` }}></div>
                        <div className="bg-muted" style={{ width: `${(team.warning / team.total_alerts) * 100}%` }}></div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center text-muted-foreground py-8">
                  No team data available. Add team labels to alerts to track by team.
                </div>
              )}
            </div>
          )}

          {/* On-Call Burden Tab */}
          {activeTab === 'burden' && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-foreground">On-Call Burden</h3>
              <p className="text-sm text-muted-foreground">
                Weighted burden score based on on-call hours, incidents handled, and critical incidents (3x weight)
              </p>

              {data.oncall_burden.length > 0 ? (
                <div className="space-y-3">
                  {data.oncall_burden.map((user, idx) => {
                    const maxScore = data.oncall_burden[0]?.burden_score || 1;
                    const barWidth = (user.burden_score / maxScore) * 100;

                    return (
                      <div key={idx} className="bg-muted/50 rounded-lg p-4">
                        <div className="flex items-center justify-between mb-2">
                          <div>
                            <div className="font-medium text-foreground">{user.name}</div>
                            <div className="text-sm text-muted-foreground">{user.email}</div>
                          </div>
                          <div className="text-right">
                            <div className="text-lg font-bold text-blue-400">{user.burden_score}</div>
                            <div className="text-xs text-muted-foreground">burden score</div>
                          </div>
                        </div>

                        {/* Progress bar */}
                        <div className="h-2 bg-muted rounded-full overflow-hidden mb-3">
                          <div
                            className="h-full bg-blue-500 rounded-full"
                            style={{ width: `${barWidth}%` }}
                          ></div>
                        </div>

                        <div className="grid grid-cols-4 gap-4 text-sm">
                          <div>
                            <div className="text-muted-foreground">On-Call Hours</div>
                            <div className="text-foreground font-medium">{user.oncall_hours}h</div>
                          </div>
                          <div>
                            <div className="text-muted-foreground">Incidents</div>
                            <div className="text-foreground font-medium">{user.incidents_handled}</div>
                          </div>
                          <div>
                            <div className="text-muted-foreground">Critical</div>
                            <div className="text-red-400 font-medium">{user.critical_incidents}</div>
                          </div>
                          <div>
                            <div className="text-muted-foreground">Avg Resolution</div>
                            <div className="text-foreground font-medium">
                              {user.avg_resolution_minutes ? `${user.avg_resolution_minutes}m` : 'N/A'}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-center text-muted-foreground py-8">
                  No on-call burden data available
                </div>
              )}
            </div>
          )}

          {/* Noise Analysis Tab */}
          {activeTab === 'noise' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-semibold text-foreground">Noise Analysis</h3>
                <p className="text-sm text-muted-foreground">
                  Identify and reduce alert noise to improve signal quality
                </p>
              </div>

              {/* Recommendation */}
              {data.noise_analysis.recommendation && (
                <div className={`p-4 rounded-lg border ${
                  data.noise_analysis.noise_ratio_percent > 50
                    ? 'bg-red-500/10 border-red-500/30'
                    : data.noise_analysis.noise_ratio_percent > 30
                    ? 'bg-yellow-500/10 border-yellow-500/30'
                    : 'bg-green-500/10 border-green-500/30'
                }`}>
                  <div className="flex items-start gap-3">
                    <svg className="h-5 w-5 text-yellow-400 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                    <div>
                      <div className="font-medium text-foreground">Recommendation</div>
                      <div className="text-sm text-foreground mt-1">{data.noise_analysis.recommendation}</div>
                    </div>
                  </div>
                </div>
              )}

              {/* Metrics Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-muted/50 rounded-lg p-4">
                  <div className="text-sm text-muted-foreground">Total Alerts</div>
                  <div className="text-xl font-bold text-foreground">{data.noise_analysis.total_alerts}</div>
                </div>
                <div className="bg-muted/50 rounded-lg p-4">
                  <div className="text-sm text-muted-foreground">Became Incidents</div>
                  <div className="text-xl font-bold text-green-400">{data.noise_analysis.alerts_became_incidents}</div>
                </div>
                <div className="bg-muted/50 rounded-lg p-4">
                  <div className="text-sm text-muted-foreground">Noise Alerts</div>
                  <div className="text-xl font-bold text-red-400">{data.noise_analysis.noise_alerts}</div>
                </div>
                <div className="bg-muted/50 rounded-lg p-4">
                  <div className="text-sm text-muted-foreground">Flapping</div>
                  <div className="text-xl font-bold text-orange-400">{data.noise_analysis.flapping_fingerprints} patterns</div>
                </div>
              </div>

              {/* Noisiest Services */}
              <div>
                <h4 className="text-md font-medium text-foreground mb-3">Noisiest Services</h4>
                {data.noise_analysis.noisiest_services.length > 0 ? (
                  <div className="space-y-2">
                    {data.noise_analysis.noisiest_services.map((service, idx) => (
                      <div key={idx} className="flex items-center justify-between bg-muted/50 rounded-lg p-3">
                        <div className="text-foreground">{service.service}</div>
                        <div className="flex items-center gap-4 text-sm">
                          <span className="text-muted-foreground">{service.total_alerts} total</span>
                          <span className="text-red-400">{service.non_incident_alerts} noise</span>
                          <span className={`px-2 py-0.5 rounded ${
                            service.noise_ratio > 50 ? 'bg-red-500/20 text-red-400' :
                            service.noise_ratio > 30 ? 'bg-yellow-500/20 text-yellow-400' :
                            'bg-green-500/20 text-green-400'
                          }`}>
                            {service.noise_ratio}%
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center text-muted-foreground py-4">
                    No noisy services detected
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
      </div>
    </div>
  );
};

export default CostAttributionDashboard;
