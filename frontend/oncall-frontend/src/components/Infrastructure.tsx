// Infrastructure.tsx - Host monitoring dashboard
import React, { useState, useEffect } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  ClipboardCopy,
  CloudDownload,
  Cpu,
  Database,
  Filter,
  Radio,
  RefreshCw,
  Search,
  Server,
  Terminal,
  XCircle
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useNotifications } from '../contexts/NotificationContext';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';
import APIKeyModal from './APIKeyModal';
import InstallAgentModal from './InstallAgentModal';

import { API_URL as API_BASE_URL } from '../config/api';

// No demo fallback - show empty state when no hosts

interface Host {
  id: string;
  hostname: string;
  agent_id: string;
  os: string;
  os_version: string;
  arch: string;
  cpu_cores: number;
  cpu_model: string;
  memory_total_bytes: number;
  agent_version: string;
  status: 'online' | 'offline' | 'warning';
  ip_address: string;
  last_seen_at: string;
  created_at: string;
  tags: Record<string, string>;
  // Latest metrics
  current_metrics?: {
    cpu_usage: number;
    memory_usage: number;
    disk_usage: number;
    network_in: number;
    network_out: number;
  };
}

interface HostListResponse {
  hosts: Host[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

interface InfrastructureStats {
  total_hosts: number;
  online_hosts: number;
  offline_hosts: number;
  warning_hosts: number;
  total_cpu_cores: number;
  total_memory_gb: number;
}

interface InfrastructureProps {
  onNavigateToHost?: (hostId: string) => void;
}

const Infrastructure: React.FC<InfrastructureProps> = ({ onNavigateToHost }) => {
  const { user, logout } = useAuth();
  const { showToast } = useNotifications();

  const [hosts, setHosts] = useState<Host[]>([]);
  const [stats, setStats] = useState<InfrastructureStats>({
    total_hosts: 0,
    online_hosts: 0,
    offline_hosts: 0,
    warning_hosts: 0,
    total_cpu_cores: 0,
    total_memory_gb: 0
  });
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [showInstallModal, setShowInstallModal] = useState(false);
  const [showAPIKeyModal, setShowAPIKeyModal] = useState(false);
  const hasFetchedRef = React.useRef(false);

  useEffect(() => {
    if (hasFetchedRef.current) return;
    hasFetchedRef.current = true;

    loadHosts();
    const interval = setInterval(loadHosts, 30000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const authenticatedFetch = async (url: string, options: RequestInit = {}) => {
    const token = localStorage.getItem('access_token');
    if (!token) throw new Error('No access token');

    const response = await fetch(url, {
      ...options,
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (response.status === 401) {
      logout();
      throw new Error('Session expired');
    }

    return response;
  };

  const loadHosts = async () => {
    try {
      // Authenticated mode
      const response = await authenticatedFetch(`${API_BASE_URL}/hosts/`);

      if (response.ok) {
        const data: HostListResponse = await response.json();
        const hostList = data.hosts || [];
        setHosts(hostList);

        // Calculate stats
        const online = hostList.filter(h => h.status === 'online').length;
        const offline = hostList.filter(h => h.status === 'offline').length;
        const warning = hostList.filter(h => h.status === 'warning').length;
        const totalCores = hostList.reduce((sum, h) => sum + (h.cpu_cores || 0), 0);
        const totalMemory = hostList.reduce((sum, h) => sum + (h.memory_total_bytes || 0), 0);

        setStats({
          total_hosts: hostList.length,
          online_hosts: online,
          offline_hosts: offline,
          warning_hosts: warning,
          total_cpu_cores: totalCores,
          total_memory_gb: Math.round(totalMemory / (1024 * 1024 * 1024))
        });
      } else {
        // Show empty state on error
        setHosts([]);
        setStats({
          total_hosts: 0,
          online_hosts: 0,
          offline_hosts: 0,
          warning_hosts: 0,
          total_cpu_cores: 0,
          total_memory_gb: 0
        });
      }
    } catch (error) {
      console.error('Error loading hosts:', error);
      // Show empty state on error
      setHosts([]);
      setStats({
        total_hosts: 0,
        online_hosts: 0,
        offline_hosts: 0,
        warning_hosts: 0,
        total_cpu_cores: 0,
        total_memory_gb: 0
      });
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    showToast({ type: 'success', message: 'Copied to clipboard' });
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const formatLastSeen = (timestamp: string): string => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'online': return 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
      case 'offline': return 'bg-red-500/10 text-red-400 border border-red-500/20';
      case 'warning': return 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20';
      default: return 'bg-accent text-muted-foreground border border-border';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'online': return <CheckCircle className="w-4 h-4" />;
      case 'offline': return <XCircle className="w-4 h-4" />;
      case 'warning': return <AlertTriangle className="w-4 h-4" />;
      default: return <Server className="w-4 h-4" />;
    }
  };

  const filteredHosts = hosts.filter(host => {
    const matchesSearch =
      host.hostname.toLowerCase().includes(searchQuery.toLowerCase()) ||
      host.ip_address?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      host.agent_id.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesStatus = statusFilter === 'all' || host.status === statusFilter;

    return matchesSearch && matchesStatus;
  });

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[400px]">
        <div className="flex flex-col items-center space-y-4">
          <RefreshCw className="w-8 h-8 text-muted-foreground animate-spin" />
          <p className="text-muted-foreground text-sm">Loading infrastructure...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-blue-500/10">
                <Server className="w-6 h-6 text-blue-400" />
              </div>
              <div>
                <h1 className="text-base font-medium text-foreground">Infrastructure</h1>
                <p className="text-muted-foreground text-sm">Monitor your servers and infrastructure</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Button
                onClick={() => setShowAPIKeyModal(true)}
                variant="outline"
                className="gap-2 border border-border text-foreground hover:bg-accent text-sm"
              >
                <Terminal className="w-4 h-4" />
                API Keys
              </Button>
              <Button
                onClick={() => setShowInstallModal(true)}
                className="gap-2 bg-primary text-primary-foreground hover:bg-white/90 text-sm"
              >
                <CloudDownload className="w-4 h-4" />
                Install Agent
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* Stats Cards */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <div className="bg-transparent border border-border rounded-xl">
            <div className="p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="p-2 rounded-xl bg-blue-500/10">
                  <Server className="w-4 h-4 text-blue-400" />
                </div>
              </div>
              <p className="text-2xl font-bold text-foreground">{stats.total_hosts}</p>
              <p className="text-xs uppercase tracking-wider text-muted-foreground">Total Hosts</p>
            </div>
          </div>

          <div className="bg-transparent border border-border rounded-xl">
            <div className="p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="p-2 rounded-xl bg-emerald-500/10">
                  <CheckCircle className="w-4 h-4 text-emerald-400" />
                </div>
              </div>
              <p className="text-2xl font-bold text-foreground">{stats.online_hosts}</p>
              <p className="text-xs uppercase tracking-wider text-muted-foreground">Online</p>
            </div>
          </div>

          <div className="bg-transparent border border-border rounded-xl">
            <div className="p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="p-2 rounded-xl bg-red-500/10">
                  <XCircle className="w-4 h-4 text-red-400" />
                </div>
              </div>
              <p className="text-2xl font-bold text-foreground">{stats.offline_hosts}</p>
              <p className="text-xs uppercase tracking-wider text-muted-foreground">Offline</p>
            </div>
          </div>

          <div className="bg-transparent border border-border rounded-xl">
            <div className="p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="p-2 rounded-xl bg-yellow-500/10">
                  <AlertTriangle className="w-4 h-4 text-yellow-400" />
                </div>
              </div>
              <p className="text-2xl font-bold text-foreground">{stats.warning_hosts}</p>
              <p className="text-xs uppercase tracking-wider text-muted-foreground">Warning</p>
            </div>
          </div>

          <div className="bg-transparent border border-border rounded-xl">
            <div className="p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="p-2 rounded-xl bg-purple-500/10">
                  <Cpu className="w-4 h-4 text-purple-400" />
                </div>
              </div>
              <p className="text-2xl font-bold text-foreground">{stats.total_cpu_cores}</p>
              <p className="text-xs uppercase tracking-wider text-muted-foreground">CPU Cores</p>
            </div>
          </div>

          <div className="bg-transparent border border-border rounded-xl">
            <div className="p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="p-2 rounded-xl bg-cyan-500/10">
                  <Database className="w-4 h-4 text-cyan-400" />
                </div>
              </div>
              <p className="text-2xl font-bold text-foreground">{stats.total_memory_gb} GB</p>
              <p className="text-xs uppercase tracking-wider text-muted-foreground">Total Memory</p>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-transparent border border-border rounded-xl">
          <div className="p-4">
            <div className="flex flex-col sm:flex-row gap-4">
              <div className="flex-1 relative">
                <Search className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Search by hostname, IP, or agent ID..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 bg-accent border-border focus:border-white/20 text-sm"
                />
              </div>
              <div className="flex items-center gap-2">
                <Filter className="w-4 h-4 text-muted-foreground" />
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="bg-accent border border-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
                >
                <option value="all">All Status</option>
                <option value="online">Online</option>
                <option value="offline">Offline</option>
                <option value="warning">Warning</option>
              </select>
            </div>
          </div>
        </div>
      </div>

        {/* Host List */}
        {filteredHosts.length === 0 ? (
          <div className="bg-transparent border border-border rounded-xl">
            <div className="p-12 text-center">
              <div className="p-4 rounded-xl bg-accent w-fit mx-auto mb-4">
                <Server className="w-12 h-12 text-muted-foreground" />
              </div>
              <h3 className="text-base font-medium text-foreground mb-2">
                {hosts.length === 0 ? 'No hosts monitored yet' : 'No hosts match your filters'}
              </h3>
              <p className="text-muted-foreground mb-6 text-sm">
                {hosts.length === 0
                  ? 'Install the OffCall agent on your servers to start monitoring'
                  : 'Try adjusting your search or filter criteria'
                }
              </p>
              {hosts.length === 0 && (
                <Button onClick={() => setShowInstallModal(true)} className="gap-2 bg-primary text-primary-foreground hover:bg-white/90 text-sm">
                  <CloudDownload className="w-4 h-4" />
                  Install Agent
                </Button>
              )}
            </div>
          </div>
        ) : (
          <div className="grid gap-4">
            {filteredHosts.map((host) => (
              <div
                key={host.id}
                className="bg-transparent border border-border rounded-xl transition-all cursor-pointer hover:bg-accent/50"
                onClick={() => onNavigateToHost?.(host.id)}
              >
                <div className="p-4">
                  <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                    {/* Host Info */}
                    <div className="flex items-center gap-4 flex-1 min-w-0">
                      <div className={`p-3 rounded-xl ${
                        host.status === 'online' ? 'bg-emerald-500/10' :
                        host.status === 'warning' ? 'bg-yellow-500/10' :
                        'bg-red-500/10'
                      }`}>
                        <Server className={`w-6 h-6 ${
                          host.status === 'online' ? 'text-emerald-400' :
                          host.status === 'warning' ? 'text-yellow-400' :
                          'text-red-400'
                        }`} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-3 mb-1">
                          <h3 className="text-base font-medium text-foreground truncate">{host.hostname}</h3>
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs ${getStatusColor(host.status)}`}>
                            {getStatusIcon(host.status)}
                            {host.status}
                          </span>
                        </div>
                        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
                          <span className="text-muted-foreground">{host.ip_address}</span>
                          <span>{host.os} {host.os_version}</span>
                          <span>{host.arch}</span>
                          <span className="text-muted-foreground">v{host.agent_version}</span>
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                          Last seen: {formatLastSeen(host.last_seen_at)}
                        </p>
                      </div>
                    </div>

                    {/* Metrics Preview */}
                    {host.current_metrics && (
                      <div className="grid grid-cols-4 gap-4 lg:gap-6">
                        <div className="text-center">
                          <div className="text-base font-medium text-foreground">
                            {host.current_metrics.cpu_usage.toFixed(1)}%
                          </div>
                          <div className="text-xs uppercase tracking-wider text-muted-foreground">CPU</div>
                          <div className="mt-1 h-1.5 bg-secondary rounded-full overflow-hidden">
                            <div
                              className={`h-full transition-all ${host.current_metrics.cpu_usage > 80 ? 'bg-red-500' : host.current_metrics.cpu_usage > 60 ? 'bg-yellow-500' : 'bg-emerald-500'}`}
                              style={{ width: `${host.current_metrics.cpu_usage}%` }}
                            />
                          </div>
                        </div>
                        <div className="text-center">
                          <div className="text-base font-medium text-foreground">
                            {host.current_metrics.memory_usage.toFixed(1)}%
                          </div>
                          <div className="text-xs uppercase tracking-wider text-muted-foreground">Memory</div>
                          <div className="mt-1 h-1.5 bg-secondary rounded-full overflow-hidden">
                            <div
                              className={`h-full transition-all ${host.current_metrics.memory_usage > 80 ? 'bg-red-500' : host.current_metrics.memory_usage > 60 ? 'bg-yellow-500' : 'bg-purple-500'}`}
                              style={{ width: `${host.current_metrics.memory_usage}%` }}
                            />
                          </div>
                        </div>
                        <div className="text-center">
                          <div className="text-base font-medium text-foreground">
                            {host.current_metrics.disk_usage.toFixed(1)}%
                          </div>
                          <div className="text-xs uppercase tracking-wider text-muted-foreground">Disk</div>
                          <div className="mt-1 h-1.5 bg-secondary rounded-full overflow-hidden">
                            <div
                              className={`h-full transition-all ${host.current_metrics.disk_usage > 80 ? 'bg-red-500' : host.current_metrics.disk_usage > 60 ? 'bg-yellow-500' : 'bg-blue-500'}`}
                              style={{ width: `${host.current_metrics.disk_usage}%` }}
                            />
                          </div>
                        </div>
                        <div className="text-center">
                          <div className="text-base font-medium text-foreground flex items-center justify-center gap-1">
                            <Radio className="w-4 h-4 text-muted-foreground" />
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {formatBytes(host.current_metrics.network_in)}/s
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Tags */}
                    {host.tags && Object.keys(host.tags).length > 0 && (
                      <div className="flex flex-wrap gap-2 lg:max-w-xs">
                        {Object.entries(host.tags).slice(0, 3).map(([key, value]) => (
                          <span key={key} className="inline-flex items-center text-xs px-2 py-0.5 rounded bg-accent border border-border text-muted-foreground">
                            {key}: {value}
                          </span>
                        ))}
                        {Object.keys(host.tags).length > 3 && (
                          <span className="inline-flex items-center text-xs px-2 py-0.5 rounded bg-accent border border-border text-muted-foreground">
                            +{Object.keys(host.tags).length - 3} more
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Install Agent Modal - Standalone component to prevent re-render issues */}
      <InstallAgentModal
        isOpen={showInstallModal}
        onClose={() => setShowInstallModal(false)}
      />

      {/* API Keys Modal - Standalone component to prevent re-render issues */}
      <APIKeyModal
        isOpen={showAPIKeyModal}
        onClose={() => setShowAPIKeyModal(false)}
      />
    </div>
  );
};

export default Infrastructure;
