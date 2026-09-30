// RunbookExecutionMonitor.tsx - Real-time runbook execution monitoring
import React, { useState, useEffect, useRef } from 'react';
import {
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Clock,
  Play,
  RefreshCw,
  Square,
  Terminal,
  XCircle
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useNotifications } from '../contexts/NotificationContext';
// Magic UI imports removed - using plain HTML/Tailwind equivalents

import { API_URL as API_BASE_URL } from '../config/api';

interface DeploymentStep {
  step_number: number;
  name: string;
  command: string;
  status: string;
  output?: string;
  error_output?: string;
  started_at?: string;
  completed_at?: string;
  duration?: number;
}

interface Deployment {
  id: string;
  status: string;
  started_at?: string;
  completed_at?: string;
  steps?: DeploymentStep[];
}

interface RunbookExecution {
  id: string;
  runbook_id: string;
  status: string;
  trigger_type: string;
  is_dry_run: boolean;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  output_summary?: string;
  deployment?: Deployment;
  runbook?: {
    id: string;
    title: string;
    description?: string;
  };
}

interface RunbookExecutionMonitorProps {
  executionId: string;
  onClose?: () => void;
  onCompleted?: (success: boolean) => void;
}

const RunbookExecutionMonitor: React.FC<RunbookExecutionMonitorProps> = ({
  executionId,
  onClose,
  onCompleted
}) => {
  const { token } = useAuth();
  const { showToast } = useNotifications();

  const [execution, setExecution] = useState<RunbookExecution | null>(null);
  const [loading, setLoading] = useState(true);
  const [cancelling, setCancelling] = useState(false);
  const [expandedStep, setExpandedStep] = useState<number | null>(null);
  const outputRef = useRef<HTMLDivElement>(null);

  // Poll for execution status
  useEffect(() => {
    if (!token || !executionId) return;

    let intervalId: NodeJS.Timeout;

    const fetchExecution = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/runbooks/executions/${executionId}`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });

        if (!response.ok) throw new Error('Failed to fetch execution');

        const data: RunbookExecution = await response.json();
        setExecution(data);
        setLoading(false);

        // Stop polling if execution is complete
        if (['completed', 'failed', 'cancelled'].includes(data.status)) {
          clearInterval(intervalId);
          if (onCompleted) {
            onCompleted(data.status === 'completed');
          }
        }
      } catch (error) {
        console.error('Error fetching execution:', error);
        setLoading(false);
      }
    };

    fetchExecution();
    intervalId = setInterval(fetchExecution, 2000); // Poll every 2 seconds

    return () => clearInterval(intervalId);
  }, [token, executionId, onCompleted]);

  // Auto-scroll output
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [execution?.deployment?.steps]);

  // Cancel execution
  const handleCancel = async () => {
    if (!token) return;

    try {
      setCancelling(true);
      const response = await fetch(`${API_BASE_URL}/runbooks/executions/${executionId}/cancel`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) throw new Error('Failed to cancel execution');

      showToast({ message: 'Execution cancelled', type: 'success' });
    } catch (error) {
      console.error('Error cancelling execution:', error);
      showToast({ message: 'Failed to cancel execution', type: 'error' });
    } finally {
      setCancelling(false);
    }
  };

  // Get status color and icon
  const getStatusDisplay = (status: string) => {
    switch (status) {
      case 'pending':
        return {
          color: 'text-muted-foreground bg-accent',
          icon: <Clock className="h-4 w-4" />,
          label: 'Pending',
          badgeVariant: 'default' as const,
          pulseColor: 'blue' as const
        };
      case 'running':
        return {
          color: 'text-blue-400 bg-blue-500/10',
          icon: <RefreshCw className="h-4 w-4 animate-spin" />,
          label: 'Running',
          badgeVariant: 'info' as const,
          pulseColor: 'blue' as const
        };
      case 'completed':
      case 'success':
        return {
          color: 'text-emerald-400 bg-emerald-500/10',
          icon: <CheckCircle className="h-4 w-4" />,
          label: 'Completed',
          badgeVariant: 'success' as const,
          pulseColor: 'green' as const
        };
      case 'failed':
        return {
          color: 'text-red-400 bg-red-500/10',
          icon: <XCircle className="h-4 w-4" />,
          label: 'Failed',
          badgeVariant: 'error' as const,
          pulseColor: 'red' as const
        };
      case 'cancelled':
        return {
          color: 'text-yellow-400 bg-yellow-500/10',
          icon: <Square className="h-4 w-4" />,
          label: 'Cancelled',
          badgeVariant: 'warning' as const,
          pulseColor: 'yellow' as const
        };
      default:
        return {
          color: 'text-muted-foreground bg-accent',
          icon: <Clock className="h-4 w-4" />,
          label: status,
          badgeVariant: 'default' as const,
          pulseColor: 'blue' as const
        };
    }
  };

  // Format duration
  const formatDuration = (seconds?: number) => {
    if (!seconds) return '-';
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
  };

  if (loading) {
    return (
      <div className="border border-border rounded-lg bg-transparent">
        <div className="p-6">
          <div className="flex justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
          </div>
        </div>
      </div>
    );
  }

  if (!execution) {
    return (
      <div className="border border-border rounded-lg bg-transparent">
        <div className="p-6">
          <p className="text-center text-muted-foreground">
            Execution not found
          </p>
        </div>
      </div>
    );
  }

  const statusDisplay = getStatusDisplay(execution.status);
  const steps = execution.deployment?.steps || [];

  return (
    <div className="border border-border rounded-lg bg-transparent overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-border bg-transparent">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-purple-500/10 rounded-lg flex items-center justify-center">
                <Terminal className="h-5 w-5 text-purple-400" />
              </div>
              <h3 className="text-lg font-semibold text-foreground">
                {execution.runbook?.title || 'Runbook Execution'}
              </h3>
              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${
                statusDisplay.badgeVariant === 'success' ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400' :
                statusDisplay.badgeVariant === 'error' ? 'border-red-500/30 bg-red-500/10 text-red-400' :
                statusDisplay.badgeVariant === 'warning' ? 'border-yellow-500/30 bg-yellow-500/10 text-yellow-400' :
                statusDisplay.badgeVariant === 'info' ? 'border-blue-500/30 bg-blue-500/10 text-blue-400' :
                'border-border bg-secondary text-foreground'
              }`}>
                <span className={`h-2 w-2 rounded-full mr-1.5 ${
                  statusDisplay.pulseColor === 'green' ? 'bg-emerald-500' :
                  statusDisplay.pulseColor === 'red' ? 'bg-red-500' :
                  statusDisplay.pulseColor === 'yellow' ? 'bg-yellow-500' :
                  'bg-blue-500'
                }`} />
                {statusDisplay.label}
              </span>
              {execution.is_dry_run && (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border border-blue-500/30 bg-blue-500/10 text-blue-400">
                  Dry Run
                </span>
              )}
            </div>
            <p className="text-sm text-muted-foreground mt-1">
              Execution ID: {execution.id.slice(0, 8)}...
            </p>
          </div>
          <div className="flex items-center gap-2">
            {['pending', 'running'].includes(execution.status) && (
              <button
                onClick={handleCancel}
                disabled={cancelling}
                className="border border-red-500/30 text-red-400 hover:bg-red-500/10 rounded-md px-4 py-1.5 text-sm font-medium inline-flex items-center gap-1 disabled:opacity-50"
              >
                {cancelling ? (
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-red-600"></div>
                ) : (
                  <Square className="h-4 w-4" />
                )}
                <span className="ml-1">Cancel</span>
              </button>
            )}
            {onClose && (
              <button
                onClick={onClose}
                className="border border-border text-foreground hover:bg-accent rounded-md px-4 py-1.5 text-sm font-medium"
              >
                Close
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Progress */}
      {steps.length > 0 && (
        <div className="p-4 border-b border-border">
          <div className="flex items-center justify-between text-sm text-muted-foreground mb-2">
            <span>Progress</span>
            <span>
              {steps.filter(s => s.status === 'success' || s.status === 'completed').length} / {steps.length} steps
            </span>
          </div>
          <div className="h-2 bg-secondary rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-300 ${
                execution.status === 'failed' ? 'bg-red-500' :
                execution.status === 'completed' ? 'bg-green-500' : 'bg-indigo-500'
              }`}
              style={{
                width: `${(steps.filter(s => s.status === 'success' || s.status === 'completed' || s.status === 'failed').length / steps.length) * 100}%`
              }}
            />
          </div>
        </div>
      )}

      {/* Steps */}
      <div className="max-h-96 overflow-y-auto" ref={outputRef}>
        {steps.length > 0 ? (
          <div className="divide-y divide-border">
            {steps.map((step) => {
              const stepStatus = getStatusDisplay(step.status);
              const isExpanded = expandedStep === step.step_number;

              return (
                <div key={step.step_number} className="p-4">
                  <div
                    className="flex items-start justify-between cursor-pointer"
                    onClick={() => setExpandedStep(isExpanded ? null : step.step_number)}
                  >
                    <div className="flex items-start gap-3">
                      <span className={`inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium border mt-0.5 ${
                        stepStatus.badgeVariant === 'success' ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400' :
                        stepStatus.badgeVariant === 'error' ? 'border-red-500/30 bg-red-500/10 text-red-400' :
                        stepStatus.badgeVariant === 'warning' ? 'border-yellow-500/30 bg-yellow-500/10 text-yellow-400' :
                        stepStatus.badgeVariant === 'info' ? 'border-blue-500/30 bg-blue-500/10 text-blue-400' :
                        'border-border bg-secondary text-foreground'
                      }`}>
                        {stepStatus.icon}
                      </span>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-foreground">
                            Step {step.step_number}: {step.name}
                          </span>
                        </div>
                        <code className="text-xs text-muted-foreground font-mono">
                          {step.command.length > 60 ? step.command.slice(0, 60) + '...' : step.command}
                        </code>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {step.duration && (
                        <span className="text-xs text-muted-foreground">
                          {formatDuration(step.duration)}
                        </span>
                      )}
                      {isExpanded ? (
                        <ChevronUp className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <ChevronDown className="h-4 w-4 text-muted-foreground" />
                      )}
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="mt-3 ml-8 space-y-2">
                      <div>
                        <label className="text-xs font-medium text-muted-foreground">
                          Full Command
                        </label>
                        <pre className="mt-1 text-xs bg-accent text-foreground p-2 rounded overflow-x-auto">
                          {step.command}
                        </pre>
                      </div>
                      {step.output && (
                        <div>
                          <label className="text-xs font-medium text-muted-foreground">
                            Output
                          </label>
                          <pre className="mt-1 text-xs bg-accent text-green-400 p-2 rounded overflow-x-auto max-h-40">
                            {step.output}
                          </pre>
                        </div>
                      )}
                      {step.error_output && (
                        <div>
                          <label className="text-xs font-medium text-red-500">
                            Error Output
                          </label>
                          <pre className="mt-1 text-xs bg-accent text-red-400 p-2 rounded overflow-x-auto max-h-40">
                            {step.error_output}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="p-8 text-center text-muted-foreground">
            {execution.status === 'pending' ? (
              <p>Waiting to start execution...</p>
            ) : execution.is_dry_run ? (
              <div>
                <p className="mb-2">Dry run completed - no steps were executed.</p>
                <p className="text-sm">Run without dry run mode to execute the runbook.</p>
              </div>
            ) : (
              <p>No steps to display</p>
            )}
          </div>
        )}
      </div>

      {/* Error Message */}
      {execution.error_message && (
        <div className="p-4 border-t border-red-500/20 bg-red-500/10">
          <div className="flex items-start gap-2">
            <XCircle className="h-5 w-5 text-red-400 flex-shrink-0" />
            <div>
              <h4 className="text-sm font-medium text-red-400">
                Execution Error
              </h4>
              <p className="text-sm text-red-400/80 mt-1">
                {execution.error_message}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="p-4 border-t border-border bg-transparent">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <div className="flex items-center gap-4">
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border border-border bg-secondary text-foreground">
              Trigger: {execution.trigger_type}
            </span>
            {execution.started_at && (
              <span>
                Started: {new Date(execution.started_at).toLocaleTimeString()}
              </span>
            )}
            {execution.completed_at && (
              <span>
                Completed: {new Date(execution.completed_at).toLocaleTimeString()}
              </span>
            )}
          </div>
          {['completed', 'failed'].includes(execution.status) && (
            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${
              execution.status === 'completed' ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400' : 'border-red-500/30 bg-red-500/10 text-red-400'
            }`}>
              {execution.status === 'completed' ? 'Execution successful' : 'Execution failed'}
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

export default RunbookExecutionMonitor;
