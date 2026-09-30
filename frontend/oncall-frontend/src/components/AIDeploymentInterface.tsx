// frontend/oncall-frontend/src/components/AIDeploymentInterface.tsx
import React, { useState, useEffect, useRef } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  Clock,
  Cpu,
  Eye,
  FileText,
  Pause,
  Play,
  ShieldCheck,
  Square,
  Terminal,
  Undo2,
  XCircle,
  Zap
} from 'lucide-react';
import { useNotifications } from '../contexts/NotificationContext';
import { API_URL } from '../config/api';

interface DeploymentStep {
  id: string;
  command: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  output?: string;
  error?: string;
  startTime?: string;
  endTime?: string;
  duration?: number;
}

interface DeploymentSolution {
  provider: 'claude' | 'gemini';
  description: string;
  steps: string[];
  commands: string[];
  estimatedTime: string;
  riskLevel: 'low' | 'medium' | 'high';
  reversible: boolean;
}

interface AIDeploymentInterfaceProps {
  incidentId: string;
  provider: 'claude' | 'gemini';
  solution: DeploymentSolution;
  onDeploymentComplete: (success: boolean, deploymentId?: string) => void;
  onCancel: () => void;
}

type DeploymentStatus = 'ready' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled' | 'rolling_back';

const AIDeploymentInterface: React.FC<AIDeploymentInterfaceProps> = ({
  incidentId,
  provider,
  solution,
  onDeploymentComplete,
  onCancel
}) => {
  const { showToast } = useNotifications();
  const [deploymentStatus, setDeploymentStatus] = useState<DeploymentStatus>('ready');
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [deploymentSteps, setDeploymentSteps] = useState<DeploymentStep[]>([]);
  const [deploymentId, setDeploymentId] = useState<string | null>(null);
  const [startTime, setStartTime] = useState<Date | null>(null);
  const [endTime, setEndTime] = useState<Date | null>(null);
  const [showLogs, setShowLogs] = useState(false);
  const [realTimeOutput, setRealTimeOutput] = useState<string>('');

  const wsRef = useRef<WebSocket | null>(null);
  const logContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Initialize deployment steps from solution
    const steps: DeploymentStep[] = solution.commands.map((command, index) => ({
      id: `step-${index}`,
      command,
      description: solution.steps[index] || `Execute step ${index + 1}`,
      status: 'pending'
    }));

    setDeploymentSteps(steps);
  }, [solution]);

  useEffect(() => {
    // Auto-scroll logs to bottom
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [realTimeOutput]);

  const startDeployment = async () => {
    if (deploymentStatus === 'running') return;

    try {
      setDeploymentStatus('running');
      setStartTime(new Date());

      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_URL}/incidents/${incidentId}/deploy-solution`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          provider,
          solution: {
            commands: solution.commands,
            steps: solution.steps,
            risk_level: solution.riskLevel
          },
          execution_mode: 'supervised' // supervised | automatic
        })
      });

      if (!response.ok) {
        throw new Error(`Deployment failed: ${response.status}`);
      }

      const data = await response.json();
      setDeploymentId(data.deployment_id);

      // Set up WebSocket for real-time updates
      setupWebSocketConnection(data.deployment_id);

      showToast({
        type: 'info',
        title: 'Deployment Started',
        message: `${provider} solution deployment initiated. Monitoring progress...`,
        autoClose: true,
        duration: 3000
      });

    } catch (error) {
      console.error('Deployment start failed:', error);
      setDeploymentStatus('failed');

      showToast({
        type: 'error',
        title: 'Deployment Failed',
        message: `Failed to start deployment: ${error instanceof Error ? error.message : 'Unknown error'}`,
        autoClose: true
      });
    }
  };

  const setupWebSocketConnection = (deploymentId: string) => {
    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/v1/deployments/${deploymentId}/stream`;

    wsRef.current = new WebSocket(wsUrl);

    wsRef.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleDeploymentUpdate(data);
      } catch (error) {
        console.error('WebSocket message parse error:', error);
      }
    };

    wsRef.current.onclose = () => {
      console.log('WebSocket connection closed');
    };

    wsRef.current.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  };

  const handleDeploymentUpdate = (update: any) => {
    switch (update.type) {
      case 'step_started':
        updateStepStatus(update.step_id, 'running', update.start_time);
        setCurrentStepIndex(update.step_index);
        break;

      case 'step_completed':
        updateStepStatus(update.step_id, 'completed', update.start_time, update.end_time, update.output);
        break;

      case 'step_failed':
        updateStepStatus(update.step_id, 'failed', update.start_time, update.end_time, update.output, update.error);
        break;

      case 'deployment_completed':
        setDeploymentStatus('completed');
        setEndTime(new Date());
        onDeploymentComplete(true, deploymentId || undefined);

        showToast({
          type: 'success',
          title: 'Deployment Successful',
          message: `${provider} solution deployed successfully in ${update.total_duration}`,
          autoClose: true,
          duration: 5000
        });
        break;

      case 'deployment_failed':
        setDeploymentStatus('failed');
        setEndTime(new Date());
        onDeploymentComplete(false);

        showToast({
          type: 'error',
          title: 'Deployment Failed',
          message: `Deployment failed: ${update.error}`,
          autoClose: true
        });
        break;

      case 'output':
        setRealTimeOutput(prev => prev + update.data + '\n');
        break;
    }
  };

  const updateStepStatus = (
    stepId: string,
    status: DeploymentStep['status'],
    startTime?: string,
    endTime?: string,
    output?: string,
    error?: string
  ) => {
    setDeploymentSteps(prev => prev.map(step =>
      step.id === stepId
        ? {
            ...step,
            status,
            startTime,
            endTime,
            output,
            error,
            duration: startTime && endTime ?
              new Date(endTime).getTime() - new Date(startTime).getTime() : undefined
          }
        : step
    ));
  };

  const pauseDeployment = async () => {
    if (!deploymentId) return;

    try {
      const token = localStorage.getItem('access_token');
      await fetch(`${API_URL}/deployments/${deploymentId}/pause`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      setDeploymentStatus('paused');
      showToast({
        type: 'info',
        title: 'Deployment Paused',
        message: 'Deployment has been paused. You can resume or cancel.',
        autoClose: true
      });
    } catch (error) {
      console.error('Pause deployment failed:', error);
    }
  };

  const resumeDeployment = async () => {
    if (!deploymentId) return;

    try {
      const token = localStorage.getItem('access_token');
      await fetch(`${API_URL}/deployments/${deploymentId}/resume`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      setDeploymentStatus('running');
      showToast({
        type: 'info',
        title: 'Deployment Resumed',
        message: 'Deployment has been resumed.',
        autoClose: true
      });
    } catch (error) {
      console.error('Resume deployment failed:', error);
    }
  };

  const cancelDeployment = async () => {
    if (!deploymentId) {
      onCancel();
      return;
    }

    try {
      const token = localStorage.getItem('access_token');
      await fetch(`${API_URL}/deployments/${deploymentId}/cancel`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      setDeploymentStatus('cancelled');
      wsRef.current?.close();
      onCancel();

      showToast({
        type: 'warning',
        title: 'Deployment Cancelled',
        message: 'Deployment has been cancelled.',
        autoClose: true
      });
    } catch (error) {
      console.error('Cancel deployment failed:', error);
    }
  };

  const rollbackDeployment = async () => {
    if (!deploymentId || !solution.reversible) return;

    try {
      setDeploymentStatus('rolling_back');

      const token = localStorage.getItem('access_token');
      await fetch(`${API_URL}/deployments/${deploymentId}/rollback`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      showToast({
        type: 'info',
        title: 'Rolling Back',
        message: 'Initiating rollback process...',
        autoClose: true
      });
    } catch (error) {
      console.error('Rollback failed:', error);
      showToast({
        type: 'error',
        title: 'Rollback Failed',
        message: 'Failed to initiate rollback. Please manually revert changes.',
        autoClose: true
      });
    }
  };

  const formatDuration = (ms?: number) => {
    if (!ms) return '';
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    return `${minutes}:${(seconds % 60).toString().padStart(2, '0')}`;
  };

  const getStatusIcon = (status: DeploymentStep['status']) => {
    switch (status) {
      case 'running':
        return <Cpu className="w-4 h-4 text-blue-400 animate-spin" />;
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-400" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-400" />;
      case 'skipped':
        return <AlertTriangle className="w-4 h-4 text-yellow-400" />;
      default:
        return <Clock className="w-4 h-4 text-muted-foreground" />;
    }
  };

  const getStatusBadgeClasses = (status: DeploymentStatus): string => {
    switch (status) {
      case 'running': return 'bg-secondary text-muted-foreground border-border';
      case 'completed': return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      case 'failed': return 'bg-red-500/10 text-red-400 border-red-500/20';
      case 'paused': return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20';
      case 'rolling_back': return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20';
      default: return 'bg-secondary text-muted-foreground border-border';
    }
  };

  const getStatusPulseColor = (status: DeploymentStatus): string => {
    switch (status) {
      case 'running': return 'bg-blue-500';
      case 'completed': return 'bg-emerald-500';
      case 'failed': return 'bg-red-500';
      case 'paused': return 'bg-yellow-500';
      case 'rolling_back': return 'bg-yellow-500';
      default: return 'bg-purple-500';
    }
  };

  const getTotalDuration = () => {
    if (!startTime) return null;
    const end = endTime || new Date();
    return end.getTime() - startTime.getTime();
  };

  return (
    <div className="border border-border rounded-lg bg-transparent p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <div className={`p-2 rounded-xl ${
            provider === 'claude' ? 'bg-blue-500/10' : 'bg-purple-500/10'
          }`}>
            {provider === 'claude' ? (
              <Cpu className="w-6 h-6 text-blue-400" />
            ) : (
              <Terminal className="w-6 h-6 text-purple-400" />
            )}
          </div>
          <div>
            <h3 className="text-base font-medium text-foreground">
              {provider === 'claude' ? 'Claude Code' : 'Gemini CLI'} Deployment
            </h3>
            <p className="text-sm text-muted-foreground">{solution.description}</p>
          </div>
        </div>

        <div className="text-right flex flex-col items-end gap-1">
          <div className="flex items-center gap-2">
            <span className={`h-2.5 w-2.5 rounded-full ${getStatusPulseColor(deploymentStatus)} inline-block`} />
            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${getStatusBadgeClasses(deploymentStatus)}`}>
              {deploymentStatus.replace('_', ' ')}
            </span>
          </div>
          {getTotalDuration() && (
            <div className="text-sm text-muted-foreground">
              {formatDuration(getTotalDuration()!)}
            </div>
          )}
        </div>
      </div>

      {/* Risk Assessment */}
      <div className="border border-border rounded-lg bg-transparent p-4">
        <div className="flex items-center space-x-4">
          <div className="p-2 rounded-lg bg-yellow-500/10">
            <Zap className="w-5 h-5 text-yellow-400" />
          </div>
          <div className="flex-1">
            <div className="flex items-center space-x-2">
              <span className="text-foreground font-medium">Risk Level: </span>
              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${
                solution.riskLevel === 'low' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
                solution.riskLevel === 'high' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                'bg-yellow-500/10 text-yellow-400 border-yellow-500/20'
              }`}>
                {solution.riskLevel.toUpperCase()}
              </span>
              {solution.reversible && (
                <span className="flex items-center text-green-400 text-xs">
                  <ShieldCheck className="w-4 h-4 mr-1" />
                  Reversible
                </span>
              )}
            </div>
            <p className="text-muted-foreground text-sm mt-1">
              Estimated completion: {solution.estimatedTime}
            </p>
          </div>
        </div>
      </div>

      {/* Control Buttons */}
      <div className="flex items-center space-x-3">
        {deploymentStatus === 'ready' && (
          <button
            onClick={startDeployment}
            className="bg-primary text-primary-foreground hover:bg-white/90 rounded-md px-6 py-2.5 text-sm font-medium inline-flex items-center gap-2"
          >
            <Play className="w-5 h-5" />
            <span>Start Deployment</span>
          </button>
        )}

        {deploymentStatus === 'running' && (
          <button
            onClick={pauseDeployment}
            className="border border-border text-foreground hover:bg-accent rounded-md px-6 py-2.5 text-sm font-medium inline-flex items-center gap-2"
          >
            <Pause className="w-4 h-4" />
            <span>Pause</span>
          </button>
        )}

        {deploymentStatus === 'paused' && (
          <button
            onClick={resumeDeployment}
            className="bg-primary text-primary-foreground hover:bg-white/90 rounded-md px-6 py-2.5 text-sm font-medium inline-flex items-center gap-2"
          >
            <Play className="w-4 h-4" />
            <span>Resume</span>
          </button>
        )}

        {['running', 'paused'].includes(deploymentStatus) && (
          <button
            onClick={cancelDeployment}
            className="border border-red-500/20 text-red-400 hover:bg-red-500/10 rounded-md px-6 py-2.5 text-sm font-medium inline-flex items-center gap-2"
          >
            <Square className="w-4 h-4" />
            <span>Cancel</span>
          </button>
        )}

        {['completed', 'failed'].includes(deploymentStatus) && solution.reversible && (
          <button
            onClick={rollbackDeployment}
            className="border border-orange-500/20 text-orange-400 hover:bg-orange-500/10 rounded-md px-6 py-2.5 text-sm font-medium inline-flex items-center gap-2"
          >
            <Undo2 className="w-4 h-4" />
            <span>Rollback</span>
          </button>
        )}

        <button
          onClick={() => setShowLogs(!showLogs)}
          className="border border-border text-foreground hover:bg-accent rounded-md px-6 py-2.5 text-sm font-medium inline-flex items-center gap-2"
        >
          <Eye className="w-4 h-4" />
          <span>{showLogs ? 'Hide' : 'Show'} Logs</span>
        </button>

        <button
          onClick={onCancel}
          className="text-muted-foreground hover:text-foreground transition-colors"
        >
          Close
        </button>
      </div>

      {/* Deployment Steps */}
      <div className="space-y-3">
        <h4 className="text-base font-medium text-foreground">Deployment Steps</h4>
        {deploymentSteps.map((step, index) => (
          <div
            key={step.id}
            className={`border border-border rounded-lg bg-transparent p-4 ${
              currentStepIndex === index && deploymentStatus === 'running'
                ? 'border-blue-500/50 bg-blue-500/5'
                : ''
            }`}
          >
            <div className="flex items-center space-x-3">
              {getStatusIcon(step.status)}
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <span className="text-foreground font-medium">{step.description}</span>
                  {step.duration && (
                    <span className="text-xs text-muted-foreground">{formatDuration(step.duration)}</span>
                  )}
                </div>
                <code className="text-xs text-muted-foreground font-mono">{step.command}</code>
              </div>
            </div>

            {step.output && (
              <div className="mt-2 p-2 bg-transparent border border-border rounded text-xs text-green-400 font-mono">
                {step.output}
              </div>
            )}

            {step.error && (
              <div className="mt-2 p-2 bg-red-900/20 border border-red-500/20 rounded text-xs text-red-400 font-mono">
                {step.error}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Real-time Logs */}
      {showLogs && (
        <div className="space-y-2">
          <h4 className="text-base font-medium text-foreground flex items-center">
            <FileText className="w-5 h-5 mr-2" />
            Real-time Output
          </h4>
          <div
            ref={logContainerRef}
            className="bg-transparent border border-border rounded-lg p-4 h-64 overflow-y-auto font-mono text-xs text-green-400"
          >
            <pre className="whitespace-pre-wrap">{realTimeOutput || 'Waiting for output...'}</pre>
          </div>
        </div>
      )}
    </div>
  );
};

export default AIDeploymentInterface;
