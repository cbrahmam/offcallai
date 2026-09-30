// frontend/oncall-frontend/src/components/AnomalyDetection.tsx
import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Brain,
  CheckCircle,
  Clock,
  Eye,
  Filter,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Settings,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  TrendingDown,
  TrendingUp,
  X,
  XCircle
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine
} from 'recharts';

import { API_URL as API_BASE_URL } from '../config/api';

interface Detector {
  id: string;
  name: string;
  description?: string;
  metric_name: string;
  algorithm: string;
  sensitivity: number;
  window_size: number;
  detect_spikes: boolean;
  detect_drops: boolean;
  detect_trends: boolean;
  alert_on_anomaly: boolean;
  enabled: boolean;
  last_run?: string;
  last_anomaly?: string;
  baseline_mean?: number;
  baseline_std?: number;
  created_at: string;
}

interface Anomaly {
  id: string;
  detector_id: string;
  anomaly_type: string;
  severity: string;
  status: string;
  metric_name: string;
  host_id?: string;
  service_name?: string;
  detected_at: string;
  resolved_at?: string;
  duration_minutes?: number;
  anomaly_value: number;
  expected_value?: number;
  expected_min?: number;
  expected_max?: number;
  deviation_score?: number;
  ai_description?: string;
  ai_possible_causes: string[];
  ai_recommended_actions: string[];
}

interface AnomalySummary {
  total_active: number;
  total_acknowledged: number;
  total_resolved: number;
  by_severity: Record<string, number>;
  by_type: Record<string, number>;
  recent_24h: number;
  recent_7d: number;
}

const ALGORITHMS = [
  { id: 'zscore', label: 'Z-Score', description: 'Standard deviation based detection' },
  { id: 'iqr', label: 'IQR', description: 'Interquartile range based detection' },
  { id: 'moving_average', label: 'Moving Average', description: 'Moving average deviation' },
];

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-yellow-500',
  low: 'bg-blue-500',
};

const TYPE_ICONS: Record<string, React.ReactNode> = {
  spike: <TrendingUp className="h-4 w-4 text-red-400" />,
  drop: <TrendingDown className="h-4 w-4 text-blue-400" />,
  trend: <Activity className="h-4 w-4 text-yellow-400" />,
  outlier: <AlertTriangle className="h-4 w-4 text-orange-400" />,
};

type TabType = 'anomalies' | 'detectors';

interface AnomalyDetectionProps {
  isDemoMode?: boolean;
}

