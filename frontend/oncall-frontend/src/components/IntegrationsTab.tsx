// frontend/oncall-frontend/src/components/IntegrationsTab.tsx
import React, { useState, useEffect } from 'react';
import {
  ArrowRight,
  CheckCircle,
  Link,
  MessageCircle,
  Plus,
  Trash2,
  X,
  Zap
} from 'lucide-react';
import { Button } from './ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';

import { API_URL as API_BASE_URL } from '../config/api';

interface Integration {
  id: string;
  name: string;
  type: string;
  is_active: boolean;
  config: any;
  created_at: string;
  last_sync_at?: string;
  webhook_url?: string;
  icon?: string;
}

interface Tool {
  name: string;
  icon: string;
  description: string;
  webhookPath: string;
  docs: string;
  instructions: string[];
}

interface ToolsMap {
  [key: string]: Tool;
}

const IntegrationsTab: React.FC = () => {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [loading, setLoading] = useState(true);
  const [showWizard, setShowWizard] = useState(false);

  const availableTools: ToolsMap = {
    slack: {
      name: 'Slack',
      icon: '/icons/slack.svg',
      description: 'Get incident notifications in Slack',
      webhookPath: '/slack/oauth/start',
      docs: 'https://api.slack.com/messaging/webhooks',
      instructions: [
        'Click "Connect to Slack" below',
        'Authorize OffCall AI in your workspace',
        'Select the channels for notifications',
        'You\'ll receive instant alerts in Slack'
      ]
    }
  };

  useEffect(() => {
    const url = new URL(window.location.href);
    if (url.searchParams.has('code') || url.searchParams.has('state')) {
      url.searchParams.delete('code');
      url.searchParams.delete('state');
      window.history.replaceState({}, '', url.toString());
    }

    fetchIntegrations();
  }, []);

  const fetchIntegrations = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('access_token');

      const response = await fetch(`${API_BASE_URL}/integrations/`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        }
      });

      if (response.ok) {
        const data = await response.json();
        setIntegrations(data.integrations || []);
      }
    } catch (error) {
      console.error('Error fetching integrations:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteIntegration = async (integrationId: string, integrationName: string) => {
    if (!window.confirm(`Are you sure you want to delete "${integrationName}"? This action cannot be undone.`)) {
      return;
    }

    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/integrations/${integrationId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        }
      });

      if (response.ok) {
        // Remove from local state
        setIntegrations(prev => prev.filter(i => i.id !== integrationId));
      } else {
        const errorText = await response.text();
        alert(`Failed to delete integration: ${errorText}`);
      }
    } catch (error) {
      console.error('Error deleting integration:', error);
      alert('Failed to delete integration. Please try again.');
    }
  };

  if (showWizard) {
    return (
      <IntegrationWizard
        onClose={() => {
          setShowWizard(false);
          fetchIntegrations();
        }}
        availableTools={availableTools}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-base font-medium text-foreground">Integrations</h2>
          <p className="text-muted-foreground mt-1">Connect notifications and install the OffCall Agent</p>
        </div>
      </div>

      {/* Install OffCall Agent Card */}
      <div className="border border-border rounded-lg bg-transparent">
        <div className="p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-lg bg-secondary flex items-center justify-center">
                <Zap className="w-6 h-6 text-muted-foreground" />
              </div>
              <div>
                <h3 className="text-base font-medium text-foreground">Install OffCall Agent</h3>
                <p className="text-muted-foreground">
                  Deploy our lightweight monitoring agent to collect metrics, logs, and traces from your infrastructure
                </p>
              </div>
            </div>
            <Button
              onClick={() => window.location.href = '/infrastructure'}
              className="gap-2"
            >
              Go to Infrastructure
              <ArrowRight className="w-4 h-4" />
            </Button>
          </div>
          <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <CheckCircle className="w-4 h-4 text-green-500" />
              Kubernetes & Docker support
            </div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <CheckCircle className="w-4 h-4 text-green-500" />
              Auto-discovery of services
            </div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <CheckCircle className="w-4 h-4 text-green-500" />
              Real-time alerting
            </div>
          </div>
        </div>
      </div>

      {/* Slack Integration Card */}
      <div className="border border-border rounded-lg bg-transparent">
        <div className="p-6">
          <h3 className="text-sm font-medium text-foreground flex items-center gap-2">
            <Link className="w-4 h-4 text-muted-foreground" />
            Notifications
          </h3>
        </div>
        <div className="p-6 pt-0">
          {loading ? (
            <div className="text-center py-8 text-muted-foreground">Loading integrations...</div>
          ) : (
            <>
              {/* Show connected Slack integrations */}
              {integrations.filter(i => i.type === 'slack').length > 0 ? (
                <div className="space-y-4">
                  {integrations.filter(i => i.type === 'slack').map((integration) => (
                    <div key={integration.id} className="border border-border rounded-lg bg-accent">
                      <div className="p-4">
                        <div className="flex items-start justify-between">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center text-lg">
                              💬
                            </div>
                            <div>
                              <h4 className="font-semibold text-foreground">{integration.name}</h4>
                              <p className="text-sm text-muted-foreground">Slack Notifications</p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${
                              integration.is_active ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-secondary text-muted-foreground border-border'
                            }`}>
                              {integration.is_active ? (
                                <span className="flex items-center gap-1">
                                  <CheckCircle className="w-3 h-3" />
                                  Connected
                                </span>
                              ) : 'Inactive'}
                            </span>
                            <button
                              onClick={() => handleDeleteIntegration(integration.id, integration.name)}
                              className="p-1.5 rounded-md hover:bg-red-500/10 text-muted-foreground hover:text-red-400 transition-colors"
                              title="Disconnect Slack"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8">
                  <div className="w-16 h-16 rounded-xl bg-purple-500/20 flex items-center justify-center text-3xl mx-auto mb-4">
                    💬
                  </div>
                  <h3 className="font-semibold text-foreground mb-2">Connect Slack</h3>
                  <p className="text-muted-foreground mb-4 max-w-md mx-auto">
                    Get real-time incident notifications delivered directly to your Slack channels
                  </p>
                  <Button onClick={() => setShowWizard(true)} className="gap-2">
                    <Plus className="w-4 h-4" />
                    Connect Slack
                  </Button>
                </div>
              )}
            </>
          )}
        </div>
      </div>

    </div>
  );
};

interface IntegrationWizardProps {
  onClose: () => void;
  availableTools: ToolsMap;
}

const IntegrationWizard: React.FC<IntegrationWizardProps> = ({ onClose, availableTools }) => {
  const slackTool = availableTools['slack'];

  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent className="max-w-lg">
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute right-4 top-4 p-2 rounded-full hover:bg-secondary transition-colors z-10"
          aria-label="Close"
        >
          <X className="w-5 h-5 text-muted-foreground hover:text-foreground" />
        </button>
        <DialogHeader>
          <div className="flex items-center space-x-3">
            <div className="w-12 h-12 rounded-xl bg-purple-500/20 flex items-center justify-center text-2xl">
              💬
            </div>
            <div>
              <DialogTitle className="text-xl">Connect Slack</DialogTitle>
              <p className="text-muted-foreground text-sm">Get real-time incident notifications</p>
            </div>
          </div>
        </DialogHeader>

        <div className="py-4 space-y-6">
          <div className="border border-border rounded-lg bg-accent">
            <div className="p-6">
              <div className="space-y-3 mb-6">
                {slackTool.instructions.map((instruction, idx) => (
                  <div key={idx} className="flex items-start gap-3">
                    <span className="flex-shrink-0 w-6 h-6 rounded-full bg-purple-500 text-foreground text-sm flex items-center justify-center">
                      {idx + 1}
                    </span>
                    <p className="text-muted-foreground">{instruction}</p>
                  </div>
                ))}
              </div>

              <Button
                onClick={async () => {
                  try {
                    const token = localStorage.getItem('access_token');
                    const response = await fetch(`${API_BASE_URL}/slack/oauth/start`, {
                      method: 'POST',
                      headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                      }
                    });

                    if (response.ok) {
                      const data = await response.json();
                      window.location.href = data.authorization_url;
                    } else {
                      alert('Failed to start Slack OAuth');
                    }
                  } catch (error) {
                    console.error('Slack OAuth error:', error);
                    alert('Failed to connect to Slack');
                  }
                }}
                className="w-full bg-primary text-primary-foreground hover:bg-white/90"
              >
                Connect to Slack
              </Button>
            </div>
          </div>

          <div className="text-center">
            <a
              href={slackTool.docs}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              Learn more about Slack webhooks
            </a>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default IntegrationsTab;
