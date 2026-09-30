// frontend/oncall-frontend/src/components/ContainerMonitoring.tsx
import React, { useState, useEffect } from 'react';
import {
  Activity,
  AlertCircle,
  Box,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Clock,
  Container,
  Cpu,
  ExternalLink,
  Filter,
  HardDrive,
  Layers,
  MoreVertical,
  Network,
  Play,
  Plus,
  RefreshCw,
  Scale,
  Search,
  Server,
  Settings,
  Terminal,
  Trash2,
  XCircle
} from 'lucide-react';
import { API_URL } from '../config/api';

// Types
interface Cluster {
  id: string;
  name: string;
  display_name: string;
  description: string;
  provider: string;
  region: string;
  version: string;
  status: string;
  connection_status: string;
  last_sync: string;
  node_count: number;
  pod_count: number;
  namespace_count: number;
  deployment_count: number;
  service_count: number;
  cpu_capacity: number;
  cpu_usage: number;
  memory_capacity: number;
  memory_usage: number;
}

interface Node {
  id: string;
  cluster_id: string;
  name: string;
  status: string;
  kubernetes_version: string;
  os_image: string;
  instance_type: string;
  zone: string;
  cpu_capacity: number;
  cpu_usage: number;
  memory_capacity: number;
  memory_usage: number;
  pod_count: number;
  pod_capacity: number;
  conditions: any[];
  roles: string[];
  is_master: boolean;
}

interface Pod {
  id: string;
  cluster_id: string;
  namespace_id: string;
  name: string;
  phase: string;
  node_name: string;
  owner_kind: string;
  owner_name: string;
  restart_count: number;
  container_count: number;
  ready_containers: number;
  containers: any[];
  cpu_usage: number;
  memory_usage: number;
  pod_ip: string;
  created_at: string;
}

interface Deployment {
  id: string;
  cluster_id: string;
  namespace_id: string;
  name: string;
  replicas: number;
  ready_replicas: number;
  available_replicas: number;
  status: string;
  strategy_type: string;
  containers: any[];
  created_at: string;
}

interface Namespace {
  id: string;
  cluster_id: string;
  name: string;
  status: string;
  pod_count: number;
  cpu_usage: number;
  memory_usage: number;
}

interface K8sEvent {
  id: string;
  cluster_id: string;
  namespace_name: string;
  involved_kind: string;
  involved_name: string;
  event_type: string;
  reason: string;
  message: string;
  last_timestamp: string;
  count: number;
}

interface ClusterSummary {
  total_clusters: number;
  healthy_clusters: number;
  warning_clusters: number;
  critical_clusters: number;
  total_nodes: number;
  total_pods: number;
  running_pods: number;
  failed_pods: number;
  pending_pods: number;
  total_cpu_capacity: number;
  total_cpu_usage: number;
  total_memory_capacity: number;
  total_memory_usage: number;
}

type ViewMode = 'overview' | 'clusters' | 'nodes' | 'pods' | 'deployments' | 'services' | 'events';

interface ContainerMonitoringProps {
  isDemoMode?: boolean;
}

