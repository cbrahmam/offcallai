// InstallAgentModal.tsx - Standalone modal for agent installation
// Isolated from parent re-renders to prevent key display issues
import React, { useState, useCallback } from 'react';
import {
  ClipboardCopy,
  CloudDownload
} from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';

import { API_URL as API_BASE_URL } from '../config/api';

interface InstallAgentModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const InstallAgentModal: React.FC<InstallAgentModalProps> = ({ isOpen, onClose }) => {
  const [newKeyName, setNewKeyName] = useState('');
  const [generatedKey, setGeneratedKey] = useState<string | null>(null);
  const [isCreatingKey, setIsCreatingKey] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

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
        setCopied(null);
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

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 2000);
  };

  const handleClose = () => {
    // Don't clear the key on close - user might want to come back
    onClose();
  };

  const selfOrigin = API_BASE_URL.replace(/\/api\/v1\/?$/, '');
  const installKey = generatedKey || 'YOUR_API_KEY';
  const installCommand = `curl -fsSL ${selfOrigin}/install.sh | OFFCALL_API_KEY=${installKey} OFFCALL_API_URL=${API_BASE_URL} bash`;

  const dockerCommand = `docker run -d \\
  --name offcall-agent \\
  -e OFFCALL_API_KEY=${generatedKey || 'YOUR_API_KEY'} \\
  -v /var/run/docker.sock:/var/run/docker.sock:ro \\
  offcallai/agent:latest`;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-secondary">
              <CloudDownload className="w-4 h-4 text-foreground" />
            </div>
            Install OffCall Agent
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          {/* Step 1: API Key */}
          <div>
            <h4 className="text-sm font-medium text-foreground mb-3 flex items-center gap-2">
              <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400">Step 1</span>
              Generate API Key
            </h4>
            {generatedKey ? (
              <div className="bg-transparent border border-emerald-500/20 rounded-xl p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400">
                    {copied === 'key' ? 'Copied!' : 'API Key Generated - Copy Now!'}
                  </span>
                  <button
                    onClick={() => copyToClipboard(generatedKey, 'key')}
                    className="h-7 px-2 text-xs border border-border text-foreground rounded-lg hover:bg-accent transition-colors inline-flex items-center gap-1"
                  >
                    <ClipboardCopy className="w-4 h-4" />
                    {copied === 'key' ? 'Copied' : 'Copy'}
                  </button>
                </div>
                <code className="block text-xs text-emerald-400 font-mono break-all select-all p-2 bg-secondary/30 border border-border rounded">
                  {generatedKey}
                </code>
                <p className="text-xs text-yellow-400 mt-2 font-medium">
                  Save this key now - it won't be shown again!
                </p>
              </div>
            ) : (
              <div className="flex gap-2">
                <Input
                  placeholder="Key name (e.g., Production Servers)"
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
                  {isCreatingKey ? 'Creating...' : 'Generate Key'}
                </button>
              </div>
            )}
          </div>

          {/* Step 2: Install */}
          <div>
            <h4 className="text-sm font-medium text-foreground mb-3 flex items-center gap-2">
              <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400">Step 2</span>
              Run Install Command
            </h4>
            <div className="bg-transparent border border-border rounded-xl p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-muted-foreground">One-liner install (Linux/macOS)</span>
                <button
                  onClick={() => copyToClipboard(installCommand, 'install')}
                  className="h-7 px-2 text-xs border border-border text-foreground rounded-lg hover:bg-accent transition-colors inline-flex items-center gap-1"
                >
                  <ClipboardCopy className="w-4 h-4" />
                  {copied === 'install' ? 'Copied' : 'Copy'}
                </button>
              </div>
              <code className="text-sm text-emerald-400 font-mono break-all">{installCommand}</code>
            </div>
          </div>

          {/* Docker */}
          <div>
            <h4 className="text-sm font-medium text-foreground mb-3 flex items-center gap-2">
              <span className="text-xs px-2 py-0.5 rounded-full bg-secondary text-muted-foreground">Alt</span>
              Or use Docker
            </h4>
            <div className="bg-transparent border border-border rounded-xl p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-muted-foreground">Docker run command</span>
                <button
                  onClick={() => copyToClipboard(dockerCommand, 'docker')}
                  className="h-7 px-2 text-xs border border-border text-foreground rounded-lg hover:bg-accent transition-colors inline-flex items-center gap-1"
                >
                  <ClipboardCopy className="w-4 h-4" />
                  {copied === 'docker' ? 'Copied' : 'Copy'}
                </button>
              </div>
              <pre className="text-sm text-emerald-400 font-mono whitespace-pre-wrap">
                {dockerCommand}
              </pre>
            </div>
          </div>
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

export default InstallAgentModal;
