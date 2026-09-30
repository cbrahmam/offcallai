// REBUILD FORCED v3.0
import React, { useState, useEffect } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  Eye,
  EyeOff,
  Key,
  Plus,
  Trash2
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useNotifications } from '../contexts/NotificationContext';
import { API_URL } from '../config/api';

interface APIKey {
  id: string;
  provider: string;
  key_name: string;
  is_valid: boolean;
  last_validated: string | null;
  validation_error: string | null;
  total_requests: number;
  total_tokens: number;
  last_used: string | null;
  created_at: string;
}

interface APIKeyManagementProps {
  onNavigateBack?: () => void;
}

const APIKeyManagement: React.FC<APIKeyManagementProps> = ({ onNavigateBack }) => {
  const { user } = useAuth();
  const { showToast } = useNotifications();
  // Sentry-compatible DSN for this deployment; the key is filled in by the user.
  const sentryHost = API_URL.replace(/^https?:\/\//, '').replace(/\/api\/v1\/?$/, '');
  const sentryDsn = (orgId: string) => `https://YOUR_API_KEY@${sentryHost}/api/sentry/${orgId}`;

  const [apiKeys, setApiKeys] = useState<APIKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);

  useEffect(() => {
    loadAPIKeys();
  }, []);

  const loadAPIKeys = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_URL}/api_keys/`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        setApiKeys(data);
      }
    } catch (error) {
      console.error('Failed to load API keys:', error);
      showToast({
        type: 'error',
        title: 'Error',
        message: 'Failed to load API keys',
        autoClose: true,
      });
    } finally {
      setLoading(false);
    }
  };

  const deleteAPIKey = async (keyId: string) => {
    if (!window.confirm('Are you sure you want to delete this API key?')) {
      return;
    }

    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_URL}/api_keys/${keyId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        setApiKeys(prev => prev.filter(key => key.id !== keyId));
        showToast({
          type: 'success',
          title: 'API Key Deleted',
          message: 'API key has been removed successfully',
          autoClose: true,
        });
      }
    } catch (error) {
      console.error('Failed to delete API key:', error);
      showToast({
        type: 'error',
        title: 'Error',
        message: 'Failed to delete API key',
        autoClose: true,
      });
    }
  };

  const parseValidationError = (errorMessage: string | null): string => {
    if (!errorMessage) return 'Unknown error';

  // First try to extract JSON from the string
  const jsonMatch = errorMessage.match(/\{.*\}/);
  if (jsonMatch) {
    try {
      const errorObj = JSON.parse(jsonMatch[0]);

      // Handle Claude API error format
      if (errorObj.error && errorObj.error.message) {
        return errorObj.error.message;
      }

      if (errorObj.message) {
        return errorObj.message;
      }

      if (errorObj.detail) {
        return errorObj.detail;
      }
    } catch {
      // If JSON parsing fails, continue to string cleanup
    }
  }

  // Fallback: just return the readable part
  return 'Invalid API key - please check your key and try again';
};

  const validateAPIKey = async (keyId: string) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_URL}/api_keys/${keyId}/validate`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        await loadAPIKeys();

        showToast({
          type: data.is_valid ? 'success' : 'error',
          title: data.is_valid ? 'API Key Valid' : 'API Key Invalid',
          message: data.is_valid
            ? 'API key validated successfully'
            : parseValidationError(data.error_message),
          autoClose: true,
        });
      }
    } catch (error) {
      console.error('Failed to validate API key:', error);
      showToast({
        type: 'error',
        title: 'Validation Error',
        message: 'Failed to validate API key',
        autoClose: true,
      });
    }
  };

  const getProviderIcon = (provider: string) => {
    switch (provider.toLowerCase()) {
      case 'openai': return '🤖';
      case 'claude': return '🧠';
      case 'gemini': return '💎';
      default: return '🔑';
    }
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-zinc-400"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="p-2 rounded-xl bg-secondary">
                <Key className="w-7 h-7 text-foreground" />
              </div>
              <div>
                <h1 className="text-base font-medium text-foreground mb-1">API Keys</h1>
                <p className="text-sm text-muted-foreground">
                  Manage your AI provider API keys for incident analysis
                </p>
              </div>
            </div>
            <button
              onClick={() => setShowAddModal(true)}
              className="px-4 py-2 bg-primary text-primary-foreground font-medium rounded-lg hover:bg-white/90 transition-colors text-sm inline-flex items-center gap-2"
            >
              <Plus className="w-5 h-5" />
              <span>Add API Key</span>
            </button>
          </div>
        </div>

        {apiKeys.length === 0 ? (
          <div className="bg-transparent border border-border rounded-xl p-16 text-center">
            <div className="p-3 rounded-xl bg-secondary w-fit mx-auto mb-4">
              <Key className="w-10 h-10 text-foreground" />
            </div>
            <h3 className="text-base font-medium text-foreground mb-2">No API Keys</h3>
            <p className="text-sm text-muted-foreground mb-6">
              Add your AI provider API keys to enable intelligent incident analysis.
            </p>
            <button
              onClick={() => setShowAddModal(true)}
              className="px-4 py-2 bg-primary text-primary-foreground font-medium rounded-lg hover:bg-white/90 transition-colors text-sm inline-flex items-center gap-2"
            >
              <Plus className="w-5 h-5" />
              Add Your First API Key
            </button>
          </div>
        ) : (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {apiKeys.map((apiKey) => (
              <div
                key={apiKey.id}
                className={`bg-card border rounded-xl p-5 ${
                  apiKey.is_valid ? 'border-border' : 'border-red-500/30'
                }`}
              >
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center space-x-3">
                    <span className="text-3xl">{getProviderIcon(apiKey.provider)}</span>
                    <div>
                      <h3 className="text-base font-medium text-foreground">{apiKey.key_name}</h3>
                      <p className="text-sm text-muted-foreground capitalize">{apiKey.provider}</p>
                    </div>
                  </div>

                  {apiKey.is_valid ? (
                    <CheckCircle className="w-6 h-6 text-emerald-400 flex-shrink-0" />
                  ) : (
                    <AlertTriangle className="w-6 h-6 text-red-400 flex-shrink-0" />
                  )}
                </div>

                <div className="mb-4">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    apiKey.is_valid
                      ? 'bg-emerald-500/10 text-emerald-400'
                      : 'bg-red-500/10 text-red-400'
                  }`}>
                    {apiKey.is_valid ? 'Valid' : 'Invalid'}
                  </span>

                  {/* FIXED: Better error display */}
                  {!apiKey.is_valid && apiKey.validation_error && (
                    <div className="mt-3 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
                      <p className="text-sm text-red-400 font-medium mb-1">Validation Error:</p>
                      <p className="text-xs text-red-400/80 leading-relaxed">
                        {parseValidationError(apiKey.validation_error)}
                      </p>
                    </div>
                  )}
                </div>

                <div className="space-y-2 mb-4 text-sm">
                  <div className="flex justify-between text-muted-foreground">
                    <span>Total Requests:</span>
                    <span className="text-foreground font-medium">{apiKey.total_requests.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between text-muted-foreground">
                    <span>Total Tokens:</span>
                    <span className="text-foreground font-medium">{apiKey.total_tokens.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between text-muted-foreground">
                    <span>Last Used:</span>
                    <span className="text-foreground font-medium">{formatDate(apiKey.last_used)}</span>
                  </div>
                  <div className="flex justify-between text-muted-foreground">
                    <span>Added:</span>
                    <span className="text-foreground font-medium">{formatDate(apiKey.created_at)}</span>
                  </div>
                </div>

                <div className="flex space-x-2">
                  <button
                    onClick={() => validateAPIKey(apiKey.id)}
                    className="flex-1 px-4 py-2 border border-border text-foreground rounded-lg hover:bg-accent transition-colors text-sm"
                  >
                    Validate
                  </button>
                  <button
                    onClick={() => deleteAPIKey(apiKey.id)}
                    className="px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 rounded-lg transition-colors"
                    title="Delete API Key"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Sentry SDK Compatibility Section */}
        <div className="mt-12 border-t border-border pt-8">
          <div className="mb-6">
            <h2 className="text-base font-medium text-foreground mb-2">Sentry SDK Compatibility</h2>
            <p className="text-sm text-muted-foreground">
              Use your existing Sentry SDK with OffCall AI - just change the DSN URL.
            </p>
          </div>

          <div className="bg-transparent border border-border rounded-xl p-6">
            <div className="flex items-start space-x-4">
              <div className="p-2 rounded-xl bg-secondary">
                <span className="text-2xl">🔗</span>
              </div>
              <div className="flex-1">
                <h3 className="text-base font-medium text-foreground mb-2">Your Sentry-Compatible DSN</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Use this DSN in your Sentry SDK initialization to send errors to OffCall AI:
                </p>

                <div className="bg-secondary/30 border border-border rounded-lg p-4 mb-4">
                  <code className="text-sm text-foreground break-all">
                    {sentryDsn(user?.organization_id || 'YOUR_ORG_ID')}
                  </code>
                </div>

                <div className="space-y-4">
                  <div>
                    <p className="text-sm font-medium text-foreground mb-2">JavaScript Example:</p>
                    <div className="bg-secondary/30 border border-border rounded-lg p-3">
                      <pre className="text-xs text-emerald-400 whitespace-pre-wrap">{`import * as Sentry from "@sentry/browser";

Sentry.init({
  dsn: "${sentryDsn(user?.organization_id || 'YOUR_ORG_ID')}",
  environment: "production",
});`}</pre>
                    </div>
                  </div>

                  <div>
                    <p className="text-sm font-medium text-foreground mb-2">Python Example:</p>
                    <div className="bg-secondary/30 border border-border rounded-lg p-3">
                      <pre className="text-xs text-emerald-400 whitespace-pre-wrap">{`import sentry_sdk

sentry_sdk.init(
    dsn="${sentryDsn(user?.organization_id || 'YOUR_ORG_ID')}",
    environment="production",
)`}</pre>
                    </div>
                  </div>
                </div>

                <p className="text-xs text-muted-foreground mt-4">
                  Replace YOUR_API_KEY with an Agent API Key from your Infrastructure settings.
                </p>
              </div>
            </div>
          </div>
        </div>

        {showAddModal && (
          <AddAPIKeyModal
            onClose={() => setShowAddModal(false)}
            onSuccess={() => {
              setShowAddModal(false);
              loadAPIKeys();
            }}
          />
        )}
      </div>
    </div>
  );
};

// Add API Key Modal Component
interface AddAPIKeyModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

const AddAPIKeyModal: React.FC<AddAPIKeyModalProps> = ({ onClose, onSuccess }) => {
  const { showToast } = useNotifications();
  const [formData, setFormData] = useState({
    provider: 'openai',
    key_name: '',
    api_key: ''
  });
  const [showApiKey, setShowApiKey] = useState(false);
  const [loading, setLoading] = useState(false);

  const providers = [
    { value: 'openai', label: 'OpenAI (GPT-4, GPT-3.5)', icon: '🤖' },
    { value: 'claude', label: 'Anthropic Claude', icon: '🧠' },
    { value: 'gemini', label: 'Google Gemini', icon: '💎' }
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.key_name.trim() || !formData.api_key.trim()) {
      showToast({
        type: 'error',
        title: 'Missing Information',
        message: 'Please fill in all required fields',
        autoClose: true,
      });
      return;
    }

    setLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_URL}/api_keys/`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });

      if (response.ok) {
        const data = await response.json();
        showToast({
          type: data.is_valid ? 'success' : 'warning',
          title: 'API Key Added',
          message: data.is_valid
            ? 'API key added and validated successfully'
            : 'API key added but validation failed. Please check the key.',
          autoClose: true,
        });
        onSuccess();
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to add API key');
      }
    } catch (error) {
      console.error('Failed to add API key:', error);
      showToast({
        type: 'error',
        title: 'Error',
        message: error instanceof Error ? error.message : 'Failed to add API key',
        autoClose: true,
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-background border border-border rounded-xl p-6 w-full max-w-md">
        <h2 className="text-base font-medium text-foreground mb-6">Add API Key</h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-foreground mb-2">
              AI Provider *
            </label>
            <select
              value={formData.provider}
              onChange={(e) => setFormData(prev => ({ ...prev, provider: e.target.value }))}
              className="w-full px-3 py-2 bg-transparent border border-border rounded-lg text-foreground focus:outline-none focus:ring-1 focus:ring-primary/30 text-sm"
            >
              {providers.map(provider => (
                <option key={provider.value} value={provider.value}>
                  {provider.icon} {provider.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-foreground mb-2">
              Key Name *
            </label>
            <input
              type="text"
              value={formData.key_name}
              onChange={(e) => setFormData(prev => ({ ...prev, key_name: e.target.value }))}
              placeholder="e.g., Production OpenAI Key"
              className="w-full px-3 py-2 bg-transparent border border-border rounded-lg text-foreground placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30 text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-foreground mb-2">
              API Key *
            </label>
            <div className="relative">
              <input
                type={showApiKey ? "text" : "password"}
                value={formData.api_key}
                onChange={(e) => setFormData(prev => ({ ...prev, api_key: e.target.value }))}
                placeholder="Enter your API key"
                className="w-full px-3 py-2 pr-10 bg-transparent border border-border rounded-lg text-foreground placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30 text-sm"
              />
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute right-3 top-2 text-muted-foreground hover:text-foreground"
              >
                {showApiKey ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Your API key is encrypted and stored securely. We only use it to make requests on your behalf.
            </p>
            <p className="text-xs text-blue-400 mt-1">
              Don't have an API key? Type <span className="font-mono bg-secondary px-1 rounded">DEMO</span> to try with our demo key (Claude & Gemini only).
            </p>
          </div>

          <div className="flex space-x-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-border text-foreground rounded-lg hover:bg-accent transition-colors text-sm"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 px-4 py-2 bg-primary text-primary-foreground font-medium rounded-lg hover:bg-white/90 transition-colors disabled:opacity-50 text-sm"
            >
              {loading ? 'Adding...' : 'Add Key'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default APIKeyManagement;
