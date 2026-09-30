// HostDetail.tsx - Detailed host view with metrics charts
import React, { useState, useEffect } from 'react';
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle,
  Cpu,
  Database,
  Pencil,
  Radio,
  RefreshCw,
  Server,
  Tag,
  Terminal,
  Trash2,
  XCircle
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useNotifications } from '../contexts/NotificationContext';
import { Button } from './ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from './ui/tabs';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts';

import { API_URL as API_BASE_URL } from '../config/api';

interface Host {
  id: string;
  hostname: string;
  agent_id: string;
  os: string;
  os_version: string;
  kernel: string;
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
}

interface MetricPoint {
  timestamp: string;
  value: number;
}

interface MetricSeries {
  metric_name: string;
  host_id: string;
  data: MetricPoint[];
  unit?: string;
}

interface CurrentMetrics {
  cpu_usage: number;
  cpu_user: number;
  cpu_system: number;
  cpu_iowait: number;
  load_1: number;
  load_5: number;
  load_15: number;
  memory_used: number;
  memory_free: number;
  memory_usage_percent: number;
  swap_used: number;
  swap_free: number;
  disk_usage_percent: number;
  disk_used: number;
  disk_free: number;
  network_bytes_in: number;
  network_bytes_out: number;
  process_count: number;
  process_running: number;
}

interface HostDetailProps {
  hostId: string;
  onBack: () => void;
}

