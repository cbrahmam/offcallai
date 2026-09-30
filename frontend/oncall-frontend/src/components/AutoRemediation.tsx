// frontend/oncall-frontend/src/components/AutoRemediation.tsx
import React, { useState, useEffect } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  Bell,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Clock,
  Container,
  Database,
  Edit2,
  Eye,
  FileText,
  Loader2,
  Pause,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  Scale,
  Server,
  Settings,
  Shield,
  Target,
  Terminal,
  ThumbsDown,
  ThumbsUp,
  Ticket,
  Trash2,
  Webhook,
  XCircle,
  Zap
} from 'lucide-react';

import { API_URL as API_BASE_URL } from '../config/api';

interface RemediationRule {
  id: string;
  name: string;
  description: string | null;
  enabled: boolean;
  priority: number;
  trigger_type: string;
  trigger_conditions: Record<string, any>;
  scope_type: string | null;
  action_type: string;
  action_config: Record<string, any>;
  require_approval: boolean;
  max_executions_per_hour: number;
  cooldown_minutes: number;
  dry_run: boolean;
  execution_count: number;
  success_count: number;
  failure_count: number;
  last_executed_at: string | null;
  tags: string[];
  created_at: string;
}

interface RemediationExecution {
  id: string;
  rule_id: string | null;
  status: string;
  trigger_type: string;
  trigger_source: string | null;
  target_type: string | null;
  target_name: string | null;
  action_type: string;
  is_dry_run: boolean;
  is_manual: boolean;
  requires_approval: boolean;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  result: Record<string, any>;
  error_message: string | null;
  created_at: string;
}

interface RemediationPlaybook {
  id: string;
  name: string;
  description: string | null;
  category: string | null;
  steps: Array<{
    id: string;
    name: string;
    action_type: string;
    action_config: Record<string, any>;
  }>;
  enabled: boolean;
  execution_count: number;
  success_count: number;
  created_at: string;
}

interface RemediationStats {
  total_rules: number;
  active_rules: number;
  total_executions: number;
  successful_executions: number;
  failed_executions: number;
  pending_approvals: number;
  avg_execution_time_seconds: number;
  executions_last_24h: number;
  executions_last_7d: number;
}

type TabType = 'overview' | 'rules' | 'executions' | 'playbooks' | 'templates';