export default function AnomalyDetection({ isDemoMode = false }: AnomalyDetectionProps) {
  const [activeTab, setActiveTab] = useState<TabType>('anomalies');
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [detectors, setDetectors] = useState<Detector[]>([]);
  const [summary, setSummary] = useState<AnomalySummary | null>(null);
  const [selectedAnomaly, setSelectedAnomaly] = useState<Anomaly | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [severityFilter, setSeverityFilter] = useState<string>('');

  // New detector form
  const [newDetector, setNewDetector] = useState({
    name: '',
    description: '',
    metric_name: 'cpu.usage',
    algorithm: 'zscore',
    sensitivity: 2.0,
    window_size: 60,
    min_data_points: 30,
    detect_spikes: true,
    detect_drops: true,
    detect_trends: true,
    alert_on_anomaly: true,
    enabled: true
  });

  const getAuthHeaders = useCallback(() => {
    const token = localStorage.getItem('access_token');
    return {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  }, []);

  const fetchAnomalies = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (statusFilter) params.append('status', statusFilter);
      if (severityFilter) params.append('severity', severityFilter);

      const response = await fetch(`${API_BASE_URL}/anomalies/?${params}`, {
        headers: getAuthHeaders(),
      });

      if (!response.ok) throw new Error('Failed to fetch anomalies');

      const data = await response.json();
      const anomaliesData = data.anomalies || [];
      setAnomalies(anomaliesData);
    } catch (err) {
      console.error('Failed to fetch anomalies:', err);
      setAnomalies([]);
      setError(err instanceof Error ? err.message : 'Failed to fetch anomalies');
    } finally {
      setLoading(false);
    }
  }, [getAuthHeaders, statusFilter, severityFilter]);

  const fetchDetectors = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/anomalies/detectors`, {
        headers: getAuthHeaders(),
      });

      if (!response.ok) throw new Error('Failed to fetch detectors');

      const data = await response.json();
      const detectorsData = data.detectors || [];
      setDetectors(detectorsData);
    } catch (err) {
      console.error('Failed to fetch detectors:', err);
      setDetectors([]);
    }
  }, [getAuthHeaders]);

  const fetchSummary = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/anomalies/summary`, {
        headers: getAuthHeaders(),
      });

      if (!response.ok) throw new Error('Failed to fetch summary');

      const data = await response.json();
      setSummary(data);
    } catch (err) {
      console.error('Failed to fetch summary:', err);
      setSummary(null);
    }
  }, [getAuthHeaders]);

  const createDetector = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/anomalies/detectors`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(newDetector),
      });

      if (!response.ok) throw new Error('Failed to create detector');

      setShowCreateModal(false);
      setNewDetector({
        name: '',
        description: '',
        metric_name: 'cpu.usage',
        algorithm: 'zscore',
        sensitivity: 2.0,
        window_size: 60,
        min_data_points: 30,
        detect_spikes: true,
        detect_drops: true,
        detect_trends: true,
        alert_on_anomaly: true,
        enabled: true
      });
      fetchDetectors();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create detector');
    }
  };

  const toggleDetector = async (detectorId: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/anomalies/detectors/${detectorId}/toggle`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });

      if (!response.ok) throw new Error('Failed to toggle detector');

      fetchDetectors();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to toggle detector');
    }
  };

  const runDetector = async (detectorId: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/anomalies/detectors/${detectorId}/run`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });

      if (!response.ok) throw new Error('Failed to run detector');

      const data = await response.json();
      alert(`Detection complete: ${data.anomalies_found} anomalies found in ${data.data_points_analyzed} data points`);
      fetchAnomalies();
      fetchSummary();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run detector');
    }
  };

  const deleteDetector = async (detectorId: string) => {
    if (!window.confirm('Are you sure you want to delete this detector?')) return;

    try {
      const response = await fetch(`${API_BASE_URL}/anomalies/detectors/${detectorId}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });

      if (!response.ok) throw new Error('Failed to delete detector');

      fetchDetectors();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete detector');
    }
  };

  const acknowledgeAnomaly = async (anomalyId: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/anomalies/${anomalyId}/acknowledge`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({}),
      });

      if (!response.ok) throw new Error('Failed to acknowledge anomaly');

      fetchAnomalies();
      fetchSummary();
      setSelectedAnomaly(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to acknowledge anomaly');
    }
  };

  const resolveAnomaly = async (anomalyId: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/anomalies/${anomalyId}/resolve`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });

      if (!response.ok) throw new Error('Failed to resolve anomaly');

      fetchAnomalies();
      fetchSummary();
      setSelectedAnomaly(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resolve anomaly');
    }
  };

  useEffect(() => {
    fetchAnomalies();
    fetchDetectors();
    fetchSummary();
  }, [fetchAnomalies, fetchDetectors, fetchSummary]);

  const renderSummaryCards = () => (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div className="bg-muted/50 rounded-lg border border-border">
        <div className="p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-muted-foreground">Active</span>
            <div className="p-2.5 rounded-xl bg-red-500/10">
              <AlertTriangle className="w-4 h-4 text-red-400" />
            </div>
          </div>
          <p className="text-2xl font-bold text-foreground">{summary?.total_active || 0}</p>
        </div>
      </div>
      <div className="bg-muted/50 rounded-lg border border-border">
        <div className="p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-muted-foreground">Acknowledged</span>
            <div className="p-2.5 rounded-xl bg-yellow-500/10">
              <Eye className="w-4 h-4 text-yellow-400" />
            </div>
          </div>
          <p className="text-2xl font-bold text-foreground">{summary?.total_acknowledged || 0}</p>
        </div>
      </div>
      <div className="bg-muted/50 rounded-lg border border-border">
        <div className="p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-muted-foreground">Last 24h</span>
            <div className="p-2.5 rounded-xl bg-blue-500/10">
              <Clock className="w-4 h-4 text-blue-400" />
            </div>
          </div>
          <p className="text-2xl font-bold text-foreground">{summary?.recent_24h || 0}</p>
        </div>
      </div>
      <div className="bg-muted/50 rounded-lg border border-border">
        <div className="p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-muted-foreground">Resolved</span>
            <div className="p-2.5 rounded-xl bg-green-500/10">
              <CheckCircle className="w-4 h-4 text-green-400" />
            </div>
          </div>
          <p className="text-2xl font-bold text-foreground">{summary?.total_resolved || 0}</p>
        </div>
      </div>
    </div>
  );

  const renderAnomaliesList = () => (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex items-center gap-3">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-4 py-2 bg-muted border border-border rounded-lg text-sm text-foreground"
        >
          <option value="">All Status</option>
          <option value="active">Active</option>
          <option value="acknowledged">Acknowledged</option>
          <option value="resolved">Resolved</option>
        </select>
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="px-4 py-2 bg-muted border border-border rounded-lg text-sm text-foreground"
        >
          <option value="">All Severity</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <button
          onClick={fetchAnomalies}
          className="p-2 bg-muted hover:bg-muted/80 rounded-lg"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {/* Anomalies list */}
      <div className="space-y-2">
        {anomalies.map((anomaly) => (
          <div
            key={anomaly.id}
            onClick={() => setSelectedAnomaly(anomaly)}
            className="p-4 bg-muted/50 rounded-lg border border-border hover:border-blue-500 cursor-pointer transition-colors"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-3">
                {TYPE_ICONS[anomaly.anomaly_type] || <Activity className="h-4 w-4" />}
                <span className="font-medium text-foreground">{anomaly.metric_name}</span>
                <span className={`px-2 py-0.5 rounded text-xs text-foreground ${SEVERITY_COLORS[anomaly.severity]}`}>
                  {anomaly.severity}
                </span>
                <span className={`px-2 py-0.5 rounded text-xs ${
                  anomaly.status === 'active' ? 'bg-red-500/20 text-red-400' :
                  anomaly.status === 'acknowledged' ? 'bg-yellow-500/20 text-yellow-400' :
                  'bg-green-500/20 text-green-400'
                }`}>
                  {anomaly.status}
                </span>
              </div>
              <span className="text-xs text-muted-foreground">
                {new Date(anomaly.detected_at).toLocaleString()}
              </span>
            </div>
            <div className="flex items-center gap-6 text-sm text-muted-foreground">
              <span>Value: <span className="text-foreground font-mono">{anomaly.anomaly_value.toFixed(2)}</span></span>
              {anomaly.expected_value && (
                <span>Expected: <span className="text-foreground font-mono">{anomaly.expected_value.toFixed(2)}</span></span>
              )}
              {anomaly.deviation_score && (
                <span>Deviation: <span className="text-foreground font-mono">{anomaly.deviation_score.toFixed(2)}σ</span></span>
              )}
            </div>
          </div>
        ))}

        {anomalies.length === 0 && !loading && (
          <div className="py-12 text-center text-muted-foreground">
            <Brain className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>No anomalies detected</p>
            <p className="text-sm mt-1">Create detectors and run them to find anomalies</p>
          </div>
        )}
      </div>
    </div>
  );

  const renderDetectorsList = () => (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold text-foreground">Anomaly Detectors</h3>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm text-foreground"
        >
          <Plus className="h-4 w-4" />
          New Detector
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {detectors.map((detector) => (
          <div
            key={detector.id}
            className="p-4 bg-muted/50 rounded-lg border border-border"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Brain className={`h-5 w-5 ${detector.enabled ? 'text-green-400' : 'text-muted-foreground'}`} />
                <h4 className="font-medium text-foreground">{detector.name}</h4>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => runDetector(detector.id)}
                  className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded"
                  title="Run Detection"
                >
                  <Play className="h-4 w-4" />
                </button>
                <button
                  onClick={() => toggleDetector(detector.id)}
                  className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded"
                  title={detector.enabled ? 'Disable' : 'Enable'}
                >
                  {detector.enabled ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                </button>
                <button
                  onClick={() => deleteDetector(detector.id)}
                  className="p-1.5 text-muted-foreground hover:text-red-400 hover:bg-muted rounded"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>

            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Metric</span>
                <span className="text-foreground font-mono">{detector.metric_name}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Algorithm</span>
                <span className="text-foreground">{ALGORITHMS.find(a => a.id === detector.algorithm)?.label || detector.algorithm}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Sensitivity</span>
                <span className="text-foreground">{detector.sensitivity}σ</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Window</span>
                <span className="text-foreground">{detector.window_size} min</span>
              </div>
              {detector.baseline_mean !== undefined && (
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Baseline</span>
                  <span className="text-foreground font-mono">
                    {detector.baseline_mean?.toFixed(2)} ± {detector.baseline_std?.toFixed(2)}
                  </span>
                </div>
              )}
              {detector.last_run && (
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>Last run</span>
                  <span>{new Date(detector.last_run).toLocaleString()}</span>
                </div>
              )}
            </div>

            <div className="flex items-center gap-2 mt-3">
              {detector.detect_spikes && (
                <span className="px-2 py-0.5 bg-red-500/20 text-red-400 rounded text-xs">Spikes</span>
              )}
              {detector.detect_drops && (
                <span className="px-2 py-0.5 bg-blue-500/20 text-blue-400 rounded text-xs">Drops</span>
              )}
              {detector.detect_trends && (
                <span className="px-2 py-0.5 bg-yellow-500/20 text-yellow-400 rounded text-xs">Trends</span>
              )}
            </div>
          </div>
        ))}

        {detectors.length === 0 && (
          <div className="col-span-full py-12 text-center text-muted-foreground">
            <Brain className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>No detectors configured</p>
            <p className="text-sm mt-1">Create your first anomaly detector to start detecting anomalies</p>
          </div>
        )}
      </div>
    </div>
  );

  const renderAnomalyDetail = () => {
    if (!selectedAnomaly) return null;

    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
        <div className="w-full max-w-2xl bg-muted rounded-lg border border-border max-h-[90vh] overflow-y-auto">
          <div className="flex items-center justify-between px-6 py-4 border-b border-border sticky top-0 bg-muted">
            <div className="flex items-center gap-3">
              {TYPE_ICONS[selectedAnomaly.anomaly_type]}
              <h3 className="text-lg font-semibold text-foreground">Anomaly Details</h3>
            </div>
            <button onClick={() => setSelectedAnomaly(null)} className="text-muted-foreground hover:text-foreground">
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="p-6 space-y-6">
            {/* Header info */}
            <div className="flex items-center gap-3">
              <span className={`px-3 py-1 rounded text-sm text-foreground ${SEVERITY_COLORS[selectedAnomaly.severity]}`}>
                {selectedAnomaly.severity.toUpperCase()}
              </span>
              <span className={`px-3 py-1 rounded text-sm ${
                selectedAnomaly.status === 'active' ? 'bg-red-500/20 text-red-400' :
                selectedAnomaly.status === 'acknowledged' ? 'bg-yellow-500/20 text-yellow-400' :
                'bg-green-500/20 text-green-400'
              }`}>
                {selectedAnomaly.status.toUpperCase()}
              </span>
              <span className="text-sm text-muted-foreground capitalize">{selectedAnomaly.anomaly_type}</span>
            </div>

            {/* Metric details */}
            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 bg-muted/50 rounded-lg">
                <p className="text-sm text-muted-foreground mb-1">Metric</p>
                <p className="text-foreground font-mono">{selectedAnomaly.metric_name}</p>
              </div>
              <div className="p-4 bg-muted/50 rounded-lg">
                <p className="text-sm text-muted-foreground mb-1">Detected At</p>
                <p className="text-foreground">{new Date(selectedAnomaly.detected_at).toLocaleString()}</p>
              </div>
              <div className="p-4 bg-muted/50 rounded-lg">
                <p className="text-sm text-muted-foreground mb-1">Anomaly Value</p>
                <p className="text-2xl font-bold text-red-400">{selectedAnomaly.anomaly_value.toFixed(2)}</p>
              </div>
              <div className="p-4 bg-muted/50 rounded-lg">
                <p className="text-sm text-muted-foreground mb-1">Expected Range</p>
                <p className="text-foreground font-mono">
                  {selectedAnomaly.expected_min?.toFixed(2)} - {selectedAnomaly.expected_max?.toFixed(2)}
                </p>
              </div>
            </div>

            {selectedAnomaly.deviation_score && (
              <div className="p-4 bg-muted/50 rounded-lg">
                <p className="text-sm text-muted-foreground mb-1">Deviation Score</p>
                <p className="text-foreground">
                  <span className="text-2xl font-bold">{selectedAnomaly.deviation_score.toFixed(2)}</span>
                  <span className="text-muted-foreground ml-1">standard deviations from normal</span>
                </p>
              </div>
            )}

            {/* AI Analysis */}
            {selectedAnomaly.ai_description && (
              <div className="p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <Brain className="h-5 w-5 text-blue-400" />
                  <h4 className="font-medium text-blue-400">AI Analysis</h4>
                </div>
                <p className="text-foreground">{selectedAnomaly.ai_description}</p>
              </div>
            )}

            {selectedAnomaly.ai_possible_causes.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-2">Possible Causes</h4>
                <ul className="space-y-1">
                  {selectedAnomaly.ai_possible_causes.map((cause, i) => (
                    <li key={i} className="flex items-start gap-2 text-foreground">
                      <span className="text-muted-foreground">•</span>
                      {cause}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {selectedAnomaly.ai_recommended_actions.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-2">Recommended Actions</h4>
                <ul className="space-y-1">
                  {selectedAnomaly.ai_recommended_actions.map((action, i) => (
                    <li key={i} className="flex items-start gap-2 text-foreground">
                      <span className="text-blue-400">→</span>
                      {action}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <div className="flex justify-end gap-3 px-6 py-4 border-t border-border sticky bottom-0 bg-muted">
            {selectedAnomaly.status === 'active' && (
              <>
                <button
                  onClick={() => acknowledgeAnomaly(selectedAnomaly.id)}
                  className="px-4 py-2 bg-yellow-600 hover:bg-yellow-700 rounded-lg text-foreground"
                >
                  Acknowledge
                </button>
                <button
                  onClick={() => resolveAnomaly(selectedAnomaly.id)}
                  className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-foreground"
                >
                  Resolve
                </button>
              </>
            )}
            {selectedAnomaly.status === 'acknowledged' && (
              <button
                onClick={() => resolveAnomaly(selectedAnomaly.id)}
                className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-foreground"
              >
                Resolve
              </button>
            )}
            <button
              onClick={() => setSelectedAnomaly(null)}
              className="px-4 py-2 text-muted-foreground hover:text-foreground"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    );
  };

  const renderCreateModal = () => (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-lg bg-muted rounded-lg border border-border">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h3 className="text-lg font-semibold text-foreground">Create Anomaly Detector</h3>
          <button onClick={() => setShowCreateModal(false)} className="text-muted-foreground hover:text-foreground">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">Name</label>
            <input
              type="text"
              value={newDetector.name}
              onChange={(e) => setNewDetector({ ...newDetector, name: e.target.value })}
              className="w-full px-4 py-2 bg-muted border border-border rounded-lg text-foreground"
              placeholder="CPU Spike Detector"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">Metric Name</label>
            <input
              type="text"
              value={newDetector.metric_name}
              onChange={(e) => setNewDetector({ ...newDetector, metric_name: e.target.value })}
              className="w-full px-4 py-2 bg-muted border border-border rounded-lg text-foreground"
              placeholder="cpu.usage"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">Algorithm</label>
            <select
              value={newDetector.algorithm}
              onChange={(e) => setNewDetector({ ...newDetector, algorithm: e.target.value })}
              className="w-full px-4 py-2 bg-muted border border-border rounded-lg text-foreground"
            >
              {ALGORITHMS.map((algo) => (
                <option key={algo.id} value={algo.id}>{algo.label}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Sensitivity (σ)</label>
              <input
                type="number"
                step="0.1"
                min="0.5"
                max="5"
                value={newDetector.sensitivity}
                onChange={(e) => setNewDetector({ ...newDetector, sensitivity: parseFloat(e.target.value) })}
                className="w-full px-4 py-2 bg-muted border border-border rounded-lg text-foreground"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Window (min)</label>
              <input
                type="number"
                min="5"
                max="1440"
                value={newDetector.window_size}
                onChange={(e) => setNewDetector({ ...newDetector, window_size: parseInt(e.target.value) })}
                className="w-full px-4 py-2 bg-muted border border-border rounded-lg text-foreground"
              />
            </div>
          </div>
          <div className="space-y-2">
            <label className="block text-sm font-medium text-foreground">Detection Types</label>
            <div className="flex flex-wrap items-center gap-4">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={newDetector.detect_spikes}
                  onChange={(e) => setNewDetector({ ...newDetector, detect_spikes: e.target.checked })}
                />
                <span className="text-sm text-foreground">Spikes</span>
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={newDetector.detect_drops}
                  onChange={(e) => setNewDetector({ ...newDetector, detect_drops: e.target.checked })}
                />
                <span className="text-sm text-foreground">Drops</span>
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={newDetector.detect_trends}
                  onChange={(e) => setNewDetector({ ...newDetector, detect_trends: e.target.checked })}
                />
                <span className="text-sm text-foreground">Trends</span>
              </label>
            </div>
          </div>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={newDetector.alert_on_anomaly}
              onChange={(e) => setNewDetector({ ...newDetector, alert_on_anomaly: e.target.checked })}
            />
            <span className="text-sm text-foreground">Alert on anomaly detection</span>
          </label>
        </div>
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-border">
          <button
            onClick={() => setShowCreateModal(false)}
            className="px-4 py-2 text-muted-foreground hover:text-foreground"
          >
            Cancel
          </button>
          <button
            onClick={createDetector}
            disabled={!newDetector.name || !newDetector.metric_name}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg text-foreground"
          >
            Create Detector
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-background">
      {/* Colorful Header */}
      <div className="relative overflow-hidden border-b border-border">

        <div className="relative max-w-7xl mx-auto px-6 py-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-violet-500/10">
                <Brain className="w-6 h-6 text-violet-400" />
              </div>
              <div>
                <h1 className="text-base font-medium text-foreground">Anomaly Detection</h1>
                <p className="text-muted-foreground text-sm">AI-powered detection of unusual patterns in your metrics</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
      {/* Summary cards */}
      {renderSummaryCards()}

      {/* Tabs */}
      <div className="flex items-center border-b border-border mb-6">
        <button
          onClick={() => setActiveTab('anomalies')}
          className={`flex items-center gap-2 px-4 py-2 font-medium text-sm border-b-2 transition-colors ${
            activeTab === 'anomalies'
              ? 'border-blue-500 text-blue-400'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <AlertTriangle className="h-4 w-4" />
          Anomalies
        </button>
        <button
          onClick={() => setActiveTab('detectors')}
          className={`flex items-center gap-2 px-4 py-2 font-medium text-sm border-b-2 transition-colors ${
            activeTab === 'detectors'
              ? 'border-blue-500 text-blue-400'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <Brain className="h-4 w-4" />
          Detectors
        </button>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <RefreshCw className="h-8 w-8 animate-spin text-blue-500" />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="p-4 bg-red-500/20 border border-red-500/30 rounded-lg text-red-400 mb-4">
          {error}
        </div>
      )}

      {/* Content */}
      {!loading && !error && (
        <>
          {activeTab === 'anomalies' && renderAnomaliesList()}
          {activeTab === 'detectors' && renderDetectorsList()}
        </>
      )}

      </div>

      {/* Modals */}
      {selectedAnomaly && renderAnomalyDetail()}
      {showCreateModal && renderCreateModal()}
    </div>
  );
}