const HostDetail: React.FC<HostDetailProps> = ({ hostId, onBack }) => {
  const { logout } = useAuth();
  const { showToast } = useNotifications();

  const [host, setHost] = useState<Host | null>(null);
  const [currentMetrics, setCurrentMetrics] = useState<CurrentMetrics | null>(null);
  const [cpuHistory, setCpuHistory] = useState<any[]>([]);
  const [memoryHistory, setMemoryHistory] = useState<any[]>([]);
  const [diskHistory, setDiskHistory] = useState<any[]>([]);
  const [networkHistory, setNetworkHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState<string>('1h');
  const [activeTab, setActiveTab] = useState<string>('overview');

  const hasFetchedRef = React.useRef(false);

  useEffect(() => {
    if (hasFetchedRef.current) return;
    hasFetchedRef.current = true;

    loadHostDetails();
    loadCurrentMetrics();
    loadMetricHistory();

    const interval = setInterval(() => {
      loadCurrentMetrics();
    }, 30000);

    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadMetricHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeRange]);

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

  const loadHostDetails = async () => {
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/hosts/${hostId}`);
      if (response.ok) {
        const data = await response.json();
        setHost(data);
      }
    } catch (error) {
      console.error('Error loading host:', error);
      showToast({ type: 'error', message: 'Failed to load host details' });
    } finally {
      setLoading(false);
    }
  };

  const loadCurrentMetrics = async () => {
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/metrics/hosts/${hostId}/current`);
      if (response.ok) {
        const data = await response.json();
        // Transform backend format to frontend expected format
        const metricsMap = data.metrics || {};
        const transformed: CurrentMetrics = {
          cpu_usage: metricsMap['system.cpu.usage']?.value || 0,
          cpu_user: metricsMap['system.cpu.user']?.value || 0,
          cpu_system: metricsMap['system.cpu.system']?.value || 0,
          cpu_iowait: metricsMap['system.cpu.iowait']?.value || 0,
          load_1: metricsMap['system.load.1']?.value || 0,
          load_5: metricsMap['system.load.5']?.value || 0,
          load_15: metricsMap['system.load.15']?.value || 0,
          memory_used: metricsMap['system.memory.used']?.value || 0,
          memory_free: metricsMap['system.memory.free']?.value || 0,
          memory_usage_percent: metricsMap['system.memory.usage_percent']?.value || 0,
          swap_used: metricsMap['system.swap.used']?.value || 0,
          swap_free: metricsMap['system.swap.free']?.value || 0,
          disk_usage_percent: metricsMap['system.disk.usage_percent']?.value || 0,
          disk_used: metricsMap['system.disk.used']?.value || 0,
          disk_free: metricsMap['system.disk.free']?.value || 0,
          network_bytes_in: metricsMap['system.network.bytes_in']?.value || 0,
          network_bytes_out: metricsMap['system.network.bytes_out']?.value || 0,
          process_count: metricsMap['system.processes.total']?.value || 0,
          process_running: metricsMap['system.processes.running']?.value || 0,
        };
        setCurrentMetrics(transformed);
      }
    } catch (error) {
      console.error('Error loading current metrics:', error);
    }
  };

  const loadMetricHistory = async () => {
    const timeRangeHours: Record<string, number> = {
      '1h': 1,
      '6h': 6,
      '24h': 24,
      '7d': 168,
      '30d': 720
    };

    const hours = timeRangeHours[timeRange] || 1;
    const startTime = new Date(Date.now() - hours * 60 * 60 * 1000).toISOString();
    const endTime = new Date().toISOString();

    try {
      // Load CPU history
      const cpuResponse = await authenticatedFetch(
        `${API_BASE_URL}/metrics/hosts/${hostId}/history?metric_names=system.cpu.usage,system.cpu.user,system.cpu.system&start_time=${startTime}&end_time=${endTime}`
      );
      if (cpuResponse.ok) {
        const data = await cpuResponse.json();
        const formatted = formatMetricHistory(data.metrics, ['system.cpu.usage', 'system.cpu.user', 'system.cpu.system']);
        setCpuHistory(formatted);
      }

      // Load Memory history
      const memResponse = await authenticatedFetch(
        `${API_BASE_URL}/metrics/hosts/${hostId}/history?metric_names=system.memory.usage_percent&start_time=${startTime}&end_time=${endTime}`
      );
      if (memResponse.ok) {
        const data = await memResponse.json();
        const formatted = formatMetricHistory(data.metrics, ['system.memory.usage_percent']);
        setMemoryHistory(formatted);
      }

      // Load Disk history
      const diskResponse = await authenticatedFetch(
        `${API_BASE_URL}/metrics/hosts/${hostId}/history?metric_names=system.disk.usage_percent&start_time=${startTime}&end_time=${endTime}`
      );
      if (diskResponse.ok) {
        const data = await diskResponse.json();
        const formatted = formatMetricHistory(data.metrics, ['system.disk.usage_percent']);
        setDiskHistory(formatted);
      }

      // Load Network history
      const netResponse = await authenticatedFetch(
        `${API_BASE_URL}/metrics/hosts/${hostId}/history?metric_names=system.network.bytes_in,system.network.bytes_out&start_time=${startTime}&end_time=${endTime}`
      );
      if (netResponse.ok) {
        const data = await netResponse.json();
        const formatted = formatMetricHistory(data.metrics, ['system.network.bytes_in', 'system.network.bytes_out']);
        setNetworkHistory(formatted);
      }
    } catch (error) {
      console.error('Error loading metric history:', error);
    }
  };

  const formatMetricHistory = (metrics: any[], metricNames: string[]): any[] => {
    if (!metrics || metrics.length === 0) return [];

    const timeMap: Record<string, any> = {};

    metrics.forEach((m) => {
      const shortName = m.metric_name.split('.').pop() || m.metric_name;
      const dataPoints = m.data_points || m.data || [];
      dataPoints.forEach((point: any) => {
        // Support both time_bucket (from backend) and timestamp formats
        const timeStr = point.time_bucket || point.timestamp;
        const time = new Date(timeStr).getTime();
        if (!timeMap[time]) {
          timeMap[time] = { timestamp: time };
        }
        timeMap[time][shortName] = point.value;
      });
    });

    return Object.values(timeMap).sort((a, b) => a.timestamp - b.timestamp);
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const formatTimestamp = (timestamp: number): string => {
    const date = new Date(timestamp);
    if (timeRange === '1h' || timeRange === '6h') {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    return date.toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  const handleDeleteHost = async () => {
    if (!window.confirm(`Are you sure you want to delete host "${host?.hostname}"? This action cannot be undone.`)) {
      return;
    }

    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/hosts/${hostId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        showToast({ type: 'success', message: 'Host deleted successfully' });
        onBack();
      } else {
        const error = await response.json();
        showToast({ type: 'error', message: error.detail || 'Failed to delete host' });
      }
    } catch (error) {
      console.error('Error deleting host:', error);
      showToast({ type: 'error', message: 'Failed to delete host' });
    }
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

  const MetricGauge: React.FC<{ value: number; label: string; unit?: string; warning?: number; critical?: number }> = ({
    value,
    label,
    unit = '%',
    warning = 70,
    critical = 90
  }) => {
    const getColor = () => {
      if (value >= critical) return 'text-red-400';
      if (value >= warning) return 'text-yellow-400';
      return 'text-emerald-400';
    };

    const getBarColor = () => {
      if (value >= critical) return 'bg-red-500';
      if (value >= warning) return 'bg-yellow-500';
      return 'bg-emerald-500';
    };

    return (
      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground">{label}</span>
          <span className={`text-lg font-semibold ${getColor()}`}>
            {value.toFixed(1)}{unit}
          </span>
        </div>
        <div className="h-2 bg-secondary rounded-full overflow-hidden">
          <div
            className={`h-full ${getBarColor()} transition-all duration-500`}
            style={{ width: `${Math.min(value, 100)}%` }}
          />
        </div>
      </div>
    );
  };

  const chartTooltipStyle = { backgroundColor: '#141414', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '8px' };

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[400px]">
        <div className="flex flex-col items-center space-y-4">
          <RefreshCw className="w-8 h-8 text-muted-foreground animate-spin" />
          <p className="text-muted-foreground text-sm">Loading host details...</p>
        </div>
      </div>
    );
  }

  if (!host) {
    return (
      <div className="p-6">
        <div className="bg-transparent border border-border rounded-xl">
          <div className="p-12 text-center">
            <Server className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-base font-medium text-foreground mb-2">Host not found</h3>
            <p className="text-muted-foreground mb-6 text-sm">The requested host could not be found.</p>
            <Button onClick={onBack} variant="outline" className="border border-border text-foreground hover:bg-accent text-sm">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Infrastructure
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-4">
          <Button variant="ghost" onClick={onBack} className="p-2 text-muted-foreground hover:text-foreground hover:bg-accent">
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div className="p-3 bg-secondary rounded-lg">
            <Server className="w-8 h-8 text-muted-foreground" />
          </div>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-[20px] font-semibold text-foreground">{host.hostname}</h1>
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs ${getStatusColor(host.status)}`}>
                {getStatusIcon(host.status)}
                {host.status}
              </span>
            </div>
            <p className="text-muted-foreground text-sm">{host.ip_address}</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Time Range Selector */}
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            className="bg-accent border border-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
          >
            <option value="1h">Last 1 hour</option>
            <option value="6h">Last 6 hours</option>
            <option value="24h">Last 24 hours</option>
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
          </select>
          <Button variant="outline" onClick={() => { loadCurrentMetrics(); loadMetricHistory(); }} className="border border-border text-foreground hover:bg-accent text-sm">
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
          <Button variant="outline" onClick={handleDeleteHost} className="border border-red-500/30 text-red-400 hover:bg-red-500/10 text-sm">
            <Trash2 className="w-4 h-4 mr-2" />
            Delete
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="bg-accent border border-border">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="cpu">CPU</TabsTrigger>
          <TabsTrigger value="memory">Memory</TabsTrigger>
          <TabsTrigger value="disk">Disk</TabsTrigger>
          <TabsTrigger value="network">Network</TabsTrigger>
          <TabsTrigger value="info">System Info</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6 mt-6">
          {/* Current Metrics Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-transparent border border-border rounded-xl">
              <div className="p-6 pb-2">
                <h3 className="text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                  <Cpu className="w-4 h-4" />
                  CPU Usage
                </h3>
              </div>
              <div className="p-6 pt-0">
                <MetricGauge value={currentMetrics?.cpu_usage || 0} label="" />
                <div className="mt-4 grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <span className="text-muted-foreground">User</span>
                    <p className="text-muted-foreground">{currentMetrics?.cpu_user?.toFixed(1)}%</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">System</span>
                    <p className="text-muted-foreground">{currentMetrics?.cpu_system?.toFixed(1)}%</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">IOWait</span>
                    <p className="text-muted-foreground">{currentMetrics?.cpu_iowait?.toFixed(1)}%</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-transparent border border-border rounded-xl">
              <div className="p-6 pb-2">
                <h3 className="text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                  <Database className="w-4 h-4" />
                  Memory Usage
                </h3>
              </div>
              <div className="p-6 pt-0">
                <MetricGauge value={currentMetrics?.memory_usage_percent || 0} label="" />
                <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-muted-foreground">Used</span>
                    <p className="text-muted-foreground">{formatBytes(currentMetrics?.memory_used || 0)}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Free</span>
                    <p className="text-muted-foreground">{formatBytes(currentMetrics?.memory_free || 0)}</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-transparent border border-border rounded-xl">
              <div className="p-6 pb-2">
                <h3 className="text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                  <Database className="w-4 h-4" />
                  Disk Usage
                </h3>
              </div>
              <div className="p-6 pt-0">
                <MetricGauge value={currentMetrics?.disk_usage_percent || 0} label="" />
                <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-muted-foreground">Used</span>
                    <p className="text-muted-foreground">{formatBytes(currentMetrics?.disk_used || 0)}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Free</span>
                    <p className="text-muted-foreground">{formatBytes(currentMetrics?.disk_free || 0)}</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-transparent border border-border rounded-xl">
              <div className="p-6 pb-2">
                <h3 className="text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                  <Radio className="w-4 h-4" />
                  Network
                </h3>
              </div>
              <div className="p-6 pt-0">
                <div className="space-y-3">
                  <div>
                    <span className="text-muted-foreground text-xs">Inbound</span>
                    <p className="text-lg font-semibold text-emerald-400">
                      {formatBytes(currentMetrics?.network_bytes_in || 0)}/s
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-xs">Outbound</span>
                    <p className="text-lg font-semibold text-blue-400">
                      {formatBytes(currentMetrics?.network_bytes_out || 0)}/s
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Load Average & Processes */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-transparent border border-border rounded-xl">
              <div className="p-6">
                <h3 className="text-xs uppercase tracking-wider text-muted-foreground">Load Average</h3>
              </div>
              <div className="p-6 pt-0">
                <div className="grid grid-cols-3 gap-4">
                  <div className="text-center">
                    <p className="text-2xl font-bold text-foreground">{currentMetrics?.load_1?.toFixed(2) || '0.00'}</p>
                    <p className="text-xs uppercase tracking-wider text-muted-foreground">1 min</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-foreground">{currentMetrics?.load_5?.toFixed(2) || '0.00'}</p>
                    <p className="text-xs uppercase tracking-wider text-muted-foreground">5 min</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-foreground">{currentMetrics?.load_15?.toFixed(2) || '0.00'}</p>
                    <p className="text-xs uppercase tracking-wider text-muted-foreground">15 min</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-transparent border border-border rounded-xl">
              <div className="p-6">
                <h3 className="text-xs uppercase tracking-wider text-muted-foreground">Processes</h3>
              </div>
              <div className="p-6 pt-0">
                <div className="grid grid-cols-2 gap-4">
                  <div className="text-center">
                    <p className="text-2xl font-bold text-foreground">{currentMetrics?.process_count || 0}</p>
                    <p className="text-xs uppercase tracking-wider text-muted-foreground">Total</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-emerald-400">{currentMetrics?.process_running || 0}</p>
                    <p className="text-xs uppercase tracking-wider text-muted-foreground">Running</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Overview Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-transparent border border-border rounded-xl">
              <div className="p-6">
                <h3 className="text-xs uppercase tracking-wider text-muted-foreground">CPU History</h3>
              </div>
              <div className="p-6 pt-0">
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={cpuHistory}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                      <XAxis dataKey="timestamp" tickFormatter={formatTimestamp} stroke="#3f3f46" fontSize={10} />
                      <YAxis domain={[0, 100]} stroke="#3f3f46" fontSize={10} />
                      <Tooltip contentStyle={chartTooltipStyle} labelFormatter={(label) => new Date(label).toLocaleString()} />
                      <Area type="monotone" dataKey="usage" stroke="#3B82F6" fill="#3B82F6" fillOpacity={0.15} name="CPU %" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            <div className="bg-transparent border border-border rounded-xl">
              <div className="p-6">
                <h3 className="text-xs uppercase tracking-wider text-muted-foreground">Memory History</h3>
              </div>
              <div className="p-6 pt-0">
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={memoryHistory}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                      <XAxis dataKey="timestamp" tickFormatter={formatTimestamp} stroke="#3f3f46" fontSize={10} />
                      <YAxis domain={[0, 100]} stroke="#3f3f46" fontSize={10} />
                      <Tooltip contentStyle={chartTooltipStyle} labelFormatter={(label) => new Date(label).toLocaleString()} />
                      <Area type="monotone" dataKey="usage_percent" stroke="#10B981" fill="#10B981" fillOpacity={0.15} name="Memory %" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          </div>
        </TabsContent>

        {/* CPU Tab */}
        <TabsContent value="cpu" className="space-y-6 mt-6">
          <div className="bg-transparent border border-border rounded-xl">
            <div className="p-6">
              <h3 className="text-base font-medium text-foreground flex items-center gap-2">
                <Cpu className="w-5 h-5 text-muted-foreground" />
                CPU Usage Over Time
              </h3>
            </div>
            <div className="p-6 pt-0">
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={cpuHistory}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                    <XAxis dataKey="timestamp" tickFormatter={formatTimestamp} stroke="#3f3f46" fontSize={11} />
                    <YAxis domain={[0, 100]} stroke="#3f3f46" fontSize={11} unit="%" />
                    <Tooltip contentStyle={chartTooltipStyle} labelFormatter={(label) => new Date(label).toLocaleString()} />
                    <Legend />
                    <Area type="monotone" dataKey="usage" stroke="#3B82F6" fill="#3B82F6" fillOpacity={0.1} name="Total" />
                    <Area type="monotone" dataKey="user" stroke="#10B981" fill="#10B981" fillOpacity={0.1} name="User" />
                    <Area type="monotone" dataKey="system" stroke="#F59E0B" fill="#F59E0B" fillOpacity={0.1} name="System" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </TabsContent>

        {/* Memory Tab */}
        <TabsContent value="memory" className="space-y-6 mt-6">
          <div className="bg-transparent border border-border rounded-xl">
            <div className="p-6">
              <h3 className="text-base font-medium text-foreground flex items-center gap-2">
                <Database className="w-5 h-5 text-muted-foreground" />
                Memory Usage Over Time
              </h3>
            </div>
            <div className="p-6 pt-0">
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={memoryHistory}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                    <XAxis dataKey="timestamp" tickFormatter={formatTimestamp} stroke="#3f3f46" fontSize={11} />
                    <YAxis domain={[0, 100]} stroke="#3f3f46" fontSize={11} unit="%" />
                    <Tooltip contentStyle={chartTooltipStyle} labelFormatter={(label) => new Date(label).toLocaleString()} />
                    <Area type="monotone" dataKey="usage_percent" stroke="#10B981" fill="#10B981" fillOpacity={0.15} name="Memory Usage" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </TabsContent>

        {/* Disk Tab */}
        <TabsContent value="disk" className="space-y-6 mt-6">
          <div className="bg-transparent border border-border rounded-xl">
            <div className="p-6">
              <h3 className="text-base font-medium text-foreground flex items-center gap-2">
                <Database className="w-5 h-5 text-muted-foreground" />
                Disk Usage Over Time
              </h3>
            </div>
            <div className="p-6 pt-0">
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={diskHistory}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                    <XAxis dataKey="timestamp" tickFormatter={formatTimestamp} stroke="#3f3f46" fontSize={11} />
                    <YAxis domain={[0, 100]} stroke="#3f3f46" fontSize={11} unit="%" />
                    <Tooltip contentStyle={chartTooltipStyle} labelFormatter={(label) => new Date(label).toLocaleString()} />
                    <Area type="monotone" dataKey="usage_percent" stroke="#F59E0B" fill="#F59E0B" fillOpacity={0.15} name="Disk Usage" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </TabsContent>

        {/* Network Tab */}
        <TabsContent value="network" className="space-y-6 mt-6">
          <div className="bg-transparent border border-border rounded-xl">
            <div className="p-6">
              <h3 className="text-base font-medium text-foreground flex items-center gap-2">
                <Radio className="w-5 h-5 text-muted-foreground" />
                Network Traffic Over Time
              </h3>
            </div>
            <div className="p-6 pt-0">
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={networkHistory}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                    <XAxis dataKey="timestamp" tickFormatter={formatTimestamp} stroke="#3f3f46" fontSize={11} />
                    <YAxis stroke="#3f3f46" fontSize={11} tickFormatter={(value) => formatBytes(value)} />
                    <Tooltip contentStyle={chartTooltipStyle} labelFormatter={(label) => new Date(label).toLocaleString()} formatter={(value) => value !== undefined ? formatBytes(value as number) + '/s' : 'N/A'} />
                    <Legend />
                    <Line type="monotone" dataKey="bytes_in" stroke="#10B981" name="Inbound" dot={false} />
                    <Line type="monotone" dataKey="bytes_out" stroke="#3B82F6" name="Outbound" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </TabsContent>

        {/* System Info Tab */}
        <TabsContent value="info" className="space-y-6 mt-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-transparent border border-border rounded-xl">
              <div className="p-6">
                <h3 className="text-base font-medium text-foreground flex items-center gap-2">
                  <Server className="w-5 h-5 text-muted-foreground" />
                  System Information
                </h3>
              </div>
              <div className="p-6 pt-0">
                <div className="space-y-4">
                  <div className="flex justify-between items-center border-b border-border pb-2">
                    <span className="text-muted-foreground text-sm">Hostname</span>
                    <span className="text-foreground font-medium text-sm">{host.hostname}</span>
                  </div>
                  <div className="flex justify-between items-center border-b border-border pb-2">
                    <span className="text-muted-foreground text-sm">IP Address</span>
                    <span className="text-foreground font-medium text-sm">{host.ip_address}</span>
                  </div>
                  <div className="flex justify-between items-center border-b border-border pb-2">
                    <span className="text-muted-foreground text-sm">Operating System</span>
                    <span className="text-foreground font-medium text-sm">{host.os} {host.os_version}</span>
                  </div>
                  <div className="flex justify-between items-center border-b border-border pb-2">
                    <span className="text-muted-foreground text-sm">Kernel</span>
                    <span className="text-foreground font-medium text-sm">{host.kernel || 'N/A'}</span>
                  </div>
                  <div className="flex justify-between items-center border-b border-border pb-2">
                    <span className="text-muted-foreground text-sm">Architecture</span>
                    <span className="text-foreground font-medium text-sm">{host.arch}</span>
                  </div>
                  <div className="flex justify-between items-center border-b border-border pb-2">
                    <span className="text-muted-foreground text-sm">CPU Model</span>
                    <span className="text-foreground font-medium truncate ml-4 text-sm">{host.cpu_model}</span>
                  </div>
                  <div className="flex justify-between items-center border-b border-border pb-2">
                    <span className="text-muted-foreground text-sm">CPU Cores</span>
                    <span className="text-foreground font-medium text-sm">{host.cpu_cores}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground text-sm">Total Memory</span>
                    <span className="text-foreground font-medium text-sm">{formatBytes(host.memory_total_bytes)}</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-transparent border border-border rounded-xl">
              <div className="p-6">
                <h3 className="text-base font-medium text-foreground flex items-center gap-2">
                  <Terminal className="w-5 h-5 text-muted-foreground" />
                  Agent Information
                </h3>
              </div>
              <div className="p-6 pt-0">
                <div className="space-y-4">
                  <div className="flex justify-between items-center border-b border-border pb-2">
                    <span className="text-muted-foreground text-sm">Agent ID</span>
                    <span className="text-foreground font-mono text-sm">{host.agent_id}</span>
                  </div>
                  <div className="flex justify-between items-center border-b border-border pb-2">
                    <span className="text-muted-foreground text-sm">Agent Version</span>
                    <span className="text-foreground font-medium text-sm">v{host.agent_version}</span>
                  </div>
                  <div className="flex justify-between items-center border-b border-border pb-2">
                    <span className="text-muted-foreground text-sm">First Seen</span>
                    <span className="text-foreground font-medium text-sm">
                      {new Date(host.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground text-sm">Last Seen</span>
                    <span className="text-foreground font-medium text-sm">
                      {new Date(host.last_seen_at).toLocaleString()}
                    </span>
                  </div>
                </div>

                {/* Tags */}
                {host.tags && Object.keys(host.tags).length > 0 && (
                  <div className="mt-6">
                    <h4 className="text-xs uppercase tracking-wider text-muted-foreground mb-3 flex items-center gap-2">
                      <Tag className="w-4 h-4" />
                      Tags
                    </h4>
                    <div className="flex flex-wrap items-center gap-2">
                      {Object.entries(host.tags).map(([key, value]) => (
                        <span key={key} className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-accent border border-border text-muted-foreground">
                          {key}: {value}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default HostDetail;
