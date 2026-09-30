import React, { useEffect, useState } from 'react';
import { API_URL as API_BASE_URL } from '../config/api';
import {
  CheckCircle,
  ExternalLink,
  Loader2,
  XCircle
} from 'lucide-react';

const SlackCallBack: React.FC = () => {
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('Processing Slack authorization...');
  const [workspaceName, setWorkspaceName] = useState<string>('');

  useEffect(() => {
    const handleCallback = async () => {
      try {
        // Get code and state from URL
        const urlParams = new URLSearchParams(window.location.search);
        const code = urlParams.get('code');
        const state = urlParams.get('state');
        const error = urlParams.get('error');

        // Handle error from Slack
        if (error) {
          setStatus('error');
          setMessage(`Slack authorization failed: ${error}`);
          return;
        }

        if (!code || !state) {
          setStatus('error');
          setMessage('Missing authorization code or state');
          return;
        }

        setMessage('Exchanging authorization code with Slack...');

        // Call backend callback endpoint (NO AUTH TOKEN NEEDED - state validates user)

        const response = await fetch(`${API_BASE_URL}/slack/oauth/callback`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            code,
            state
          })
        });

        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.detail || 'Failed to complete Slack authorization');
        }

        // Success!
        setStatus('success');
        setWorkspaceName(data.workspace_name || 'your workspace');
        setMessage(`Successfully connected to ${data.workspace_name || 'Slack'}!`);

        // Redirect to settings after 2 seconds
        setTimeout(() => {
          window.location.href = '/settings/integrations';
        }, 2000);

      } catch (error) {
        console.error('Slack callback error:', error);
        setStatus('error');
        setMessage(error instanceof Error ? error.message : 'Failed to connect Slack');
      }
    };

    handleCallback();
  }, []);

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      <div className="max-w-md w-full">
        <div className={`bg-transparent border rounded-xl relative ${
          status === 'success' ? 'border-emerald-500/20' :
          status === 'error' ? 'border-red-500/20' :
          'border-border'
        }`}>
          <div className="p-8 text-center">
            {/* Icon */}
            <div className="flex justify-center mb-6">
              {status === 'loading' && (
                <div className="w-16 h-16 bg-secondary rounded-full flex items-center justify-center relative">
                  <Loader2 className="w-8 h-8 text-foreground animate-spin" />
                </div>
              )}
              {status === 'success' && (
                <div className="w-16 h-16 bg-emerald-500/10 border border-emerald-500/20 rounded-full flex items-center justify-center">
                  <CheckCircle className="w-8 h-8 text-emerald-400" />
                </div>
              )}
              {status === 'error' && (
                <div className="w-16 h-16 bg-red-500/10 border border-red-500/20 rounded-full flex items-center justify-center">
                  <XCircle className="w-8 h-8 text-red-400" />
                </div>
              )}
            </div>

            {/* Title */}
            <h2 className="text-base font-medium text-foreground mb-4">
              {status === 'loading' && 'Connecting to Slack...'}
              {status === 'success' && 'Connected!'}
              {status === 'error' && 'Connection Failed'}
            </h2>

            {/* Status Badge */}
            <div className="flex justify-center mb-4">
              <span className={`text-xs px-2.5 py-1 rounded-full ${
                status === 'success' ? 'bg-emerald-500/10 text-emerald-400' :
                status === 'error' ? 'bg-red-500/10 text-red-400' :
                'bg-blue-500/10 text-blue-400'
              }`}>
                {status === 'loading' && 'Processing'}
                {status === 'success' && 'Success'}
                {status === 'error' && 'Failed'}
              </span>
            </div>

            {/* Message */}
            <p className="text-sm text-muted-foreground mb-6">
              {message}
            </p>

            {/* Loading bar */}
            {status === 'loading' && (
              <div className="w-full bg-secondary rounded-full h-2 mb-4">
                <div className="bg-white/20 h-2 rounded-full animate-pulse" style={{ width: '60%' }} />
              </div>
            )}

            {/* Success details */}
            {status === 'success' && workspaceName && (
              <div className="bg-transparent border border-emerald-500/20 rounded-xl mb-4">
                <div className="p-4">
                  <div className="flex items-center justify-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                    <p className="text-emerald-400 text-sm">
                      OffCall AI is now connected to <strong>{workspaceName}</strong>
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Action button */}
            {status === 'error' && (
              <button
                onClick={() => window.location.href = '/settings/integrations'}
                className="px-6 py-2.5 bg-primary text-primary-foreground font-medium rounded-lg hover:bg-white/90 transition-colors text-sm inline-flex items-center"
              >
                Go to Settings
                <ExternalLink className="w-4 h-4 ml-2" />
              </button>
            )}

            {status === 'success' && (
              <p className="text-muted-foreground text-sm">
                Redirecting to settings...
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SlackCallBack;
