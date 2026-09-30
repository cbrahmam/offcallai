// APIKeyModal.tsx - Standalone modal for API key management
// Isolated from parent re-renders to prevent key display issues
import React, { useState, useEffect, useCallback } from 'react';
import {
  ClipboardCopy,
  Terminal
} from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';

import { API_URL as API_BASE_URL } from '../config/api';

interface AgentAPIKey {
  id: string;
  name: string;
  key_prefix: string;
  created_at: string;
  last_used_at: string | null;
  is_active: boolean;
}

interface APIKeyModalProps {
  isOpen: boolean;
  onClose: () => void;
  onKeyCreated?: () => void;
}

const APIKeyModal: React.FC<APIKeyModalProps> = ({ isOpen, onClose, onKeyCreated }) => {
  const [apiKeys, setApiKeys] = useState<AgentAPIKey[]>([]);
  const [newKeyName, setNewKeyName] = useState('');
  const [generatedKey, setGeneratedKey] = useState<string | null>(null);
  const [isCreatingKey, setIsCreatingKey] = useState(false);
  const [copied, setCopied] = useState(false);

  const authenticatedFetch = useCallback(async (url: string, options: RequestInit = {}) => {
    const token = localStorage.getItem('access_token');
    if (!token) throw new Error('No access token');

    return fetch(url, {
      ...options,
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });
  }, []);

  const loadAPIKeys = useCallback(async () => {
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/hosts/api-keys`);
      if (response.ok) {
        const data = await response.json();
        setApiKeys(data.keys || data.api_keys || []);
      }
    } catch (error) {
      console.error('Error loading API keys:', error);
    }
  }, [authenticatedFetch]);

  useEffect(() => {
    if (isOpen) {
      loadAPIKeys();
    }
  }, [isOpen, loadAPIKeys]);

  const createAPIKey = async () => {
    if (!newKeyName.trim()) {
      alert('Please enter a name for the API key');
      return;
    }

    setIsCreatingKey(true);
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/hosts/api-keys`, {
        method: 'POST',
        body: JSON.stringify({ name: newKeyName }),
      });

      if (response.ok) {
        const data = await response.json();
        setGeneratedKey(data.api_key);
        setNewKeyName('');
        setCopied(false);
        onKeyCreated?.();
      } else {
        const errorData = await response.json().catch(() => ({}));
        alert(errorData.detail || 'Failed to create API key');
      }
    } catch (error) {
      console.error('Error creating API key:', error);
      alert('Failed to create API key');
    } finally {
      setIsCreatingKey(false);
    }
  };

  const revokeAPIKey = async (keyId: string) => {
    if (!window.confirm('Are you sure you want to revoke this API key?')) return;

    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/hosts/api-keys/${keyId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        loadAPIKeys();
      }
    } catch (error) {
      console.error('Error revoking API key:', error);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
  };

  const handleClose = () => {
    if (generatedKey) {
      loadAPIKeys();
    }
    setGeneratedKey(null);
    setNewKeyName('');
    setCopied(false);
    onClose();
  };

  const handleCreateAnother = () => {
    loadAPIKeys();
    setGeneratedKey(null);
    setCopied(false);
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-secondary">
              <Terminal className="w-4 h-4 text-foreground" />
            </div>
            Manage API Keys
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Show generated key */}
          {generatedKey ? (
            <div className="bg-transparent border border-emerald-500/20 rounded-xl p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400">
                  {copied ? 'Copied!' : 'API Key Generated - Copy Now!'}
                </span>
                <button
                  onClick={() => copyToClipboard(generatedKey)}
                  className="h-7 px-2 text-xs border border-border text-foreground rounded-lg hover:bg-accent transition-colors inline-flex items-center gap-1"
                >
                  <ClipboardCopy className="w-4 h-4" />
                  {copied ? 'Copied' : 'Copy'}
                </button>
              </div>
              <code className="block text-xs text-emerald-400 font-mono break-all select-all p-2 bg-secondary/30 border border-border rounded">
                {generatedKey}
              </code>
              <p className="text-xs text-yellow-400 mt-2 font-medium">
                Save this key now - it won't be shown again!
              </p>
              <button
                onClick={handleCreateAnother}
                className="mt-3 w-full px-4 py-2 border border-border text-foreground rounded-lg hover:bg-accent transition-colors text-sm"
              >
                I've Copied It - Create Another Key
              </button>
            </div>
          ) : (
            <div className="flex gap-2">
              <Input
                placeholder="New key name..."
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                className="flex-1"
                onKeyDown={(e) => e.key === 'Enter' && createAPIKey()}
              />
              <button
                onClick={createAPIKey}
                disabled={isCreatingKey}
                className="px-4 py-2 bg-primary text-primary-foreground font-medium rounded-lg hover:bg-white/90 transition-colors disabled:opacity-50 text-sm"
              >
                {isCreatingKey ? 'Creating...' : 'Create'}
              </button>
            </div>
          )}

          {/* Existing keys */}
          {!generatedKey && (
            <div className="space-y-2">
              {apiKeys.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No API keys yet. Create one to start installing agents.
                </p>
              ) : (
                apiKeys.map((key) => (
                  <div key={key.id} className="bg-transparent border border-border rounded-xl p-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-foreground">{key.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {key.key_prefix}... · Created {new Date(key.created_at).toLocaleDateString()}
                        </p>
                      </div>
                      <button
                        onClick={() => revokeAPIKey(key.id)}
                        className="px-3 py-1.5 bg-red-500/10 text-red-400 border border-red-500/20 rounded-lg hover:bg-red-500/20 transition-colors text-xs"
                      >
                        Revoke
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          <button
            onClick={handleClose}
            className="px-4 py-2 border border-border text-foreground rounded-lg hover:bg-accent transition-colors text-sm"
          >
            Close
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default APIKeyModal;