const AutoRemediation: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [rules, setRules] = useState<RemediationRule[]>([]);
  const [executions, setExecutions] = useState<RemediationExecution[]>([]);
  const [playbooks, setPlaybooks] = useState<RemediationPlaybook[]>([]);
  const [stats, setStats] = useState<RemediationStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreateRule, setShowCreateRule] = useState(false);
  const [showCreatePlaybook, setShowCreatePlaybook] = useState(false);
  const [expandedRule, setExpandedRule] = useState<string | null>(null);
  const [expandedExecution, setExpandedExecution] = useState<string | null>(null);

  const getAuthHeaders = () => {
    const token = localStorage.getItem('access_token');
    return {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    };
  };

  useEffect(() => {
    fetchData();
  }, [activeTab]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const headers = getAuthHeaders();

      if (activeTab === 'overview' || activeTab === 'rules') {
        const [statsRes, rulesRes] = await Promise.all([
          fetch(`${API_BASE_URL}/remediation/stats`, { headers }),
          fetch(`${API_BASE_URL}/remediation/rules?page_size=100`, { headers })
        ]);

        if (statsRes.ok) {
          const statsData = await statsRes.json();
          if (statsData && statsData.total_rules !== undefined) {
            setStats(statsData);
          } else {
            setStats(null);
          }
        } else {
          setStats(null);
        }

        if (rulesRes.ok) {
          const rulesData = await rulesRes.json();
          const fetchedRules = rulesData.items || [];
          setRules(fetchedRules);
        } else {
          setRules([]);
        }
      }

      if (activeTab === 'overview' || activeTab === 'executions') {
        const execRes = await fetch(`${API_BASE_URL}/remediation/executions?page_size=50`, { headers });
        if (execRes.ok) {
          const execData = await execRes.json();
          const fetchedExecs = execData.items || [];
          setExecutions(fetchedExecs);
        } else {
          setExecutions([]);
        }
      }

      if (activeTab === 'playbooks') {
        const playbooksRes = await fetch(`${API_BASE_URL}/remediation/playbooks`, { headers });
        if (playbooksRes.ok) {
          const playbooksData = await playbooksRes.json();
          const fetchedPlaybooks = playbooksData.items || [];
          setPlaybooks(fetchedPlaybooks);
        } else {
          setPlaybooks([]);
        }
      }
    } catch (error) {
      console.error('Error fetching remediation data:', error);
      setStats(null);
      setRules([]);
      setExecutions([]);
      setPlaybooks([]);
    } finally {
      setLoading(false);
    }
  };

  const toggleRule = async (ruleId: string, enabled: boolean) => {
    try {
      const res = await fetch(
        `${API_BASE_URL}/remediation/rules/${ruleId}/toggle?enabled=${enabled}`,
        { method: 'POST', headers: getAuthHeaders() }
      );
      if (res.ok) {
        fetchData();
      }
    } catch (error) {
      console.error('Error toggling rule:', error);
    }
  };

  const deleteRule = async (ruleId: string) => {
    if (!window.confirm('Are you sure you want to delete this rule?')) return;
    try {
      const res = await fetch(`${API_BASE_URL}/remediation/rules/${ruleId}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });
      if (res.ok) {
        fetchData();
      }
    } catch (error) {
      console.error('Error deleting rule:', error);
    }
  };

  const approveExecution = async (executionId: string, approved: boolean) => {
    try {
      const res = await fetch(`${API_BASE_URL}/remediation/executions/${executionId}/approve`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ approved, notes: approved ? 'Approved' : 'Rejected' })
      });
      if (res.ok) {
        fetchData();
      }
    } catch (error) {
      console.error('Error approving execution:', error);
    }
  };

  const getActionIcon = (actionType: string) => {
    const icons: Record<string, React.ReactNode> = {
      'restart_service': <RefreshCw className="w-4 h-4" />,
      'restart_pod': <Container className="w-4 h-4" />,
      'scale_up': <Scale className="w-4 h-4" />,
      'scale_down': <Scale className="w-4 h-4" />,
      'rollback_deployment': <RotateCcw className="w-4 h-4" />,
      'runbook_execution': <FileText className="w-4 h-4" />,
      'webhook_call': <Webhook className="w-4 h-4" />,
      'script_execution': <Terminal className="w-4 h-4" />,
      'notify_team': <Bell className="w-4 h-4" />,
      'create_ticket': <Ticket className="w-4 h-4" />,
      'clear_cache': <Database className="w-4 h-4" />,
      'drain_node': <Server className="w-4 h-4" />
    };
    return icons[actionType] || <Zap className="w-4 h-4" />;
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      'pending': 'bg-yellow-500/20 text-yellow-400',
      'queued': 'bg-blue-500/20 text-blue-400',
      'running': 'bg-blue-500/20 text-blue-400',
      'success': 'bg-green-500/20 text-green-400',
      'failed': 'bg-red-500/20 text-red-400',
      'cancelled': 'bg-secondary text-muted-foreground',
      'timeout': 'bg-orange-500/20 text-orange-400',
      'approval_required': 'bg-purple-500/20 text-purple-400',
      'approved': 'bg-green-500/20 text-green-400',
      'rejected': 'bg-red-500/20 text-red-400'
    };
    return colors[status] || 'bg-secondary text-muted-foreground';
  };

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return '-';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    return `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`;
  };

  const renderOverview = () => (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-card rounded-lg border border-border">
          <div className="p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-muted-foreground">Active Rules</span>
              <div className="p-2.5 rounded-xl bg-blue-500/10">
                <Shield className="w-4 h-4 text-blue-400" />
              </div>
            </div>
            <div className="text-2xl font-bold text-foreground">
              {stats?.active_rules || 0}
              <span className="text-sm text-muted-foreground ml-2">/ {stats?.total_rules || 0}</span>
            </div>
          </div>
        </div>

        <div className="bg-card rounded-lg border border-border">
          <div className="p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-muted-foreground">Executions (24h)</span>
              <div className="p-2.5 rounded-xl bg-yellow-500/10">
                <Zap className="w-4 h-4 text-yellow-400" />
              </div>
            </div>
            <div className="text-2xl font-bold text-foreground">
              {stats?.executions_last_24h || 0}
            </div>
          </div>
        </div>

        <div className="bg-card rounded-lg border border-border">
          <div className="p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-muted-foreground">Success Rate</span>
              <div className="p-2.5 rounded-xl bg-green-500/10">
                <CheckCircle className="w-4 h-4 text-green-400" />
              </div>
            </div>
            <div className="text-2xl font-bold text-foreground">
              {stats?.total_executions ?
                ((stats.successful_executions / stats.total_executions) * 100).toFixed(1) : 0}%
            </div>
          </div>
        </div>

        <div className="bg-card rounded-lg border border-border">
          <div className="p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-muted-foreground">Pending Approvals</span>
              <div className="p-2.5 rounded-xl bg-purple-500/10">
                <AlertTriangle className="w-4 h-4 text-purple-400" />
              </div>
            </div>
            <div className="text-2xl font-bold text-foreground">
              {stats?.pending_approvals || 0}
            </div>
          </div>
        </div>
      </div>

      {/* Recent Executions */}
      <div className="bg-card rounded-lg border border-border">
        <div className="p-4 border-b border-border">
          <h3 className="text-lg font-medium text-foreground">Recent Executions</h3>
        </div>
        <div className="divide-y divide-border">
          {executions.slice(0, 10).map((exec) => (
            <div key={exec.id} className="p-4 hover:bg-muted/50">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {getActionIcon(exec.action_type)}
                  <div>
                    <div className="text-foreground font-medium">
                      {exec.action_type.replace(/_/g, ' ')}
                      {exec.target_name && (
                        <span className="text-muted-foreground ml-2">on {exec.target_name}</span>
                      )}
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {new Date(exec.created_at).toLocaleString()}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`px-2 py-1 rounded-full text-xs ${getStatusColor(exec.status)}`}>
                    {exec.status}
                  </span>
                  {exec.status === 'approval_required' && (
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => approveExecution(exec.id, true)}
                        className="p-1 hover:bg-green-500/20 rounded text-green-400"
                      >
                        <ThumbsUp className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => approveExecution(exec.id, false)}
                        className="p-1 hover:bg-red-500/20 rounded text-red-400"
                      >
                        <ThumbsDown className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
          {executions.length === 0 && (
            <div className="p-8 text-center text-muted-foreground">
              No executions yet. Create rules to enable auto-remediation.
            </div>
          )}
        </div>
      </div>

      {/* Active Rules Preview */}
      <div className="bg-card rounded-lg border border-border">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h3 className="text-lg font-medium text-foreground">Active Rules</h3>
          <button
            onClick={() => setActiveTab('rules')}
            className="text-blue-400 hover:text-blue-300 text-sm"
          >
            View All
          </button>
        </div>
        <div className="divide-y divide-border">
          {rules.filter(r => r.enabled).slice(0, 5).map((rule) => (
            <div key={rule.id} className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {getActionIcon(rule.action_type)}
                  <div>
                    <div className="text-foreground font-medium">{rule.name}</div>
                    <div className="text-sm text-muted-foreground">
                      Trigger: {rule.trigger_type} | Executions: {rule.execution_count}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <CheckCircle className="w-4 h-4 text-green-400" />
                  {rule.success_count}
                  <XCircle className="w-4 h-4 text-red-400 ml-2" />
                  {rule.failure_count}
                </div>
              </div>
            </div>
          ))}
          {rules.filter(r => r.enabled).length === 0 && (
            <div className="p-8 text-center text-muted-foreground">
              No active rules. Enable or create rules to start auto-remediation.
            </div>
          )}
        </div>
      </div>
    </div>
  );

  const renderRules = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-foreground">Remediation Rules</h2>
        <button
          onClick={() => setShowCreateRule(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-foreground"
        >
          <Plus className="w-4 h-4" />
          Create Rule
        </button>
      </div>

      <div className="bg-card rounded-lg border border-border">
        <div className="divide-y divide-border">
          {rules.map((rule) => (
            <div key={rule.id} className="p-4">
              <div
                className="flex items-center justify-between cursor-pointer"
                onClick={() => setExpandedRule(expandedRule === rule.id ? null : rule.id)}
              >
                <div className="flex items-center gap-3">
                  {expandedRule === rule.id ? (
                    <ChevronDown className="w-5 h-5 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="w-5 h-5 text-muted-foreground" />
                  )}
                  {getActionIcon(rule.action_type)}
                  <div>
                    <div className="text-foreground font-medium">{rule.name}</div>
                    <div className="text-sm text-muted-foreground">
                      {rule.description || `${rule.trigger_type} → ${rule.action_type.replace(/_/g, ' ')}`}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <div className="text-sm text-muted-foreground">
                    {rule.execution_count} runs
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleRule(rule.id, !rule.enabled);
                    }}
                    className={`px-3 py-1 rounded-full text-xs ${
                      rule.enabled
                        ? 'bg-green-500/20 text-green-400'
                        : 'bg-secondary text-muted-foreground'
                    }`}
                  >
                    {rule.enabled ? 'Enabled' : 'Disabled'}
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteRule(rule.id);
                    }}
                    className="p-1 hover:bg-red-500/20 rounded text-red-400"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {expandedRule === rule.id && (
                <div className="mt-4 pl-10 space-y-3">
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">Trigger Type:</span>
                      <span className="text-foreground ml-2">{rule.trigger_type}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Action Type:</span>
                      <span className="text-foreground ml-2">{rule.action_type.replace(/_/g, ' ')}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Requires Approval:</span>
                      <span className="text-foreground ml-2">{rule.require_approval ? 'Yes' : 'No'}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Cooldown:</span>
                      <span className="text-foreground ml-2">{rule.cooldown_minutes} minutes</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Max/Hour:</span>
                      <span className="text-foreground ml-2">{rule.max_executions_per_hour}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Priority:</span>
                      <span className="text-foreground ml-2">{rule.priority}</span>
                    </div>
                  </div>

                  {Object.keys(rule.trigger_conditions).length > 0 && (
                    <div>
                      <span className="text-muted-foreground text-sm">Trigger Conditions:</span>
                      <pre className="mt-1 p-2 bg-card rounded text-xs text-foreground overflow-x-auto">
                        {JSON.stringify(rule.trigger_conditions, null, 2)}
                      </pre>
                    </div>
                  )}

                  <div className="flex items-center gap-4 pt-2">
                    <div className="flex items-center gap-1 text-green-400">
                      <CheckCircle className="w-4 h-4" />
                      <span className="text-sm">{rule.success_count} successful</span>
                    </div>
                    <div className="flex items-center gap-1 text-red-400">
                      <XCircle className="w-4 h-4" />
                      <span className="text-sm">{rule.failure_count} failed</span>
                    </div>
                    {rule.last_executed_at && (
                      <div className="text-sm text-muted-foreground">
                        Last run: {new Date(rule.last_executed_at).toLocaleString()}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
          {rules.length === 0 && (
            <div className="p-8 text-center text-muted-foreground">
              No rules configured yet. Click "Create Rule" to add your first auto-remediation rule.
            </div>
          )}
        </div>
      </div>
    </div>
  );

  const renderExecutions = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-foreground">Execution History</h2>
        <button
          onClick={fetchData}
          className="flex items-center gap-2 px-4 py-2 bg-muted hover:bg-muted/80 rounded-lg text-foreground"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      <div className="bg-card rounded-lg border border-border">
        <table className="w-full">
          <thead className="bg-muted/50">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Action</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Target</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Trigger</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Status</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Duration</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Time</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {executions.map((exec) => (
              <React.Fragment key={exec.id}>
                <tr
                  className="hover:bg-muted/50 cursor-pointer"
                  onClick={() => setExpandedExecution(expandedExecution === exec.id ? null : exec.id)}
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      {getActionIcon(exec.action_type)}
                      <span className="text-foreground">{exec.action_type.replace(/_/g, ' ')}</span>
                      {exec.is_dry_run && (
                        <span className="px-1.5 py-0.5 bg-yellow-500/20 text-yellow-400 text-xs rounded">
                          Dry Run
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-foreground">{exec.target_name || '-'}</td>
                  <td className="px-4 py-3">
                    <span className="text-muted-foreground">{exec.trigger_type}</span>
                    {exec.is_manual && (
                      <span className="ml-1 text-xs text-blue-400">(manual)</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded-full text-xs ${getStatusColor(exec.status)}`}>
                      {exec.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {formatDuration(exec.duration_seconds)}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground text-sm">
                    {new Date(exec.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    {exec.status === 'approval_required' && (
                      <div className="flex items-center gap-1">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            approveExecution(exec.id, true);
                          }}
                          className="p-1 hover:bg-green-500/20 rounded text-green-400"
                          title="Approve"
                        >
                          <ThumbsUp className="w-4 h-4" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            approveExecution(exec.id, false);
                          }}
                          className="p-1 hover:bg-red-500/20 rounded text-red-400"
                          title="Reject"
                        >
                          <ThumbsDown className="w-4 h-4" />
                        </button>
                      </div>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setExpandedExecution(expandedExecution === exec.id ? null : exec.id);
                      }}
                      className="p-1 hover:bg-muted rounded text-muted-foreground"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
                {expandedExecution === exec.id && (
                  <tr>
                    <td colSpan={7} className="px-4 py-4 bg-card/50">
                      <div className="space-y-3">
                        {exec.error_message && (
                          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded">
                            <div className="text-red-400 font-medium">Error:</div>
                            <div className="text-red-300 text-sm">{exec.error_message}</div>
                          </div>
                        )}
                        {Object.keys(exec.result).length > 0 && (
                          <div>
                            <div className="text-muted-foreground text-sm mb-1">Result:</div>
                            <pre className="p-2 bg-card rounded text-xs text-foreground overflow-x-auto">
                              {JSON.stringify(exec.result, null, 2)}
                            </pre>
                          </div>
                        )}
                        <div className="grid grid-cols-3 gap-4 text-sm">
                          <div>
                            <span className="text-muted-foreground">Started:</span>
                            <span className="text-foreground ml-2">
                              {exec.started_at ? new Date(exec.started_at).toLocaleString() : '-'}
                            </span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Completed:</span>
                            <span className="text-foreground ml-2">
                              {exec.completed_at ? new Date(exec.completed_at).toLocaleString() : '-'}
                            </span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Execution ID:</span>
                            <span className="text-foreground ml-2 font-mono text-xs">{exec.id}</span>
                          </div>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
            {executions.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                  No executions yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );

  const renderPlaybooks = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-foreground">Remediation Playbooks</h2>
        <button
          onClick={() => setShowCreatePlaybook(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-foreground"
        >
          <Plus className="w-4 h-4" />
          Create Playbook
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {playbooks.map((playbook) => (
          <div key={playbook.id} className="bg-card rounded-lg border border-border p-4">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-foreground font-medium">{playbook.name}</h3>
                {playbook.description && (
                  <p className="text-muted-foreground text-sm mt-1">{playbook.description}</p>
                )}
              </div>
              <span className={`px-2 py-1 rounded text-xs ${
                playbook.enabled ? 'bg-green-500/20 text-green-400' : 'bg-secondary text-muted-foreground'
              }`}>
                {playbook.enabled ? 'Active' : 'Inactive'}
              </span>
            </div>

            <div className="mt-4">
              <div className="text-muted-foreground text-sm mb-2">Steps ({playbook.steps.length}):</div>
              <div className="space-y-2">
                {playbook.steps.map((step, idx) => (
                  <div key={step.id} className="flex items-center gap-2 text-sm">
                    <span className="w-5 h-5 rounded-full bg-muted flex items-center justify-center text-xs text-muted-foreground">
                      {idx + 1}
                    </span>
                    {getActionIcon(step.action_type)}
                    <span className="text-foreground">{step.name}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="mt-4 flex items-center justify-between border-t border-border pt-3">
              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                <span>{playbook.execution_count} runs</span>
                <span className="text-green-400">{playbook.success_count} success</span>
              </div>
              <button className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 rounded text-foreground text-sm">
                <Play className="w-3 h-3" />
                Run
              </button>
            </div>
          </div>
        ))}
        {playbooks.length === 0 && (
          <div className="col-span-2 bg-card rounded-lg border border-border p-8 text-center text-muted-foreground">
            No playbooks configured yet. Create a playbook to define multi-step remediation workflows.
          </div>
        )}
      </div>
    </div>
  );

  const renderTemplates = () => (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold text-foreground">Action Templates</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[
          { type: 'restart_service', name: 'Restart Service', desc: 'Restart a service or process', category: 'Infrastructure' },
          { type: 'restart_pod', name: 'Restart Pod', desc: 'Restart a Kubernetes pod', category: 'Kubernetes' },
          { type: 'scale_up', name: 'Scale Up', desc: 'Increase replicas/instances', category: 'Infrastructure' },
          { type: 'scale_down', name: 'Scale Down', desc: 'Decrease replicas/instances', category: 'Infrastructure' },
          { type: 'rollback_deployment', name: 'Rollback Deployment', desc: 'Roll back to previous version', category: 'Kubernetes' },
          { type: 'clear_cache', name: 'Clear Cache', desc: 'Clear application or database cache', category: 'Application' },
          { type: 'runbook_execution', name: 'Run Runbook', desc: 'Execute a predefined runbook', category: 'Automation' },
          { type: 'webhook_call', name: 'Webhook Call', desc: 'Call an external webhook', category: 'Integration' },
          { type: 'notify_team', name: 'Notify Team', desc: 'Send notification to team', category: 'Communication' },
        ].map((template) => (
          <div
            key={template.type}
            className="bg-card rounded-lg border border-border p-4 hover:border-blue-500/50 cursor-pointer transition-colors"
          >
            <div className="flex items-center gap-3">
              {getActionIcon(template.type)}
              <div>
                <h3 className="text-foreground font-medium">{template.name}</h3>
                <p className="text-muted-foreground text-sm">{template.desc}</p>
              </div>
            </div>
            <div className="mt-3 flex items-center justify-between">
              <span className="px-2 py-1 bg-muted rounded text-xs text-muted-foreground">
                {template.category}
              </span>
              <button className="text-blue-400 hover:text-blue-300 text-sm">
                Use Template
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  // Create Rule Modal
  const CreateRuleModal = () => {
    const [formData, setFormData] = useState({
      name: '',
      description: '',
      trigger_type: 'alert',
      action_type: 'restart_service',
      require_approval: false,
      enabled: true,
      priority: 50,
      cooldown_minutes: 15,
      max_executions_per_hour: 5
    });

    const handleSubmit = async (e: React.FormEvent) => {
      e.preventDefault();
      try {
        const res = await fetch(`${API_BASE_URL}/remediation/rules`, {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify({
            ...formData,
            trigger_conditions: {},
            action_config: {},
            scope_filter: {}
          })
        });
        if (res.ok) {
          setShowCreateRule(false);
          fetchData();
        }
      } catch (error) {
        console.error('Error creating rule:', error);
      }
    };

    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-card rounded-lg border border-border w-full max-w-lg mx-4">
          <div className="p-4 border-b border-border flex items-center justify-between">
            <h3 className="text-lg font-medium text-foreground">Create Remediation Rule</h3>
            <button
              onClick={() => setShowCreateRule(false)}
              className="text-muted-foreground hover:text-foreground"
            >
              <XCircle className="w-5 h-5" />
            </button>
          </div>
          <form onSubmit={handleSubmit} className="p-4 space-y-4">
            <div>
              <label className="block text-sm text-muted-foreground mb-1">Rule Name</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full bg-card border border-border rounded px-3 py-2 text-foreground"
                required
              />
            </div>

            <div>
              <label className="block text-sm text-muted-foreground mb-1">Description</label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="w-full bg-card border border-border rounded px-3 py-2 text-foreground"
                rows={2}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-muted-foreground mb-1">Trigger Type</label>
                <select
                  value={formData.trigger_type}
                  onChange={(e) => setFormData({ ...formData, trigger_type: e.target.value })}
                  className="w-full bg-card border border-border rounded px-3 py-2 text-foreground"
                >
                  <option value="alert">Alert</option>
                  <option value="anomaly">Anomaly</option>
                  <option value="incident">Incident</option>
                  <option value="threshold">Threshold</option>
                  <option value="schedule">Schedule</option>
                </select>
              </div>

              <div>
                <label className="block text-sm text-muted-foreground mb-1">Action Type</label>
                <select
                  value={formData.action_type}
                  onChange={(e) => setFormData({ ...formData, action_type: e.target.value })}
                  className="w-full bg-card border border-border rounded px-3 py-2 text-foreground"
                >
                  <option value="restart_service">Restart Service</option>
                  <option value="restart_pod">Restart Pod</option>
                  <option value="scale_up">Scale Up</option>
                  <option value="scale_down">Scale Down</option>
                  <option value="rollback_deployment">Rollback Deployment</option>
                  <option value="runbook_execution">Run Runbook</option>
                  <option value="webhook_call">Webhook Call</option>
                  <option value="notify_team">Notify Team</option>
                  <option value="clear_cache">Clear Cache</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-muted-foreground mb-1">Cooldown (minutes)</label>
                <input
                  type="number"
                  value={formData.cooldown_minutes}
                  onChange={(e) => setFormData({ ...formData, cooldown_minutes: parseInt(e.target.value) })}
                  className="w-full bg-card border border-border rounded px-3 py-2 text-foreground"
                  min="0"
                />
              </div>

              <div>
                <label className="block text-sm text-muted-foreground mb-1">Max Executions/Hour</label>
                <input
                  type="number"
                  value={formData.max_executions_per_hour}
                  onChange={(e) => setFormData({ ...formData, max_executions_per_hour: parseInt(e.target.value) })}
                  className="w-full bg-card border border-border rounded px-3 py-2 text-foreground"
                  min="1"
                />
              </div>
            </div>

            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.require_approval}
                  onChange={(e) => setFormData({ ...formData, require_approval: e.target.checked })}
                  className="rounded bg-card border-border"
                />
                <span className="text-sm text-foreground">Require Approval</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.enabled}
                  onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                  className="rounded bg-card border-border"
                />
                <span className="text-sm text-foreground">Enabled</span>
              </label>
            </div>

            <div className="flex justify-end gap-3 pt-4 border-t border-border">
              <button
                type="button"
                onClick={() => setShowCreateRule(false)}
                className="px-4 py-2 bg-muted hover:bg-muted/80 rounded text-foreground"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded text-foreground"
              >
                Create Rule
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="relative overflow-hidden border-b border-border">
        <div className="relative max-w-7xl mx-auto px-6 py-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-cyan-500/10">
                <Zap className="w-6 h-6 text-cyan-400" />
              </div>
              <div>
                <h1 className="text-base font-medium text-foreground">Auto-Remediation</h1>
                <p className="text-muted-foreground text-sm">Automated incident response and infrastructure healing</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
      {/* Tabs */}

      <div className="border-b border-border mb-6">
        <nav className="flex gap-6">
          {[
            { id: 'overview', label: 'Overview', icon: Target },
            { id: 'rules', label: 'Rules', icon: Shield },
            { id: 'executions', label: 'Executions', icon: Clock },
            { id: 'playbooks', label: 'Playbooks', icon: FileText },
            { id: 'templates', label: 'Templates', icon: Settings },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as TabType)}
              className={`flex items-center gap-2 pb-3 px-1 border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-400'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
        </div>
      ) : (
        <>
          {activeTab === 'overview' && renderOverview()}
          {activeTab === 'rules' && renderRules()}
          {activeTab === 'executions' && renderExecutions()}
          {activeTab === 'playbooks' && renderPlaybooks()}
          {activeTab === 'templates' && renderTemplates()}
        </>
      )}

      </div>

      {/* Modals */}
      {showCreateRule && <CreateRuleModal />}
    </div>
  );
};

export default AutoRemediation;
