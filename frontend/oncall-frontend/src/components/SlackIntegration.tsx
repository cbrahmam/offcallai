// frontend/oncall-frontend/src/components/SlackIntegration.tsx

import React, { useState, useEffect } from 'react';
import {
  CheckCircle,
  RefreshCw,
  XCircle
} from 'lucide-react';
import { API_URL } from '../config/api';

interface SlackStatus {
  connected: boolean;
  workspace_name?: string;
  bot_user_id?: string;
  team_id?: string;
}

const SlackIntegration: React.FC = () => {
  const [status, setStatus] = useState<SlackStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testChannel, setTestChannel] = useState('#general');
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  useEffect(() => {
    checkStatus();
  }, []);

  const checkStatus = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_URL}/slack/status`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setStatus(data);
      } else {
        setStatus({ connected: false });
      }
    } catch (error) {
      console.error('Failed to check Slack status:', error);
      setStatus({ connected: false });
    } finally {
      setLoading(false);
    }
  };

  const connectSlack = async () => {
    setConnecting(true);
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_URL}/slack/oauth/start`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        // Redirect to Slack OAuth
        window.location.href = data.authorization_url;
      } else {
        alert('Failed to start Slack connection');
      }
    } catch (error) {
      console.error('Failed to connect Slack:', error);
      alert('Failed to connect Slack');
    } finally {
      setConnecting(false);
    }
  };

  const disconnectSlack = async () => {
    if (!confirm('Are you sure you want to disconnect Slack? You will stop receiving notifications.')) {
      return;
    }

    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_URL}/slack/disconnect`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        setStatus({ connected: false });
        alert('Slack disconnected successfully');
      } else {
        alert('Failed to disconnect Slack');
      }
    } catch (error) {
      console.error('Failed to disconnect Slack:', error);
      alert('Failed to disconnect Slack');
    }
  };

  const sendTestMessage = async () => {
    setTesting(true);
    setTestResult(null);

    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_URL}/slack/test`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          channel: testChannel,
          message: `🚨 Test notification from OffCall AI - ${new Date().toLocaleString()}`
        })
      });

      const data = await response.json();

      if (response.ok && data.success) {
        setTestResult({
          success: true,
          message: `Test message sent to ${testChannel}`
        });
      } else {
        setTestResult({
          success: false,
          message: data.error || 'Failed to send test message'
        });
      }
    } catch (error) {
      console.error('Failed to send test message:', error);
      setTestResult({
        success: false,
        message: 'Network error - failed to send test message'
      });
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-transparent border border-border rounded-xl">
        <div className="p-6">
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="w-6 h-6 text-muted-foreground animate-spin" />
            <span className="ml-2 text-muted-foreground text-sm">Loading Slack status...</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-transparent border border-border rounded-xl">
      <div className="p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-3">
            <div className="w-12 h-12 bg-secondary rounded-lg flex items-center justify-center">
              <svg className="w-7 h-7 text-foreground" fill="currentColor" viewBox="0 0 24 24">
                <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z"/>
              </svg>
            </div>
            <div>
              <h3 className="text-base font-medium text-foreground">Slack Integration</h3>
              <p className="text-sm text-muted-foreground">
                Get incident notifications in Slack
              </p>
            </div>
          </div>

          {/* Status Badge */}
          {status?.connected ? (
            <span className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
              Connected
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-secondary text-muted-foreground">
              <XCircle className="w-4 h-4" />
              Not Connected
            </span>
          )}
        </div>

        {/* Connection Info or Connect Button */}
        {status?.connected ? (
          <>
            {/* Connected Info */}
            <div className="bg-transparent border border-border rounded-xl mb-4">
              <div className="p-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs uppercase tracking-wider text-muted-foreground mb-1">Workspace</p>
                    <p className="text-base font-medium text-foreground">{status.workspace_name || 'Unknown'}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wider text-muted-foreground mb-1">Bot User ID</p>
                    <p className="text-foreground font-mono text-sm">{status.bot_user_id || 'Unknown'}</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Test Message Section */}
            <div className="bg-transparent border border-border rounded-xl mb-4">
              <div className="p-4">
                <h4 className="text-base font-medium text-foreground mb-3">Send Test Message</h4>
                <div className="flex items-center space-x-2">
                  <input
                    type="text"
                    value={testChannel}
                    onChange={(e) => setTestChannel(e.target.value)}
                    placeholder="#channel-name"
                    className="flex-1 px-3 py-2 bg-transparent border border-border rounded-lg text-foreground placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30 text-sm"
                  />
                  <button
                    onClick={sendTestMessage}
                    disabled={testing}
                    className="px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-lg hover:bg-white/90 transition-colors disabled:opacity-50"
                  >
                    {testing ? 'Sending...' : 'Send Test'}
                  </button>
                </div>

                {testResult && (
                  <div className={`mt-3 text-sm px-3 py-2 rounded-lg ${
                    testResult.success
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : 'bg-red-500/10 text-red-400 border border-red-500/20'
                  }`}>
                    {testResult.message}
                  </div>
                )}
              </div>
            </div>

            {/* Features List */}
            <div className="mb-4">
              <h4 className="text-base font-medium text-foreground mb-3">What you'll receive:</h4>
              <ul className="space-y-2 text-sm text-foreground">
                <li className="flex items-center space-x-2">
                  <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                  <span>Real-time incident notifications</span>
                </li>
                <li className="flex items-center space-x-2">
                  <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                  <span>Interactive buttons (Acknowledge, Resolve)</span>
                </li>
                <li className="flex items-center space-x-2">
                  <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                  <span>Status updates and comments</span>
                </li>
                <li className="flex items-center space-x-2">
                  <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                  <span>Escalation alerts</span>
                </li>
              </ul>
            </div>

            {/* Disconnect Button */}
            <button
              onClick={disconnectSlack}
              className="w-full px-4 py-2 border border-red-500/20 text-red-400 rounded-lg hover:bg-red-500/10 transition-colors text-sm"
            >
              Disconnect Slack
            </button>
          </>
        ) : (
          <>
            {/* Not Connected - Show Features */}
            <div className="mb-6">
              <h4 className="text-base font-medium text-foreground mb-3">Connect Slack to:</h4>
              <ul className="space-y-2 text-sm text-foreground">
                <li className="flex items-center space-x-2">
                  <CheckCircle className="w-4 h-4 text-blue-400 flex-shrink-0" />
                  <span>Get notified of critical incidents instantly</span>
                </li>
                <li className="flex items-center space-x-2">
                  <CheckCircle className="w-4 h-4 text-blue-400 flex-shrink-0" />
                  <span>Acknowledge and resolve incidents from Slack</span>
                </li>
                <li className="flex items-center space-x-2">
                  <CheckCircle className="w-4 h-4 text-blue-400 flex-shrink-0" />
                  <span>Keep your team in the loop automatically</span>
                </li>
                <li className="flex items-center space-x-2">
                  <CheckCircle className="w-4 h-4 text-blue-400 flex-shrink-0" />
                  <span>No more context switching during incidents</span>
                </li>
              </ul>
            </div>

            {/* Connect Button */}
            <button
              onClick={connectSlack}
              disabled={connecting}
              className="w-full px-6 py-3 bg-primary text-primary-foreground font-medium rounded-lg hover:bg-white/90 transition-colors disabled:opacity-50 text-sm"
            >
              {connecting ? (
                <span className="flex items-center justify-center">
                  <RefreshCw className="w-5 h-5 animate-spin mr-2" />
                  Connecting...
                </span>
              ) : (
                <span className="flex items-center justify-center">
                  <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z"/>
                  </svg>
                  Connect to Slack
                </span>
              )}
            </button>

            <p className="mt-3 text-xs text-muted-foreground text-center">
              You'll be redirected to Slack to authorize the connection
            </p>
          </>
        )}
      </div>
    </div>
  );
};

export default SlackIntegration;
