// frontend/oncall-frontend/src/components/AlertRulesManager.tsx
import React, { useState, useEffect } from 'react';
import {
  Bell,
  Plus,
  Edit2,
  Trash2,
  Play,
  Pause,
  AlertTriangle,
  Activity,
  Clock,
  Cpu,
  HardDrive,
  Wifi,
  Server,
  Check,
  X,
  TestTube,
  RefreshCw
} from 'lucide-react';
import { Button } from './ui/button';

import { API_URL as API_BASE } from '../config/api';

interface AlertRule {
  id: string;
  name: string;
  description?: string;
  metric_name: string;
  operator: string;
  threshold: number;
  condition_text: string;
  aggregation: string;
  evaluation_window: number;
  duration: number;
  host_ids: string[];
  host_tags: Record<string, string>;
  severity: string;
  auto_create_incident: boolean;
  auto_resolve: boolean;
  cooldown_seconds: number;
  notify_channels: string[];
  notify_users: string[];
  status: string;
  current_value?: number;
  last_evaluated_at?: string;
  last_triggered_at?: string;
  labels: Record<string, string>;
  created_at: string;
}

interface AlertRuleSummary {
  total: number;
  enabled: number;
  disabled: number;
  firing: number;
  pending: number;
  by_severity: Record<string, number>;
}

interface AlertRuleTestResult {
  would_trigger: boolean;
  current_value?: number;
  threshold: number;
  operator: string;
  hosts_checked: number;
  hosts_triggering: number;
  details: Array<{
    host_id: string;
    hostname: string;
    value?: number;
    would_trigger: boolean;
  }>;
}

const METRIC_OPTIONS = [
  { value: 'system.cpu.usage', label: 'CPU Usage (%)', icon: Cpu },
  { value: 'system.memory.usage_percent', label: 'Memory Usage (%)', icon: Server },
  { value: 'system.disk.usage_percent', label: 'Disk Usage (%)', icon: HardDrive },
  { value: 'system.load.1', label: 'Load Average (1m)', icon: Activity },
  { value: 'system.load.5', label: 'Load Average (5m)', icon: Activity },
  { value: 'system.network.bytes_in', label: 'Network In (bytes)', icon: Wifi },
  { value: 'system.network.bytes_out', label: 'Network Out (bytes)', icon: Wifi },
];

const OPERATOR_OPTIONS = [
  { value: 'gt', label: '> (greater than)' },
  { value: 'gte', label: '>= (greater or equal)' },
  { value: 'lt', label: '< (less than)' },
  { value: 'lte', label: '<= (less or equal)' },
  { value: 'eq', label: '== (equals)' },
  { value: 'neq', label: '!= (not equals)' },
];

const SEVERITY_OPTIONS = [
  { value: 'info', label: 'Info' },
  { value: 'warning', label: 'Warning' },
  { value: 'error', label: 'Error' },
  { value: 'critical', label: 'Critical' },
];

const AGGREGATION_OPTIONS = [
  { value: 'avg', label: 'Average' },
  { value: 'max', label: 'Maximum' },
  { value: 'min', label: 'Minimum' },
  { value: 'sum', label: 'Sum' },
  { value: 'last', label: 'Last Value' },
];

interface AlertRulesManagerProps {
  isDemoMode?: boolean;
}