const ContainerMonitoring: React.FC<ContainerMonitoringProps> = ({ isDemoMode = false }) => {
  const [viewMode, setViewMode] = useState<ViewMode>('overview');
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [nodes, setNodes] = useState<Node[]>([]);
  const [pods, setPods] = useState<Pod[]>([]);
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [namespaces, setNamespaces] = useState<Namespace[]>([]);
  const [events, setEvents] = useState<K8sEvent[]>([]);
  const [summary, setSummary] = useState<ClusterSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedCluster, setSelectedCluster] = useState<string | null>(null);
  const [selectedNamespace, setSelectedNamespace] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [showCreateCluster, setShowCreateCluster] = useState(false);
  const [expandedCluster, setExpandedCluster] = useState<string | null>(null);
  const [selectedPod, setSelectedPod] = useState<Pod | null>(null);

  const getAuthHeaders = () => ({
    'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
    'Content-Type': 'application/json',
  });

  // Fetch data
  useEffect(() => {
    fetchClusters();
    fetchSummary();
  }, []);

  useEffect(() => {
    if (selectedCluster) {
      fetchNodes(selectedCluster);
      fetchNamespaces(selectedCluster);
      fetchPods(selectedCluster);
      fetchDeployments(selectedCluster);
      fetchEvents(selectedCluster);
    } else {
      fetchAllPods();
      fetchAllNodes();
      fetchAllDeployments();
      fetchAllEvents();
    }
  }, [selectedCluster]);

  const fetchClusters = async () => {
    try {
      const response = await fetch(`${API_URL}/containers/clusters`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setClusters(data.clusters || []);
      } else {
        setClusters([]);
      }
    } catch (error) {
      console.error('Failed to fetch clusters:', error);
      setClusters([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchSummary = async () => {
    try {
      const response = await fetch(`${API_URL}/containers/clusters/summary`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setSummary(data || null);
      } else {
        setSummary(null);
      }
    } catch (error) {
      console.error('Failed to fetch summary:', error);
      setSummary(null);
    }
  };

  const fetchNodes = async (clusterId: string) => {
    try {
      const response = await fetch(`${API_URL}/containers/nodes?cluster_id=${clusterId}`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setNodes(data.nodes || []);
      } else {
        setNodes([]);
      }
    } catch (error) {
      console.error('Failed to fetch nodes:', error);
      setNodes([]);
    }
  };

  const fetchAllNodes = async () => {
    try {
      const response = await fetch(`${API_URL}/containers/nodes`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setNodes(data.nodes || []);
      } else {
        setNodes([]);
      }
    } catch (error) {
      console.error('Failed to fetch nodes:', error);
      setNodes([]);
    }
  };

  const fetchNamespaces = async (clusterId: string) => {
    try {
      const response = await fetch(`${API_URL}/containers/namespaces?cluster_id=${clusterId}`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setNamespaces(data.namespaces || []);
      }
    } catch (error) {
      console.error('Failed to fetch namespaces:', error);
    }
  };

  const fetchPods = async (clusterId: string) => {
    try {
      let url = `${API_URL}/containers/pods?cluster_id=${clusterId}`;
      if (selectedNamespace) {
        url += `&namespace_id=${selectedNamespace}`;
      }
      const response = await fetch(url, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setPods(data.pods || []);
      } else {
        setPods([]);
      }
    } catch (error) {
      console.error('Failed to fetch pods:', error);
      setPods([]);
    }
  };

  const fetchAllPods = async () => {
    try {
      const response = await fetch(`${API_URL}/containers/pods`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setPods(data.pods || []);
      } else {
        setPods([]);
      }
    } catch (error) {
      console.error('Failed to fetch pods:', error);
      setPods([]);
    }
  };

  const fetchDeployments = async (clusterId: string) => {
    try {
      let url = `${API_URL}/containers/deployments?cluster_id=${clusterId}`;
      if (selectedNamespace) {
        url += `&namespace_id=${selectedNamespace}`;
      }
      const response = await fetch(url, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setDeployments(data.deployments || []);
      } else {
        setDeployments([]);
      }
    } catch (error) {
      console.error('Failed to fetch deployments:', error);
      setDeployments([]);
    }
  };

  const fetchAllDeployments = async () => {
    try {
      const response = await fetch(`${API_URL}/containers/deployments`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setDeployments(data.deployments || []);
      } else {
        setDeployments([]);
      }
    } catch (error) {
      console.error('Failed to fetch deployments:', error);
      setDeployments([]);
    }
  };

  const fetchEvents = async (clusterId: string) => {
    try {
      const response = await fetch(`${API_URL}/containers/events?cluster_id=${clusterId}&limit=50`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setEvents(data.events || []);
      } else {
        setEvents([]);
      }
    } catch (error) {
      console.error('Failed to fetch events:', error);
      setEvents([]);
    }
  };

  const fetchAllEvents = async () => {
    try {
      const response = await fetch(`${API_URL}/containers/events?limit=50`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setEvents(data.events || []);
      } else {
        setEvents([]);
      }
    } catch (error) {
      console.error('Failed to fetch events:', error);
      setEvents([]);
    }
  };

  // Helper functions
  const formatBytes = (bytes: number): string => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatCpu = (cores: number): string => {
    if (!cores) return '0';
    if (cores < 1) return `${Math.round(cores * 1000)}m`;
    return `${cores.toFixed(2)} cores`;
  };

  const getStatusColor = (status: string): string => {
    switch (status?.toLowerCase()) {
      case 'healthy':
      case 'running':
      case 'ready':
      case 'available':
      case 'active':
      case 'succeeded':
        return 'text-green-400';
      case 'warning':
      case 'pending':
      case 'progressing':
        return 'text-yellow-400';
      case 'critical':
      case 'failed':
      case 'error':
      case 'notready':
        return 'text-red-400';
      default:
        return 'text-muted-foreground';
    }
  };

  const getStatusBg = (status: string): string => {
    switch (status?.toLowerCase()) {
      case 'healthy':
      case 'running':
      case 'ready':
      case 'available':
      case 'active':
      case 'succeeded':
        return 'bg-green-500/20 text-green-400';
      case 'warning':
      case 'pending':
      case 'progressing':
        return 'bg-yellow-500/20 text-yellow-400';
      case 'critical':
      case 'failed':
      case 'error':
      case 'notready':
        return 'bg-red-500/20 text-red-400';
      default:
        return 'bg-secondary text-muted-foreground';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'healthy':
      case 'running':
      case 'ready':
      case 'available':
      case 'succeeded':
        return <CheckCircle className="w-4 h-4 text-green-400" />;
      case 'warning':
      case 'pending':
      case 'progressing':
        return <Clock className="w-4 h-4 text-yellow-400" />;
      case 'critical':
      case 'failed':
      case 'error':
        return <XCircle className="w-4 h-4 text-red-400" />;
      default:
        return <AlertCircle className="w-4 h-4 text-muted-foreground" />;
    }
  };

  // Render Overview
  const renderOverview = () => (
    <div className="space-y-6">
      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-muted/50 rounded-xl p-4 border border-border/50">
            <div className="flex items-center gap-3 mb-2">
              <Server className="w-5 h-5 text-blue-400" />
              <span className="text-muted-foreground text-sm">Clusters</span>
            </div>
            <div className="text-2xl font-bold text-foreground">{summary.total_clusters}</div>
            <div className="flex gap-2 mt-2 text-xs">
              <span className="text-green-400">{summary.healthy_clusters} healthy</span>
              {summary.warning_clusters > 0 && (
                <span className="text-yellow-400">{summary.warning_clusters} warning</span>
              )}
              {summary.critical_clusters > 0 && (
                <span className="text-red-400">{summary.critical_clusters} critical</span>
              )}
            </div>
          </div>

          <div className="bg-muted/50 rounded-xl p-4 border border-border/50">
            <div className="flex items-center gap-3 mb-2">
              <Layers className="w-5 h-5 text-purple-400" />
              <span className="text-muted-foreground text-sm">Nodes</span>
            </div>
            <div className="text-2xl font-bold text-foreground">{summary.total_nodes}</div>
          </div>

          <div className="bg-muted/50 rounded-xl p-4 border border-border/50">
            <div className="flex items-center gap-3 mb-2">
              <Box className="w-5 h-5 text-green-400" />
              <span className="text-muted-foreground text-sm">Pods</span>
            </div>
            <div className="text-2xl font-bold text-foreground">{summary.total_pods}</div>
            <div className="flex gap-2 mt-2 text-xs">
              <span className="text-green-400">{summary.running_pods} running</span>
              {summary.pending_pods > 0 && (
                <span className="text-yellow-400">{summary.pending_pods} pending</span>
              )}
              {summary.failed_pods > 0 && (
                <span className="text-red-400">{summary.failed_pods} failed</span>
              )}
            </div>
          </div>

          <div className="bg-muted/50 rounded-xl p-4 border border-border/50">
            <div className="flex items-center gap-3 mb-2">
              <Cpu className="w-5 h-5 text-orange-400" />
              <span className="text-muted-foreground text-sm">Resources</span>
            </div>
            <div className="space-y-2">
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-muted-foreground">CPU</span>
                  <span className="text-foreground">
                    {summary.total_cpu_capacity > 0
                      ? Math.round((summary.total_cpu_usage / summary.total_cpu_capacity) * 100)
                      : 0}%
                  </span>
                </div>
                <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-orange-500 rounded-full"
                    style={{
                      width: `${summary.total_cpu_capacity > 0
                        ? Math.min(100, (summary.total_cpu_usage / summary.total_cpu_capacity) * 100)
                        : 0}%`
                    }}
                  />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-muted-foreground">Memory</span>
                  <span className="text-foreground">
                    {summary.total_memory_capacity > 0
                      ? Math.round((summary.total_memory_usage / summary.total_memory_capacity) * 100)
                      : 0}%
                  </span>
                </div>
                <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-purple-500 rounded-full"
                    style={{
                      width: `${summary.total_memory_capacity > 0
                        ? Math.min(100, (summary.total_memory_usage / summary.total_memory_capacity) * 100)
                        : 0}%`
                    }}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Clusters List */}
      <div className="bg-muted/50 rounded-xl border border-border/50">
        <div className="p-4 border-b border-border/50 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-foreground">Kubernetes Clusters</h3>
          <button
            onClick={() => setShowCreateCluster(true)}
            className="flex items-center gap-2 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-foreground rounded-lg text-sm transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Cluster
          </button>
        </div>

        {clusters.length === 0 ? (
          <div className="p-8 text-center">
            <Server className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
            <h4 className="text-lg font-medium text-foreground mb-2">No Clusters Configured</h4>
            <p className="text-muted-foreground mb-4">
              Add a Kubernetes cluster to start monitoring containers, pods, and deployments.
            </p>
            <button
              onClick={() => setShowCreateCluster(true)}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-foreground rounded-lg transition-colors"
            >
              Add Your First Cluster
            </button>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {clusters.map(cluster => (
              <div key={cluster.id} className="p-4">
                <div
                  className="flex items-center justify-between cursor-pointer"
                  onClick={() => setExpandedCluster(expandedCluster === cluster.id ? null : cluster.id)}
                >
                  <div className="flex items-center gap-4">
                    <div className={`p-2 rounded-lg flex-shrink-0 ${getStatusBg(cluster.status)}`}>
                      <Server className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="font-medium text-foreground">{cluster.display_name || cluster.name}</h4>
                        <span className={`px-2 py-0.5 rounded text-xs ${getStatusBg(cluster.status)}`}>
                          {cluster.status}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-sm text-muted-foreground">
                        {cluster.provider && <span>{cluster.provider}</span>}
                        {cluster.region && <span>{cluster.region}</span>}
                        {cluster.version && <span>v{cluster.version}</span>}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-6">
                    <div className="grid grid-cols-4 gap-6 text-center">
                      <div>
                        <div className="text-lg font-semibold text-foreground">{cluster.node_count}</div>
                        <div className="text-xs text-muted-foreground">Nodes</div>
                      </div>
                      <div>
                        <div className="text-lg font-semibold text-foreground">{cluster.pod_count}</div>
                        <div className="text-xs text-muted-foreground">Pods</div>
                      </div>
                      <div>
                        <div className="text-lg font-semibold text-foreground">{cluster.deployment_count}</div>
                        <div className="text-xs text-muted-foreground">Deployments</div>
                      </div>
                      <div>
                        <div className="text-lg font-semibold text-foreground">{cluster.namespace_count}</div>
                        <div className="text-xs text-muted-foreground">Namespaces</div>
                      </div>
                    </div>
                    {expandedCluster === cluster.id ? (
                      <ChevronDown className="w-5 h-5 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="w-5 h-5 text-muted-foreground" />
                    )}
                  </div>
                </div>

                {expandedCluster === cluster.id && (
                  <div className="mt-4 pt-4 border-t border-border/50">
                    <div className="grid grid-cols-2 gap-4 mb-4">
                      <div className="bg-muted/50 rounded-lg p-3">
                        <div className="text-sm text-muted-foreground mb-2">CPU Usage</div>
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                            <div
                              className="h-full bg-orange-500 rounded-full"
                              style={{
                                width: `${cluster.cpu_capacity > 0
                                  ? Math.min(100, (cluster.cpu_usage / cluster.cpu_capacity) * 100)
                                  : 0}%`
                              }}
                            />
                          </div>
                          <span className="text-sm text-foreground">
                            {formatCpu(cluster.cpu_usage)} / {formatCpu(cluster.cpu_capacity)}
                          </span>
                        </div>
                      </div>
                      <div className="bg-muted/50 rounded-lg p-3">
                        <div className="text-sm text-muted-foreground mb-2">Memory Usage</div>
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                            <div
                              className="h-full bg-purple-500 rounded-full"
                              style={{
                                width: `${cluster.memory_capacity > 0
                                  ? Math.min(100, (cluster.memory_usage / cluster.memory_capacity) * 100)
                                  : 0}%`
                              }}
                            />
                          </div>
                          <span className="text-sm text-foreground">
                            {formatBytes(cluster.memory_usage)} / {formatBytes(cluster.memory_capacity)}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="flex gap-2">
                      <button
                        onClick={() => setSelectedCluster(cluster.id)}
                        className="flex items-center gap-2 px-3 py-1.5 bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 rounded-lg text-sm transition-colors"
                      >
                        <Layers className="w-4 h-4" />
                        View Resources
                      </button>
                      <button className="flex items-center gap-2 px-3 py-1.5 bg-muted/50 text-foreground hover:bg-muted rounded-lg text-sm transition-colors">
                        <Settings className="w-4 h-4" />
                        Settings
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recent Events */}
      {events.length > 0 && (
        <div className="bg-muted/50 rounded-xl border border-border/50">
          <div className="p-4 border-b border-border/50 flex items-center justify-between">
            <h3 className="text-lg font-semibold text-foreground">Recent Events</h3>
            <button
              onClick={() => setViewMode('events')}
              className="text-sm text-blue-400 hover:text-blue-300"
            >
              View All
            </button>
          </div>
          <div className="divide-y divide-border max-h-96 overflow-y-auto">
            {events.slice(0, 10).map(event => (
              <div key={event.id} className="p-3 hover:bg-muted/20">
                <div className="flex items-start gap-3">
                  {event.event_type === 'Warning' ? (
                    <AlertCircle className="w-4 h-4 text-yellow-400 mt-0.5 flex-shrink-0" />
                  ) : (
                    <Activity className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-foreground">{event.reason}</span>
                      <span className="text-xs text-muted-foreground">
                        {event.involved_kind}/{event.involved_name}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground truncate">{event.message}</p>
                    <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                      {event.namespace_name && <span>{event.namespace_name}</span>}
                      {event.count > 1 && <span>({event.count}x)</span>}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );

  // Render Pods View
  const renderPodsView = () => {
    const filteredPods = pods.filter(pod =>
      pod.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      pod.node_name?.toLowerCase().includes(searchTerm.toLowerCase())
    );

    return (
      <div className="space-y-4">
        <div className="flex items-center gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search pods..."
              className="w-full pl-10 pr-4 py-2 bg-muted/50 border border-border/50 rounded-lg text-foreground placeholder-muted-foreground focus:outline-none focus:border-blue-500"
            />
          </div>
          <select
            value={selectedNamespace || ''}
            onChange={(e) => setSelectedNamespace(e.target.value || null)}
            className="px-4 py-2 bg-muted/50 border border-border/50 rounded-lg text-foreground focus:outline-none focus:border-blue-500"
          >
            <option value="">All Namespaces</option>
            {namespaces.map(ns => (
              <option key={ns.id} value={ns.id}>{ns.name}</option>
            ))}
          </select>
        </div>

        <div className="bg-muted/50 rounded-xl border border-border/50 overflow-hidden">
          <table className="w-full">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Pod</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Containers</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Restarts</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Node</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">CPU/Memory</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredPods.map(pod => (
                <tr key={pod.id} className="hover:bg-muted/20">
                  <td className="px-4 py-3">
                    <div>
                      <div className="font-medium text-foreground">{pod.name}</div>
                      {pod.owner_kind && (
                        <div className="text-xs text-muted-foreground">
                          {pod.owner_kind}: {pod.owner_name}
                        </div>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded text-xs ${getStatusBg(pod.phase)}`}>
                      {pod.phase}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={pod.ready_containers === pod.container_count ? 'text-green-400' : 'text-yellow-400'}>
                      {pod.ready_containers}/{pod.container_count}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={pod.restart_count > 5 ? 'text-red-400' : 'text-foreground'}>
                      {pod.restart_count}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground text-sm">
                    {pod.node_name || '-'}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <div className="text-muted-foreground">
                      {formatCpu(pod.cpu_usage)} / {formatBytes(pod.memory_usage)}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => setSelectedPod(pod)}
                      className="p-1 text-muted-foreground hover:text-foreground"
                    >
                      <Terminal className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  // Render Deployments View
  const renderDeploymentsView = () => (
    <div className="space-y-4">
      <div className="bg-muted/50 rounded-xl border border-border/50 overflow-hidden">
        <table className="w-full">
          <thead className="bg-muted/50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Deployment</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Status</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Replicas</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Strategy</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Images</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {deployments.map(deployment => (
              <tr key={deployment.id} className="hover:bg-muted/20">
                <td className="px-4 py-3">
                  <div className="font-medium text-foreground">{deployment.name}</div>
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded text-xs ${getStatusBg(deployment.status)}`}>
                    {deployment.status}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={deployment.ready_replicas === deployment.replicas ? 'text-green-400' : 'text-yellow-400'}>
                    {deployment.ready_replicas}/{deployment.replicas}
                  </span>
                </td>
                <td className="px-4 py-3 text-muted-foreground text-sm">
                  {deployment.strategy_type}
                </td>
                <td className="px-4 py-3">
                  <div className="space-y-1">
                    {deployment.containers?.slice(0, 2).map((container: any, i: number) => (
                      <div key={i} className="text-xs text-muted-foreground truncate max-w-xs">
                        {container.image}
                      </div>
                    ))}
                    {deployment.containers?.length > 2 && (
                      <div className="text-xs text-muted-foreground">+{deployment.containers.length - 2} more</div>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <button className="p-1 text-muted-foreground hover:text-foreground" title="Scale">
                      <Scale className="w-4 h-4" />
                    </button>
                    <button className="p-1 text-muted-foreground hover:text-foreground" title="Restart">
                      <RefreshCw className="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );

  // Render Nodes View
  const renderNodesView = () => (
    <div className="space-y-4">
      <div className="grid gap-4">
        {nodes.map(node => (
          <div key={node.id} className="bg-muted/50 rounded-xl border border-border/50 p-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg flex-shrink-0 ${getStatusBg(node.status)}`}>
                  <Server className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="font-medium text-foreground">{node.name}</h4>
                    {node.is_master && (
                      <span className="px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded text-xs">master</span>
                    )}
                    <span className={`px-2 py-0.5 rounded text-xs ${getStatusBg(node.status)}`}>
                      {node.status}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-sm text-muted-foreground">
                    {node.instance_type && <span>{node.instance_type}</span>}
                    {node.zone && <span>{node.zone}</span>}
                    {node.kubernetes_version && <span>v{node.kubernetes_version}</span>}
                  </div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm text-muted-foreground">
                  {node.pod_count}/{node.pod_capacity} pods
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="flex items-center justify-between text-sm mb-1">
                  <span className="text-muted-foreground">CPU</span>
                  <span className="text-foreground">
                    {formatCpu(node.cpu_usage)} / {formatCpu(node.cpu_capacity)}
                  </span>
                </div>
                <div className="h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-orange-500 rounded-full"
                    style={{
                      width: `${node.cpu_capacity > 0
                        ? Math.min(100, (node.cpu_usage / node.cpu_capacity) * 100)
                        : 0}%`
                    }}
                  />
                </div>
              </div>
              <div>
                <div className="flex items-center justify-between text-sm mb-1">
                  <span className="text-muted-foreground">Memory</span>
                  <span className="text-foreground">
                    {formatBytes(node.memory_usage)} / {formatBytes(node.memory_capacity)}
                  </span>
                </div>
                <div className="h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-purple-500 rounded-full"
                    style={{
                      width: `${node.memory_capacity > 0
                        ? Math.min(100, (node.memory_usage / node.memory_capacity) * 100)
                        : 0}%`
                    }}
                  />
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  // Render Events View
  const renderEventsView = () => (
    <div className="bg-muted/50 rounded-xl border border-border/50">
      <div className="divide-y divide-border">
        {events.map(event => (
          <div key={event.id} className="p-4 hover:bg-muted/20">
            <div className="flex items-start gap-3">
              {event.event_type === 'Warning' ? (
                <AlertCircle className="w-5 h-5 text-yellow-400 mt-0.5 flex-shrink-0" />
              ) : (
                <Activity className="w-5 h-5 text-blue-400 mt-0.5 flex-shrink-0" />
              )}
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-foreground">{event.reason}</span>
                  <span className={`px-2 py-0.5 rounded text-xs ${
                    event.event_type === 'Warning' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-blue-500/20 text-blue-400'
                  }`}>
                    {event.event_type}
                  </span>
                </div>
                <p className="text-muted-foreground mb-2">{event.message}</p>
                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                  <span>{event.involved_kind}/{event.involved_name}</span>
                  {event.namespace_name && <span>Namespace: {event.namespace_name}</span>}
                  {event.count > 1 && <span>Count: {event.count}</span>}
                  <span>{new Date(event.last_timestamp).toLocaleString()}</span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-blue-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Colorful Header */}
      <div className="relative overflow-hidden border-b border-border">

        <div className="relative max-w-7xl mx-auto px-6 py-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-blue-500/10">
                <Container className="w-6 h-6 text-blue-400" />
              </div>
              <div>
                <h1 className="text-base font-medium text-foreground">Container Monitoring</h1>
                <p className="text-muted-foreground text-sm">Monitor Kubernetes clusters, pods, and deployments</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              {selectedCluster && (
                <button
                  onClick={() => setSelectedCluster(null)}
                  className="px-3 py-1.5 text-muted-foreground hover:text-foreground"
                >
                  Clear Filter
                </button>
              )}
              <button
                onClick={() => {
                  fetchClusters();
                  fetchSummary();
                }}
                className="p-2 text-muted-foreground hover:text-foreground hover:bg-muted/50 rounded-lg transition-colors"
              >
                <RefreshCw className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
      {/* Navigation Tabs */}
      <div className="flex items-center gap-1 mb-6 bg-muted/30 p-1 rounded-lg w-fit">
        {[
          { id: 'overview', label: 'Overview', icon: Activity },
          { id: 'nodes', label: 'Nodes', icon: Server },
          { id: 'pods', label: 'Pods', icon: Box },
          { id: 'deployments', label: 'Deployments', icon: Layers },
          { id: 'events', label: 'Events', icon: AlertCircle },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setViewMode(tab.id as ViewMode)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              viewMode === tab.id
                ? 'bg-blue-600 text-foreground'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      {viewMode === 'overview' && renderOverview()}
      {viewMode === 'nodes' && renderNodesView()}
      {viewMode === 'pods' && renderPodsView()}
      {viewMode === 'deployments' && renderDeploymentsView()}
      {viewMode === 'events' && renderEventsView()}
      </div>

      {/* Pod Detail Modal */}
      {selectedPod && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-muted rounded-xl max-w-2xl w-full max-h-[80vh] overflow-hidden">
            <div className="p-4 border-b border-border flex items-center justify-between">
              <div className="flex items-center gap-3 min-w-0">
                <div className="min-w-0">
                  <h3 className="text-lg font-semibold text-foreground truncate">{selectedPod.name}</h3>
                </div>
                <span className={`px-2 py-0.5 rounded text-xs flex-shrink-0 ${getStatusBg(selectedPod.phase)}`}>
                  {selectedPod.phase}
                </span>
              </div>
              <button
                onClick={() => setSelectedPod(null)}
                className="text-muted-foreground hover:text-foreground"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 overflow-y-auto max-h-96">
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <div className="text-sm text-muted-foreground">Node</div>
                  <div className="text-foreground">{selectedPod.node_name || 'Not scheduled'}</div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground">Pod IP</div>
                  <div className="text-foreground">{selectedPod.pod_ip || '-'}</div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground">Restarts</div>
                  <div className="text-foreground">{selectedPod.restart_count}</div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground">Owner</div>
                  <div className="text-foreground">{selectedPod.owner_kind}: {selectedPod.owner_name}</div>
                </div>
              </div>

              <h4 className="font-medium text-foreground mb-2">Containers</h4>
              <div className="space-y-2">
                {selectedPod.containers?.map((container: any, i: number) => (
                  <div key={i} className="bg-muted/50 rounded-lg p-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-medium text-foreground">{container.name}</span>
                      <span className={`px-2 py-0.5 rounded text-xs ${getStatusBg(container.state)}`}>
                        {container.state}
                      </span>
                    </div>
                    <div className="text-sm text-muted-foreground truncate">{container.image}</div>
                    {container.restart_count > 0 && (
                      <div className="text-sm text-yellow-400">Restarts: {container.restart_count}</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create Cluster Modal */}
      {showCreateCluster && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-muted rounded-xl max-w-lg w-full">
            <div className="p-4 border-b border-border">
              <h3 className="text-lg font-semibold text-foreground">Add Kubernetes Cluster</h3>
            </div>
            <div className="p-4">
              <p className="text-muted-foreground mb-4">
                To add a Kubernetes cluster, install the OffCall monitoring agent in your cluster.
                The agent will automatically sync cluster resources.
              </p>
              <div className="bg-muted/50 rounded-lg p-4 mb-4">
                <div className="text-sm text-muted-foreground mb-2">Install via Helm:</div>
                <code className="text-sm text-green-400">
                  helm install offcall-agent offcall/agent --set apiKey=YOUR_API_KEY
                </code>
              </div>
              <div className="flex justify-end gap-2">
                <button
                  onClick={() => setShowCreateCluster(false)}
                  className="px-4 py-2 text-muted-foreground hover:text-foreground"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ContainerMonitoring;
