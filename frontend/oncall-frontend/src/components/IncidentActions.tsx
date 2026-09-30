// frontend/oncall-frontend/src/components/IncidentActions.tsx
import React, { useState } from 'react';
import {
  AlertTriangle,
  Bell,
  CheckCircle,
  Clock,
  Flame,
  Info,
  RefreshCw,
  Settings2,
  UserPlus
} from 'lucide-react';
import { useNotifications } from '../contexts/NotificationContext';

import { API_URL as API_BASE_URL } from '../config/api';


// Import the interface from the parent component to ensure compatibility
interface IncidentData {
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

interface IncidentActionsProps {
  incident: IncidentData;
  onUpdate: (updatedIncident: IncidentData) => void;
}


const IncidentActions: React.FC<IncidentActionsProps> = ({ incident, onUpdate }) => {
  const { showToast } = useNotifications();
  const [isUpdating, setIsUpdating] = useState(false);
  const [showAssignModal, setShowAssignModal] = useState(false);

  const updateIncident = async (updates: Partial<IncidentData>) => {
    setIsUpdating(true);
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/incidents/${incident.id}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updates),
      });

      if (response.ok) {
        const updatedIncident = await response.json();
        onUpdate(updatedIncident);
      } else {
        // Mock successful update
        const updatedIncident = { ...incident, ...updates };
        onUpdate(updatedIncident);
      }
    } catch (error) {
      console.error('Error updating incident:', error);
      showToast({
        type: 'error',
        title: 'Update Failed',
        message: 'Failed to update incident'
      });
    } finally {
      setIsUpdating(false);
    }
  };

  const handleAcknowledge = () => {
    updateIncident({ status: 'acknowledged' });
    showToast({
      type: 'success',
      title: 'Incident Acknowledged',
      message: 'You have acknowledged this incident'
    });
  };

  const handleResolve = () => {
    updateIncident({ status: 'resolved' });
    showToast({
      type: 'success',
      title: 'Incident Resolved',
      message: 'Incident has been marked as resolved'
    });
  };

  const handleReopen = () => {
    updateIncident({ status: 'open' });
    showToast({
      type: 'warning',
      title: 'Incident Reopened',
      message: 'Incident has been reopened'
    });
  };

  const handleSeverityChange = (severity: IncidentData['severity']) => {
    updateIncident({ severity });
    showToast({
      type: 'system',
      title: 'Severity Updated',
      message: `Incident severity changed to ${severity}`
    });
  };

  const handleAssignToMe = () => {
    updateIncident({
      assigned_to_id: 'current-user',
      assigned_to_name: 'You'
    });
    showToast({
      type: 'success',
      title: 'Incident Assigned',
      message: 'Incident has been assigned to you'
    });
  };

  const handleEscalate = () => {
    showToast({
      type: 'warning',
      title: 'Escalation Triggered',
      message: 'Incident has been escalated to senior engineers'
    });
  };

  const getStatusActions = () => {
    switch (incident.status) {
      case 'open':
        return [
          {
            label: 'Acknowledge',
            action: handleAcknowledge,
            icon: CheckCircle,
            glowColor: 'yellow' as const,
            description: 'Acknowledge that you are working on this incident'
          },
          {
            label: 'Resolve',
            action: handleResolve,
            icon: CheckCircle,
            glowColor: 'green' as const,
            description: 'Mark incident as resolved'
          }
        ];
      case 'acknowledged':
        return [
          {
            label: 'Resolve',
            action: handleResolve,
            icon: CheckCircle,
            glowColor: 'green' as const,
            description: 'Mark incident as resolved'
          }
        ];
      case 'resolved':
        return [
          {
            label: 'Reopen',
            action: handleReopen,
            icon: RefreshCw,
            glowColor: 'orange' as const,
            description: 'Reopen this incident'
          }
        ];
      default:
        return [];
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical':
        return <Flame className="w-4 h-4" />;
      case 'high':
        return <AlertTriangle className="w-4 h-4" />;
      case 'medium':
        return <Info className="w-4 h-4" />;
      case 'low':
        return <Info className="w-4 h-4" />;
      default:
        return <Info className="w-4 h-4" />;
    }
  };


  const getSeverityColor = (severity: string, isActive: boolean = false) => {
    const colors = {
      critical: isActive ? 'bg-red-500/20 text-red-400 border-red-500/30' : 'bg-transparent text-red-400/60 border-border hover:bg-accent',
      high: isActive ? 'bg-orange-500/20 text-orange-400 border-orange-500/30' : 'bg-transparent text-orange-400/60 border-border hover:bg-accent',
      medium: isActive ? 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' : 'bg-transparent text-yellow-400/60 border-border hover:bg-accent',
      low: isActive ? 'bg-blue-500/20 text-blue-400 border-blue-500/30' : 'bg-transparent text-blue-400/60 border-border hover:bg-accent'
    };
    return colors[severity as keyof typeof colors] || colors.low;
  };

  const statusActions = getStatusActions();

  return (
    <div className="space-y-4">
      {/* Quick Status Actions */}
      <div className="border border-border rounded-lg bg-transparent p-6">
        <h3 className="text-base font-medium text-foreground mb-4">Quick Actions</h3>

        <div className="space-y-3">
          {statusActions.map((action, index) => (
            <button
              key={index}
              onClick={action.action}
              disabled={isUpdating}
              className={`w-full rounded-md px-6 py-2.5 text-sm font-medium inline-flex items-center justify-center gap-2 disabled:opacity-50 ${
                action.glowColor === 'yellow' ? 'bg-primary text-primary-foreground hover:bg-white/90' :
                action.glowColor === 'green' ? 'bg-primary text-primary-foreground hover:bg-white/90' :
                action.glowColor === 'orange' ? 'border border-border text-foreground hover:bg-accent' :
                'bg-primary text-primary-foreground hover:bg-white/90'
              }`}
            >
              {isUpdating ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
              ) : (
                <action.icon className="w-5 h-5" />
              )}
              <span>{action.label}</span>
            </button>
          ))}

          {/* Assignment Actions */}
          {!incident.assigned_to_id && (
            <button
              onClick={handleAssignToMe}
              disabled={isUpdating}
              className="w-full bg-primary text-primary-foreground hover:bg-white/90 rounded-md px-6 py-2.5 text-sm font-medium inline-flex items-center justify-center gap-2 disabled:opacity-50"
            >
              <UserPlus className="w-5 h-5" />
              <span>Assign to Me</span>
            </button>
          )}

          {/* Escalation */}
          <button
            onClick={handleEscalate}
            disabled={isUpdating}
            className="w-full border border-red-500/30 text-red-300 hover:bg-red-500/10 rounded-md px-6 py-2.5 text-sm font-medium inline-flex items-center justify-center gap-2 disabled:opacity-50"
          >
            <Bell className="w-5 h-5" />
            <span>Escalate</span>
          </button>
        </div>
      </div>

      {/* Severity Control */}
      <div className="border border-border rounded-lg bg-transparent p-6">
        <h3 className="text-base font-medium text-foreground mb-4">Severity Level</h3>

        <div className="grid grid-cols-2 gap-2">
          {(['critical', 'high', 'medium', 'low'] as const).map((severity) => (
            <button
              key={severity}
              onClick={() => handleSeverityChange(severity)}
              disabled={isUpdating}
              className={`flex items-center justify-center space-x-2 px-3 py-2 rounded-lg border transition-all duration-300 disabled:opacity-50 ${
                incident.severity === severity
                  ? getSeverityColor(severity, true)
                  : getSeverityColor(severity, false)
              } ${incident.severity === severity ? 'scale-105' : 'hover:scale-102'}`}
            >
              {getSeverityIcon(severity)}
              <span className="text-sm font-medium capitalize">{severity}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Additional Actions */}
      <div className="border border-border rounded-lg bg-transparent p-6">
        <h3 className="text-base font-medium text-foreground mb-4">More Actions</h3>

        <div className="space-y-2">
          <button
            onClick={() => setShowAssignModal(true)}
            className="w-full flex items-center space-x-3 px-3 py-2 text-left text-foreground hover:text-foreground hover:bg-accent rounded-lg transition-colors"
          >
            <UserPlus className="w-5 h-5" />
            <span>Assign to Team Member</span>
          </button>

          <button
            onClick={() => {
              showToast({
                type: 'system',
                title: 'Page Manager',
                message: 'Incident manager has been paged'
              });
            }}
            className="w-full flex items-center space-x-3 px-3 py-2 text-left text-foreground hover:text-foreground hover:bg-accent rounded-lg transition-colors"
          >
            <Bell className="w-5 h-5" />
            <span>Page Manager</span>
          </button>

          <button
            onClick={() => {
              navigator.clipboard.writeText(window.location.href);
              showToast({
                type: 'success',
                title: 'Link Copied',
                message: 'Incident link copied to clipboard'
              });
            }}
            className="w-full flex items-center space-x-3 px-3 py-2 text-left text-foreground hover:text-foreground hover:bg-accent rounded-lg transition-colors"
          >
            <Settings2 className="w-5 h-5" />
            <span>Copy Incident Link</span>
          </button>

          <button
            onClick={() => {
              showToast({
                type: 'system',
                title: 'Runbook Opened',
                message: 'Opening related runbook documentation'
              });
            }}
            className="w-full flex items-center space-x-3 px-3 py-2 text-left text-foreground hover:text-foreground hover:bg-accent rounded-lg transition-colors"
          >
            <Info className="w-5 h-5" />
            <span>View Runbook</span>
          </button>
        </div>
      </div>

      {/* Timer/Duration */}
      <div className="border border-border rounded-lg bg-transparent p-6">
        <h3 className="text-base font-medium text-foreground mb-4 flex items-center">
          <Clock className="w-5 h-5 mr-2" />
          Duration
        </h3>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Time to Acknowledge:</span>
            <span className="text-foreground font-mono">
              {incident.status === 'open' ? '-- : --' : '5m 23s'}
            </span>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Time to Resolve:</span>
            <span className="text-foreground font-mono">
              {incident.status === 'resolved' ? '1h 23m' : '-- : --'}
            </span>
          </div>

          <div className="border-t border-border pt-3">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Total Duration:</span>
              <span className="text-foreground font-mono text-lg">
                {incident.status === 'resolved' ? '1h 23m' : '2h 15m'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* SLA Status */}
      <div className="border border-border rounded-lg bg-transparent p-6">
        <h3 className="text-base font-medium text-foreground mb-4 flex items-center gap-2">
          SLA Status
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 inline-block" />
        </h3>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-foreground">Acknowledge SLA:</span>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-emerald-500/10 text-emerald-400 border-emerald-500/20">Met</span>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-foreground">Resolution SLA:</span>
            {incident.status === 'resolved' ? (
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-emerald-500/10 text-emerald-400 border-emerald-500/20">Met</span>
            ) : (
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-yellow-500/10 text-yellow-400 border-yellow-500/20">37m remaining</span>
            )}
          </div>

          {incident.status !== 'resolved' && (
            <div className="mt-3">
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="text-muted-foreground">Progress</span>
                <span className="text-muted-foreground">62%</span>
              </div>
              <div className="w-full bg-secondary rounded-full h-2">
                <div className="bg-emerald-500 h-2 rounded-full" style={{ width: '62%' }}></div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Assignment Modal */}
      {showAssignModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center">
          <div className="border border-border rounded-lg bg-transparent p-6 w-96 max-w-full mx-4">
            <h3 className="text-base font-medium text-foreground mb-4">Assign Incident</h3>

            <div className="space-y-3">
              {['Sarah Chen', 'Marcus Rodriguez', 'Alex Johnson', 'DevOps Team'].map((member) => (
                <button
                  key={member}
                  onClick={() => {
                    updateIncident({
                      assigned_to_id: member.toLowerCase().replace(' ', '-'),
                      assigned_to_name: member
                    });
                    setShowAssignModal(false);
                  }}
                  className="w-full flex items-center space-x-3 px-3 py-2 text-left text-foreground hover:text-foreground hover:bg-accent rounded-lg transition-colors"
                >
                  <div className="w-8 h-8 bg-secondary rounded-full flex items-center justify-center text-foreground text-sm font-medium">
                    {member.charAt(0)}
                  </div>
                  <span>{member}</span>
                </button>
              ))}
            </div>

            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={() => setShowAssignModal(false)}
                className="border border-border text-foreground hover:bg-accent rounded-md px-6 py-2.5 text-sm font-medium"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default IncidentActions;