export default function AlertRulesManager({ isDemoMode = false }: AlertRulesManagerProps) {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [summary, setSummary] = useState<AlertRuleSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingRule, setEditingRule] = useState<AlertRule | null>(null);
  const [testResult, setTestResult] = useState<AlertRuleTestResult | null>(null);
  const [testingRule, setTestingRule] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    metric_name: 'system.cpu.usage',
    operator: 'gt',
    threshold: 90,
    aggregation: 'avg',
    evaluation_window: 300,
    duration: 0,
    severity: 'warning',
    auto_create_incident: true,
    auto_resolve: true,
    cooldown_seconds: 300,
    notify_channels: ['slack'],
  });

  useEffect(() => {
    fetchRules();
    fetchSummary();
  }, []);

  const fetchRules = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE}/alert-rules/`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!response.ok) throw new Error('Failed to fetch alert rules');
      const data = await response.json();
      setRules(data.rules || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load alert rules');
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  };

  const fetchSummary = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE}/alert-rules/summary`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!response.ok) throw new Error('Failed to fetch summary');
      const data = await response.json();
      setSummary(data);
    } catch (err) {
      console.error('Failed to fetch summary:', err);
    }
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await fetchRules();
    await fetchSummary();
  };

  const createRule = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE}/alert-rules/`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
      });
      if (!response.ok) throw new Error('Failed to create alert rule');
      setShowCreateModal(false);
      resetForm();
      fetchRules();
      fetchSummary();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create rule');
    }
  };

  const updateRule = async () => {
    if (!editingRule) return;
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE}/alert-rules/${editingRule.id}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
      });
      if (!response.ok) throw new Error('Failed to update alert rule');
      setEditingRule(null);
      resetForm();
      fetchRules();
      fetchSummary();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update rule');
    }
  };

  const deleteRule = async (ruleId: string) => {
    if (!window.confirm('Are you sure you want to delete this alert rule?')) return;
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE}/alert-rules/${ruleId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!response.ok) throw new Error('Failed to delete alert rule');
      fetchRules();
      fetchSummary();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete rule');
    }
  };

  const toggleRule = async (ruleId: string, enabled: boolean) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE}/alert-rules/${ruleId}/toggle`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ enabled })
      });
      if (!response.ok) throw new Error('Failed to toggle alert rule');
      fetchRules();
      fetchSummary();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to toggle rule');
    }
  };

  const testRule = async () => {
    setTestingRule(true);
    setTestResult(null);
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE}/alert-rules/test`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          metric_name: formData.metric_name,
          operator: formData.operator,
          threshold: formData.threshold,
          aggregation: formData.aggregation,
          evaluation_window: formData.evaluation_window
        })
      });
      if (!response.ok) throw new Error('Failed to test alert rule');
      const data = await response.json();
      setTestResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to test rule');
    } finally {
      setTestingRule(false);
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      metric_name: 'system.cpu.usage',
      operator: 'gt',
      threshold: 90,
      aggregation: 'avg',
      evaluation_window: 300,
      duration: 0,
      severity: 'warning',
      auto_create_incident: true,
      auto_resolve: true,
      cooldown_seconds: 300,
      notify_channels: ['slack'],
    });
    setTestResult(null);
  };

  const openEditModal = (rule: AlertRule) => {
    setEditingRule(rule);
    setFormData({
      name: rule.name,
      description: rule.description || '',
      metric_name: rule.metric_name,
      operator: rule.operator,
      threshold: rule.threshold,
      aggregation: rule.aggregation,
      evaluation_window: rule.evaluation_window,
      duration: rule.duration,
      severity: rule.severity,
      auto_create_incident: rule.auto_create_incident,
      auto_resolve: rule.auto_resolve,
      cooldown_seconds: rule.cooldown_seconds,
      notify_channels: rule.notify_channels,
    });
  };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      enabled: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
      disabled: 'bg-secondary text-muted-foreground border-border',
      firing: 'bg-red-500/10 text-red-400 border-red-500/20 animate-pulse',
      pending: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    };
    return styles[status] || 'bg-secondary text-muted-foreground border-border';
  };

  const getSeverityBadge = (severity: string) => {
    const styles: Record<string, string> = {
      info: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
      warning: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
      error: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
      critical: 'bg-red-500/10 text-red-400 border-red-500/20',
    };
    return styles[severity] || 'bg-secondary text-muted-foreground border-border';
  };

  const formatDuration = (seconds: number) => {
    if (seconds === 0) return 'Immediate';
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
    return `${Math.floor(seconds / 3600)}h`;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background">
        <div className="border-b border-border">
          <div className="max-w-7xl mx-auto px-6 py-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-yellow-500/10">
                <Bell className="w-6 h-6 text-yellow-400" />
              </div>
              <div>
                <h1 className="text-xl font-semibold text-foreground">Alert Rules</h1>
                <p className="text-muted-foreground text-sm">Create metric-based alerts to automatically detect issues and create incidents</p>
              </div>
            </div>
          </div>
        </div>
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
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
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-yellow-500/10">
                <Bell className="w-6 h-6 text-yellow-400" />
              </div>
              <div>
                <h1 className="text-xl font-semibold text-foreground">Alert Rules</h1>
                <p className="text-muted-foreground text-sm">Create metric-based alerts to automatically detect issues and create incidents</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                onClick={handleRefresh}
                disabled={isRefreshing}
                className="border-border text-foreground hover:bg-accent"
              >
                <RefreshCw className={`w-4 h-4 mr-2 ${isRefreshing ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
              <Button
                onClick={() => { resetForm(); setShowCreateModal(true); }}
                className="bg-primary text-primary-foreground hover:bg-white/90"
              >
                <Plus className="w-4 h-4 mr-2" />
                Create Rule
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {error && (
          <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm flex items-center justify-between">
            {error}
            <button onClick={() => setError(null)} className="hover:text-red-300">
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* Summary Cards */}
        {summary && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="bg-transparent rounded-xl p-4 border border-border">
              <div className="text-2xl font-bold text-foreground">{summary.total}</div>
              <div className="text-muted-foreground text-sm">Total Rules</div>
            </div>
            <div className="bg-transparent rounded-xl p-4 border border-border">
              <div className="text-2xl font-bold text-emerald-400">{summary.enabled}</div>
              <div className="text-muted-foreground text-sm">Enabled</div>
            </div>
            <div className="bg-transparent rounded-xl p-4 border border-border">
              <div className="text-2xl font-bold text-red-400">{summary.firing}</div>
              <div className="text-muted-foreground text-sm">Firing</div>
            </div>
            <div className="bg-transparent rounded-xl p-4 border border-border">
              <div className="text-2xl font-bold text-yellow-400">{summary.pending}</div>
              <div className="text-muted-foreground text-sm">Pending</div>
            </div>
            <div className="bg-transparent rounded-xl p-4 border border-border">
              <div className="text-2xl font-bold text-muted-foreground">{summary.disabled}</div>
              <div className="text-muted-foreground text-sm">Disabled</div>
            </div>
          </div>
        )}

        {/* Rules List */}
        <div className="bg-transparent rounded-xl border border-border">
          <div className="p-6 border-b border-border">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-yellow-500/10">
                <Bell className="w-4 h-4 text-yellow-400" />
              </div>
              <span className="font-medium text-foreground text-base">Alert Rules</span>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-secondary text-muted-foreground border-border ml-auto">
                {rules.length} rule{rules.length !== 1 ? 's' : ''}
              </span>
            </div>
          </div>

          <div className="p-6">
            {rules.length === 0 ? (
              <div className="text-center py-12">
                <Bell className="h-12 w-12 text-muted-foreground mx-auto mb-4 opacity-50" />
                <h3 className="text-base font-medium text-foreground mb-2">No Alert Rules</h3>
                <p className="text-muted-foreground text-sm mb-4">Create your first alert rule to monitor your infrastructure</p>
                <Button
                  onClick={() => { resetForm(); setShowCreateModal(true); }}
                  className="bg-primary text-primary-foreground hover:bg-white/90"
                >
                  Create Alert Rule
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                {rules.map((rule) => (
                  <div
                    key={rule.id}
                    className={`p-4 rounded-lg border transition-all ${
                      rule.status === 'firing' ? 'border-red-500/20 bg-red-500/5' :
                      rule.status === 'disabled' ? 'border-border bg-transparent opacity-60' :
                      'border-border bg-transparent'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <h3 className="font-medium text-foreground text-sm">{rule.name}</h3>
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${getStatusBadge(rule.status)}`}>
                            {rule.status.toUpperCase()}
                          </span>
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${getSeverityBadge(rule.severity)}`}>
                            {rule.severity.toUpperCase()}
                          </span>
                        </div>
                        {rule.description && (
                          <p className="text-muted-foreground text-sm mb-2">{rule.description}</p>
                        )}
                        <div className="flex flex-wrap items-center gap-3 text-sm">
                          <span className="font-mono bg-accent px-2 py-1 rounded text-xs text-foreground">
                            {rule.condition_text}
                          </span>
                          {rule.current_value !== undefined && rule.current_value !== null && (
                            <span className="text-muted-foreground text-xs">
                              Current: <span className="text-foreground">{rule.current_value.toFixed(2)}</span>
                            </span>
                          )}
                          <span className="text-muted-foreground flex items-center gap-1 text-xs">
                            <Clock className="h-3 w-3" />
                            Window: {formatDuration(rule.evaluation_window)}
                          </span>
                          {rule.duration > 0 && (
                            <span className="text-muted-foreground text-xs">
                              For: {formatDuration(rule.duration)}
                            </span>
                          )}
                        </div>
                        {rule.last_evaluated_at && (
                          <div className="text-xs text-muted-foreground mt-2">
                            Last evaluated: {new Date(rule.last_evaluated_at).toLocaleString()}
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-2 ml-4">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => toggleRule(rule.id, rule.status === 'disabled')}
                          className={rule.status === 'disabled' ? 'text-muted-foreground hover:text-emerald-400' : 'text-emerald-400 hover:text-yellow-400'}
                        >
                          {rule.status === 'disabled' ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEditModal(rule)}
                          className="text-muted-foreground hover:text-blue-400"
                        >
                          <Edit2 className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => deleteRule(rule.id)}
                          className="text-muted-foreground hover:text-red-400"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Create/Edit Modal */}
      {(showCreateModal || editingRule) && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
          <div className="bg-background border border-border rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-border">
              <h2 className="text-lg font-semibold text-foreground">
                {editingRule ? 'Edit Alert Rule' : 'Create Alert Rule'}
              </h2>
              <p className="text-muted-foreground text-sm mt-1">
                Define conditions that trigger alerts and create incidents
              </p>
            </div>

            <div className="p-6 space-y-4">
              {/* Name & Description */}
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Rule Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g., High CPU Alert"
                  className="w-full px-3 py-2 bg-accent border border-border rounded-lg text-foreground placeholder-muted-foreground focus:border-primary/50 focus:ring-1 focus:ring-primary/30 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Description (optional)</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Describe when this alert should trigger..."
                  rows={2}
                  className="w-full px-3 py-2 bg-accent border border-border rounded-lg text-foreground placeholder-muted-foreground focus:border-primary/50 focus:ring-1 focus:ring-primary/30 focus:outline-none"
                />
              </div>

              {/* Condition */}
              <div className="bg-secondary/50 rounded-lg p-4 border border-border">
                <h3 className="font-medium text-foreground mb-3">Condition</h3>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="block text-xs text-muted-foreground mb-1">Metric</label>
                    <select
                      value={formData.metric_name}
                      onChange={(e) => setFormData({ ...formData, metric_name: e.target.value })}
                      className="w-full px-3 py-2 bg-accent border border-border rounded-lg text-foreground focus:outline-none"
                    >
                      {METRIC_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-muted-foreground mb-1">Operator</label>
                    <select
                      value={formData.operator}
                      onChange={(e) => setFormData({ ...formData, operator: e.target.value })}
                      className="w-full px-3 py-2 bg-accent border border-border rounded-lg text-foreground focus:outline-none"
                    >
                      {OPERATOR_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-muted-foreground mb-1">Threshold</label>
                    <input
                      type="number"
                      value={formData.threshold}
                      onChange={(e) => setFormData({ ...formData, threshold: parseFloat(e.target.value) })}
                      className="w-full px-3 py-2 bg-accent border border-border rounded-lg text-foreground focus:outline-none"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3 mt-3">
                  <div>
                    <label className="block text-xs text-muted-foreground mb-1">Aggregation</label>
                    <select
                      value={formData.aggregation}
                      onChange={(e) => setFormData({ ...formData, aggregation: e.target.value })}
                      className="w-full px-3 py-2 bg-accent border border-border rounded-lg text-foreground focus:outline-none"
                    >
                      {AGGREGATION_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-muted-foreground mb-1">Evaluation Window (seconds)</label>
                    <input
                      type="number"
                      value={formData.evaluation_window}
                      onChange={(e) => setFormData({ ...formData, evaluation_window: parseInt(e.target.value) })}
                      min={60}
                      max={3600}
                      className="w-full px-3 py-2 bg-accent border border-border rounded-lg text-foreground focus:outline-none"
                    />
                  </div>
                </div>
                <div className="mt-3">
                  <label className="block text-xs text-muted-foreground mb-1">
                    Duration (seconds) - How long condition must be true
                  </label>
                  <input
                    type="number"
                    value={formData.duration}
                    onChange={(e) => setFormData({ ...formData, duration: parseInt(e.target.value) })}
                    min={0}
                    max={3600}
                    className="w-full px-3 py-2 bg-accent border border-border rounded-lg text-foreground focus:outline-none"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Set to 0 for immediate alerting, or enter seconds (e.g., 300 for 5 minutes)
                  </p>
                </div>
              </div>

              {/* Test Button & Results */}
              <div className="flex items-center gap-3">
                <Button
                  variant="outline"
                  onClick={testRule}
                  disabled={testingRule}
                  className="border-border text-foreground hover:bg-accent"
                >
                  <TestTube className="h-4 w-4 mr-2" />
                  {testingRule ? 'Testing...' : 'Test Rule'}
                </Button>
                {testResult && (
                  <div className={`flex items-center gap-2 text-sm ${testResult.would_trigger ? 'text-red-400' : 'text-emerald-400'}`}>
                    {testResult.would_trigger ? (
                      <>
                        <AlertTriangle className="h-4 w-4" />
                        Would trigger! Current: {testResult.current_value?.toFixed(2)} ({testResult.hosts_triggering}/{testResult.hosts_checked} hosts)
                      </>
                    ) : (
                      <>
                        <Check className="h-4 w-4" />
                        Would not trigger. Current: {testResult.current_value?.toFixed(2)}
                      </>
                    )}
                  </div>
                )}
              </div>

              {/* Severity & Actions */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1">Severity</label>
                  <select
                    value={formData.severity}
                    onChange={(e) => setFormData({ ...formData, severity: e.target.value })}
                    className="w-full px-3 py-2 bg-accent border border-border rounded-lg text-foreground focus:outline-none"
                  >
                    {SEVERITY_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1">Cooldown (seconds)</label>
                  <input
                    type="number"
                    value={formData.cooldown_seconds}
                    onChange={(e) => setFormData({ ...formData, cooldown_seconds: parseInt(e.target.value) })}
                    min={60}
                    max={86400}
                    className="w-full px-3 py-2 bg-accent border border-border rounded-lg text-foreground focus:outline-none"
                  />
                </div>
              </div>

              {/* Toggles */}
              <div className="flex items-center gap-6">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.auto_create_incident}
                    onChange={(e) => setFormData({ ...formData, auto_create_incident: e.target.checked })}
                    className="rounded border-border bg-accent text-primary focus:ring-primary"
                  />
                  <span className="text-foreground text-sm">Auto-create incident</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.auto_resolve}
                    onChange={(e) => setFormData({ ...formData, auto_resolve: e.target.checked })}
                    className="rounded border-border bg-accent text-primary focus:ring-primary"
                  />
                  <span className="text-foreground text-sm">Auto-resolve when cleared</span>
                </label>
              </div>
            </div>

            <div className="p-6 border-t border-border flex justify-end gap-3">
              <Button
                variant="ghost"
                onClick={() => { setShowCreateModal(false); setEditingRule(null); resetForm(); }}
                className="text-muted-foreground hover:text-foreground"
              >
                Cancel
              </Button>
              <Button
                onClick={editingRule ? updateRule : createRule}
                disabled={!formData.name || !formData.metric_name}
                className="bg-primary text-primary-foreground hover:bg-white/90"
              >
                {editingRule ? 'Update Rule' : 'Create Rule'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
