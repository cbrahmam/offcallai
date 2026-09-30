// frontend/oncall-frontend/src/components/NetworkMonitoring.tsx
import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  BarChart3,
  CheckCircle,
  Clock,
  Cpu,
  Edit2,
  ExternalLink,
  Eye,
  Globe,
  HardDrive,
  Layers,
  MapPin,
  MoreVertical,
  Network,
  Play,
  Plus,
  Radio,
  RefreshCw,
  Router,
  Search,
  Server,
  Settings,
  Shield,
  Thermometer,
  Trash2,
  TrendingUp,
  Wifi,
  WifiOff,
  XCircle
} from 'lucide-react';

import { API_URL as API_BASE } from '../config/api';

interface NetworkDevice {
  id: string;
  name: string;
  display_name?: string;
  description?: string;
  device_type: string;
  vendor?: string;
  model?: string;
  management_ip?: string;
  location?: string;
  status: string;
  cpu_utilization?: number;
  memory_utilization?: number;
  uptime_seconds?: number;
  temperature_celsius?: number;
  interface_count: number;
  interfaces_up: number;
  interfaces_down: number;
  last_seen?: string;
  last_poll?: string;
  tags: string[];
  created_at: string;
}

interface NetworkInterface {
  id: string;
  device_id: string;
  name: string;
  display_name?: string;
  description?: string;
  if_type?: string;
  ip_address?: string;
  mac_address?: string;
  speed_mbps?: number;
  actual_speed_mbps?: number;
  admin_status: string;
  oper_status: string;
  bytes_in: number;
  bytes_out: number;
  errors_in: number;
  errors_out: number;
  utilization_in_percent?: number;
  utilization_out_percent?: number;
  bandwidth_in_bps?: number;
  bandwidth_out_bps?: number;
  connected_device_name?: string;
  connected_interface_name?: string;
  last_poll?: string;
}

interface NetworkFlow {
  id: string;
  device_id?: string;
  interface_id?: string;
  flow_start: string;
  flow_end?: string;
  duration_ms?: number;
  src_ip: string;
  src_port?: number;
  dst_ip: string;
  dst_port?: number;
  protocol_name?: string;
  bytes_total?: number;
  packets_total?: number;
  application?: string;
  direction?: string;
}

interface NetworkAlert {
  id: string;
  device_id?: string;
  interface_id?: string;
  alert_type: string;
  severity: string;
  status: string;
  title: string;
  message?: string;
  metric_value?: number;
  threshold_value?: number;
  triggered_at: string;
  acknowledged_at?: string;
  resolved_at?: string;
}

interface NetworkStats {
  total_devices: number;
  devices_up: number;
  devices_down: number;
  devices_degraded: number;
  total_interfaces: number;
  interfaces_up: number;
  interfaces_down: number;
  total_bandwidth_in_bps: number;
  total_bandwidth_out_bps: number;
  avg_cpu_utilization: number;
  avg_memory_utilization: number;
  active_alerts: number;
  devices_by_type: Record<string, number>;
  top_talkers: any[];
}

interface TopologyData {
  devices: NetworkDevice[];
  links: any[];
}

type TabType = 'overview' | 'devices' | 'interfaces' | 'flows' | 'alerts' | 'topology';

export default function NetworkMonitoring() {
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [devices, setDevices] = useState<NetworkDevice[]>([]);
  const [interfaces, setInterfaces] = useState<NetworkInterface[]>([]);
  const [flows, setFlows] = useState<NetworkFlow[]>([]);
  const [alerts, setAlerts] = useState<NetworkAlert[]>([]);
  const [stats, setStats] = useState<NetworkStats | null>(null);
  const [topology, setTopology] = useState<TopologyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [deviceTypeFilter, setDeviceTypeFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [selectedDevice, setSelectedDevice] = useState<NetworkDevice | null>(null);
  const [showDeviceModal, setShowDeviceModal] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);

  const getAuthHeaders = useCallback(() => {
    const token = localStorage.getItem('access_token');
    return {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    };
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/network/stats`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      } else {
        setStats(null);
      }
    } catch (error) {
      console.error('Failed to fetch network stats:', error);
      setStats(null);
    }
  }, [getAuthHeaders]);

  const fetchDevices = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (deviceTypeFilter !== 'all') params.append('device_type', deviceTypeFilter);
      if (statusFilter !== 'all') params.append('status', statusFilter);
      if (searchTerm) params.append('search', searchTerm);

      const response = await fetch(`${API_BASE}/network/devices?${params}`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        const devicesData = data.items || [];
        setDevices(devicesData);
      } else {
        setDevices([]);
      }
    } catch (error) {
      console.error('Failed to fetch devices:', error);
      setDevices([]);
    }
  }, [getAuthHeaders, deviceTypeFilter, statusFilter, searchTerm]);

  const fetchFlows = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/network/flows?page_size=100`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        const flowsData = data.items || [];
        setFlows(flowsData);
      } else {
        setFlows([]);
      }
    } catch (error) {
      console.error('Failed to fetch flows:', error);
      setFlows([]);
    }
  }, [getAuthHeaders]);

  const fetchAlerts = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/network/alerts?status=active`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        const alertsData = data.items || [];
        setAlerts(alertsData);
      } else {
        setAlerts([]);
      }
    } catch (error) {
      console.error('Failed to fetch alerts:', error);
      setAlerts([]);
    }
  }, [getAuthHeaders]);

  const fetchTopology = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/network/topology`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setTopology(data);
      } else {
        setTopology(null);
      }
    } catch (error) {
      console.error('Failed to fetch topology:', error);
      setTopology(null);
    }
  }, [getAuthHeaders]);

  const fetchDeviceInterfaces = useCallback(async (deviceId: string) => {
    try {
      const response = await fetch(`${API_BASE}/network/devices/${deviceId}/interfaces`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        const interfacesData = data.items || [];
        setInterfaces(interfacesData);
      } else {
        setInterfaces([]);
      }
    } catch (error) {
      console.error('Failed to fetch interfaces:', error);
      setInterfaces([]);
    }
  }, [getAuthHeaders]);

  const pollDevice = async (deviceId: string) => {
    try {
      await fetch(`${API_BASE}/network/devices/${deviceId}/poll`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      fetchDevices();
    } catch (error) {
      console.error('Failed to poll device:', error);
    }
  };

  const acknowledgeAlert = async (alertId: string) => {
    try {
      await fetch(`${API_BASE}/network/alerts/${alertId}/acknowledge`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      fetchAlerts();
    } catch (error) {
      console.error('Failed to acknowledge alert:', error);
    }
  };

  const resolveAlert = async (alertId: string) => {
    try {
      await fetch(`${API_BASE}/network/alerts/${alertId}/resolve`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      fetchAlerts();
    } catch (error) {
      console.error('Failed to resolve alert:', error);
    }
  };

  const deleteDevice = async (deviceId: string) => {
    if (!window.confirm('Are you sure you want to delete this device?')) return;
    try {
      await fetch(`${API_BASE}/network/devices/${deviceId}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });
      fetchDevices();
      fetchStats();
    } catch (error) {
      console.error('Failed to delete device:', error);
    }
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([fetchStats(), fetchDevices(), fetchAlerts()]);
      setLoading(false);
    };
    loadData();
  }, [fetchStats, fetchDevices, fetchAlerts]);

  useEffect(() => {
    if (activeTab === 'flows') fetchFlows();
    if (activeTab === 'topology') fetchTopology();
  }, [activeTab, fetchFlows, fetchTopology]);

  useEffect(() => {
    fetchDevices();
  }, [deviceTypeFilter, statusFilter, searchTerm, fetchDevices]);

  const getDeviceTypeIcon = (type: string) => {
    switch (type) {
      case 'router': return Router;
      case 'switch': return Layers;
      case 'firewall': return Shield;
      case 'load_balancer': return ArrowUpDown;
      case 'access_point': return Radio;
      case 'vpn_gateway': return Globe;
      default: return Server;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'up': return 'text-green-400';
      case 'down': return 'text-red-400';
      case 'degraded': return 'text-yellow-400';
      case 'maintenance': return 'text-blue-400';
      default: return 'text-muted-foreground';
    }
  };

  const getStatusBg = (status: string) => {
    switch (status) {
      case 'up': return 'bg-green-500/20 text-green-400';
      case 'down': return 'bg-red-500/20 text-red-400';
      case 'degraded': return 'bg-yellow-500/20 text-yellow-400';
      case 'maintenance': return 'bg-blue-500/20 text-blue-400';
      default: return 'bg-secondary text-muted-foreground';
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'bg-red-500/20 text-red-400';
      case 'warning': return 'bg-yellow-500/20 text-yellow-400';
      case 'info': return 'bg-blue-500/20 text-blue-400';
      default: return 'bg-secondary text-muted-foreground';
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatBps = (bps: number) => {
    if (bps === 0) return '0 bps';
    const k = 1000;
    const sizes = ['bps', 'Kbps', 'Mbps', 'Gbps'];
    const i = Math.floor(Math.log(bps) / Math.log(k));
    return parseFloat((bps / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatUptime = (seconds?: number) => {
    if (!seconds) return 'Unknown';
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  };

  const tabs = [
    { id: 'overview' as TabType, label: 'Overview', icon: BarChart3 },
    { id: 'devices' as TabType, label: 'Devices', icon: Server },
    { id: 'interfaces' as TabType, label: 'Interfaces', icon: Network },
    { id: 'flows' as TabType, label: 'Traffic Flows', icon: Activity },
    { id: 'alerts' as TabType, label: 'Alerts', icon: AlertTriangle },
    { id: 'topology' as TabType, label: 'Topology', icon: Globe },
  ];

  const deviceTypes = [
    { value: 'all', label: 'All Types' },
    { value: 'router', label: 'Router' },
    { value: 'switch', label: 'Switch' },
    { value: 'firewall', label: 'Firewall' },
    { value: 'load_balancer', label: 'Load Balancer' },
    { value: 'access_point', label: 'Access Point' },
    { value: 'vpn_gateway', label: 'VPN Gateway' },
    { value: 'other', label: 'Other' },
  ];

  const renderOverview = () => (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-muted/50 rounded-xl p-4 border border-border/50">
          <div className="flex items-center gap-3 mb-2">
            <Server className="w-5 h-5 text-blue-400" />
            <span className="text-muted-foreground text-sm">Total Devices</span>
          </div>
          <div className="text-2xl font-bold text-foreground">{stats?.total_devices || 0}</div>
          <div className="flex items-center gap-2 mt-2 text-xs">
            <span className="text-green-400">{stats?.devices_up || 0} up</span>
            <span className="text-red-400">{stats?.devices_down || 0} down</span>
          </div>
        </div>

        <div className="bg-muted/50 rounded-xl p-4 border border-border/50">
          <div className="flex items-center gap-3 mb-2">
            <Network className="w-5 h-5 text-purple-400" />
            <span className="text-muted-foreground text-sm">Total Interfaces</span>
          </div>
          <div className="text-2xl font-bold text-foreground">{stats?.total_interfaces || 0}</div>
          <div className="flex items-center gap-2 mt-2 text-xs">
            <span className="text-green-400">{stats?.interfaces_up || 0} up</span>
            <span className="text-red-400">{stats?.interfaces_down || 0} down</span>
          </div>
        </div>

        <div className="bg-muted/50 rounded-xl p-4 border border-border/50">
          <div className="flex items-center gap-3 mb-2">
            <Activity className="w-5 h-5 text-green-400" />
            <span className="text-muted-foreground text-sm">Total Bandwidth</span>
          </div>
          <div className="text-lg font-bold text-foreground">
            <ArrowDown className="h-3 w-3 inline text-green-400" /> {formatBps(stats?.total_bandwidth_in_bps || 0)}
          </div>
          <div className="text-lg font-bold text-foreground">
            <ArrowUp className="h-3 w-3 inline text-blue-400" /> {formatBps(stats?.total_bandwidth_out_bps || 0)}
          </div>
        </div>

        <div className="bg-muted/50 rounded-xl p-4 border border-border/50">
          <div className="flex items-center gap-3 mb-2">
            <AlertTriangle className="w-5 h-5 text-red-400" />
            <span className="text-muted-foreground text-sm">Active Alerts</span>
          </div>
          <div className="text-2xl font-bold text-foreground">{stats?.active_alerts || 0}</div>
          <div className="text-xs text-muted-foreground mt-2">
            Requires attention
          </div>
        </div>
      </div>

      {/* Resource Utilization */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-card border border-border rounded-lg p-4">
          <h3 className="text-lg font-semibold mb-4">Average Resource Utilization</h3>
          <div className="space-y-4">
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm text-muted-foreground flex items-center gap-2">
                  <Cpu className="h-4 w-4" /> CPU
                </span>
                <span className="text-sm font-medium">{(stats?.avg_cpu_utilization || 0).toFixed(1)}%</span>
              </div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${
                    (stats?.avg_cpu_utilization || 0) > 80 ? 'bg-red-500' :
                    (stats?.avg_cpu_utilization || 0) > 60 ? 'bg-yellow-500' : 'bg-green-500'
                  }`}
                  style={{ width: `${stats?.avg_cpu_utilization || 0}%` }}
                />
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm text-muted-foreground flex items-center gap-2">
                  <HardDrive className="h-4 w-4" /> Memory
                </span>
                <span className="text-sm font-medium">{(stats?.avg_memory_utilization || 0).toFixed(1)}%</span>
              </div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${
                    (stats?.avg_memory_utilization || 0) > 85 ? 'bg-red-500' :
                    (stats?.avg_memory_utilization || 0) > 70 ? 'bg-yellow-500' : 'bg-green-500'
                  }`}
                  style={{ width: `${stats?.avg_memory_utilization || 0}%` }}
                />
              </div>
            </div>
          </div>
        </div>

        <div className="bg-card border border-border rounded-lg p-4">
          <h3 className="text-lg font-semibold mb-4">Devices by Type</h3>
          <div className="grid grid-cols-2 gap-3">
            {Object.entries(stats?.devices_by_type || {}).map(([type, count]) => {
              const Icon = getDeviceTypeIcon(type);
              return (
                <div key={type} className="flex items-center gap-2 p-2 bg-muted/30 rounded-lg">
                  <Icon className="h-4 w-4 text-blue-400" />
                  <span className="text-sm capitalize">{type.replace('_', ' ')}</span>
                  <span className="ml-auto text-sm font-medium">{count}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Recent Alerts */}
      <div className="bg-card border border-border rounded-lg p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Recent Alerts</h3>
          <button
            onClick={() => setActiveTab('alerts')}
            className="text-sm text-blue-400 hover:text-blue-300"
          >
            View All
          </button>
        </div>
        <div className="space-y-2">
          {alerts.slice(0, 5).map((alert) => (
            <div key={alert.id} className="flex items-center justify-between p-3 bg-muted/30 rounded-lg">
              <div className="flex items-center gap-3">
                <AlertTriangle className={`h-4 w-4 ${
                  alert.severity === 'critical' ? 'text-red-400' : 'text-yellow-400'
                }`} />
                <div>
                  <div className="font-medium">{alert.title}</div>
                  <div className="text-xs text-muted-foreground">
                    {new Date(alert.triggered_at).toLocaleString()}
                  </div>
                </div>
              </div>
              <span className={`px-2 py-1 rounded-full text-xs ${getSeverityColor(alert.severity)}`}>
                {alert.severity}
              </span>
            </div>
          ))}
          {alerts.length === 0 && (
            <div className="text-center text-muted-foreground py-4">
              No active alerts
            </div>
          )}
        </div>
      </div>

      {/* Top Talkers */}
      {stats?.top_talkers && stats.top_talkers.length > 0 && (
        <div className="bg-card border border-border rounded-lg p-4">
          <h3 className="text-lg font-semibold mb-4">Top Traffic Sources</h3>
          <div className="space-y-2">
            {stats.top_talkers.slice(0, 5).map((talker, index) => (
              <div key={index} className="flex items-center justify-between p-3 bg-muted/30 rounded-lg">
                <div className="flex items-center gap-3">
                  <span className="text-lg font-bold text-muted-foreground">#{index + 1}</span>
                  <div>
                    <div className="font-medium">{talker.ip || talker.device_name}</div>
                    <div className="text-xs text-muted-foreground">{talker.application || 'Unknown'}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-medium">{formatBytes(talker.bytes_total || 0)}</div>
                  <div className="text-xs text-muted-foreground">{talker.flow_count || 0} flows</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );

  const renderDevices = () => (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="relative flex-1 min-w-64">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search devices..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-muted border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <select
          value={deviceTypeFilter}
          onChange={(e) => setDeviceTypeFilter(e.target.value)}
          className="px-3 py-2 bg-muted border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {deviceTypes.map((type) => (
            <option key={type.value} value={type.value}>{type.label}</option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 bg-muted border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="all">All Status</option>
          <option value="up">Up</option>
          <option value="down">Down</option>
          <option value="degraded">Degraded</option>
          <option value="maintenance">Maintenance</option>
        </select>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-foreground rounded-lg hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" />
          Add Device
        </button>
      </div>

      {/* Device Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {devices.map((device) => {
          const DeviceIcon = getDeviceTypeIcon(device.device_type);
          return (
            <div key={device.id} className="bg-card border border-border rounded-lg p-4 hover:border-blue-500/50 transition-colors">
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${getStatusBg(device.status)}`}>
                    <DeviceIcon className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="font-semibold">{device.display_name || device.name}</div>
                    <div className="text-xs text-muted-foreground capitalize">
                      {device.device_type.replace('_', ' ')}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => pollDevice(device.id)}
                    className="p-1.5 text-muted-foreground hover:text-foreground rounded"
                    title="Poll device"
                  >
                    <RefreshCw className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => {
                      setSelectedDevice(device);
                      fetchDeviceInterfaces(device.id);
                      setShowDeviceModal(true);
                    }}
                    className="p-1.5 text-muted-foreground hover:text-foreground rounded"
                    title="View details"
                  >
                    <Eye className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => deleteDevice(device.id)}
                    className="p-1.5 text-muted-foreground hover:text-red-400 rounded"
                    title="Delete device"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>

              <div className="space-y-2 text-sm">
                {device.management_ip && (
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Globe className="h-3.5 w-3.5" />
                    <span>{device.management_ip}</span>
                  </div>
                )}
                {device.location && (
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <MapPin className="h-3.5 w-3.5" />
                    <span>{device.location}</span>
                  </div>
                )}
                {device.vendor && device.model && (
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Settings className="h-3.5 w-3.5" />
                    <span>{device.vendor} {device.model}</span>
                  </div>
                )}
              </div>

              <div className="mt-3 pt-3 border-t border-border grid grid-cols-3 gap-2 text-center text-xs">
                <div>
                  <div className="text-muted-foreground">CPU</div>
                  <div className={`font-medium ${
                    (device.cpu_utilization || 0) > 80 ? 'text-red-400' :
                    (device.cpu_utilization || 0) > 60 ? 'text-yellow-400' : 'text-green-400'
                  }`}>
                    {device.cpu_utilization?.toFixed(1) || '-'}%
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground">Memory</div>
                  <div className={`font-medium ${
                    (device.memory_utilization || 0) > 85 ? 'text-red-400' :
                    (device.memory_utilization || 0) > 70 ? 'text-yellow-400' : 'text-green-400'
                  }`}>
                    {device.memory_utilization?.toFixed(1) || '-'}%
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground">Interfaces</div>
                  <div className="font-medium">
                    <span className="text-green-400">{device.interfaces_up}</span>
                    <span className="text-muted-foreground">/</span>
                    <span>{device.interface_count}</span>
                  </div>
                </div>
              </div>

              <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  Uptime: {formatUptime(device.uptime_seconds)}
                </span>
                {device.temperature_celsius && (
                  <span className="flex items-center gap-1">
                    <Thermometer className="h-3 w-3" />
                    {device.temperature_celsius.toFixed(1)}°C
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {devices.length === 0 && !loading && (
        <div className="text-center py-12 text-muted-foreground">
          <Server className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>No network devices found</p>
          <p className="text-sm mt-1">Add a device to start monitoring</p>
        </div>
      )}
    </div>
  );

  const renderInterfaces = () => (
    <div className="space-y-4">
      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <table className="w-full">
          <thead className="bg-muted/50">
            <tr>
              <th className="text-left px-4 py-3 text-sm font-medium">Interface</th>
              <th className="text-left px-4 py-3 text-sm font-medium">Status</th>
              <th className="text-left px-4 py-3 text-sm font-medium">IP Address</th>
              <th className="text-left px-4 py-3 text-sm font-medium">Speed</th>
              <th className="text-right px-4 py-3 text-sm font-medium">Traffic In</th>
              <th className="text-right px-4 py-3 text-sm font-medium">Traffic Out</th>
              <th className="text-right px-4 py-3 text-sm font-medium">Utilization</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {interfaces.map((iface) => (
              <tr key={iface.id} className="hover:bg-muted/30">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Network className={`h-4 w-4 ${
                      iface.oper_status === 'up' ? 'text-green-400' : 'text-red-400'
                    }`} />
                    <div>
                      <div className="font-medium">{iface.display_name || iface.name}</div>
                      <div className="text-xs text-muted-foreground">{iface.if_type || 'ethernet'}</div>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs ${getStatusBg(iface.oper_status)}`}>
                    {iface.oper_status}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm">{iface.ip_address || '-'}</td>
                <td className="px-4 py-3 text-sm">
                  {iface.actual_speed_mbps ? `${iface.actual_speed_mbps} Mbps` : '-'}
                </td>
                <td className="px-4 py-3 text-sm text-right">
                  <div>{formatBytes(iface.bytes_in)}</div>
                  {iface.bandwidth_in_bps && (
                    <div className="text-xs text-green-400">{formatBps(iface.bandwidth_in_bps)}</div>
                  )}
                </td>
                <td className="px-4 py-3 text-sm text-right">
                  <div>{formatBytes(iface.bytes_out)}</div>
                  {iface.bandwidth_out_bps && (
                    <div className="text-xs text-blue-400">{formatBps(iface.bandwidth_out_bps)}</div>
                  )}
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <div className="w-16">
                      <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                        <div
                          className="h-full bg-green-500 rounded-full"
                          style={{ width: `${Math.min(iface.utilization_in_percent || 0, 100)}%` }}
                        />
                      </div>
                    </div>
                    <span className="text-xs w-12 text-right">
                      {(iface.utilization_in_percent || 0).toFixed(1)}%
                    </span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {interfaces.length === 0 && (
          <div className="text-center py-8 text-muted-foreground">
            Select a device to view its interfaces
          </div>
        )}
      </div>
    </div>
  );

  const renderFlows = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Traffic Flows</h3>
        <button
          onClick={fetchFlows}
          className="flex items-center gap-2 px-3 py-1.5 text-sm bg-muted hover:bg-muted/80 rounded-lg"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <table className="w-full">
          <thead className="bg-muted/50">
            <tr>
              <th className="text-left px-4 py-3 text-sm font-medium">Time</th>
              <th className="text-left px-4 py-3 text-sm font-medium">Source</th>
              <th className="text-left px-4 py-3 text-sm font-medium">Destination</th>
              <th className="text-left px-4 py-3 text-sm font-medium">Protocol</th>
              <th className="text-left px-4 py-3 text-sm font-medium">Application</th>
              <th className="text-right px-4 py-3 text-sm font-medium">Bytes</th>
              <th className="text-right px-4 py-3 text-sm font-medium">Packets</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {flows.map((flow) => (
              <tr key={flow.id} className="hover:bg-muted/30">
                <td className="px-4 py-3 text-sm">
                  {new Date(flow.flow_start).toLocaleTimeString()}
                </td>
                <td className="px-4 py-3 text-sm">
                  <div>{flow.src_ip}</div>
                  {flow.src_port && <div className="text-xs text-muted-foreground">:{flow.src_port}</div>}
                </td>
                <td className="px-4 py-3 text-sm">
                  <div>{flow.dst_ip}</div>
                  {flow.dst_port && <div className="text-xs text-muted-foreground">:{flow.dst_port}</div>}
                </td>
                <td className="px-4 py-3 text-sm">
                  <span className="px-2 py-0.5 bg-muted rounded text-xs">
                    {flow.protocol_name || 'Unknown'}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm">{flow.application || '-'}</td>
                <td className="px-4 py-3 text-sm text-right">{formatBytes(flow.bytes_total || 0)}</td>
                <td className="px-4 py-3 text-sm text-right">{flow.packets_total?.toLocaleString() || 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {flows.length === 0 && (
          <div className="text-center py-8 text-muted-foreground">
            No traffic flows recorded
          </div>
        )}
      </div>
    </div>
  );

  const renderAlerts = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Network Alerts</h3>
        <button
          onClick={fetchAlerts}
          className="flex items-center gap-2 px-3 py-1.5 text-sm bg-muted hover:bg-muted/80 rounded-lg"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      <div className="space-y-3">
        {alerts.map((alert) => (
          <div key={alert.id} className="bg-card border border-border rounded-lg p-4">
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-3">
                <div className={`p-2 rounded-lg ${getSeverityColor(alert.severity)}`}>
                  <AlertTriangle className="h-5 w-5" />
                </div>
                <div>
                  <div className="font-semibold">{alert.title}</div>
                  {alert.message && (
                    <div className="text-sm text-muted-foreground mt-1">{alert.message}</div>
                  )}
                  <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                    <span>Type: {alert.alert_type}</span>
                    {alert.metric_value && (
                      <span>
                        Value: {alert.metric_value.toFixed(2)}
                        {alert.threshold_value && ` (threshold: ${alert.threshold_value})`}
                      </span>
                    )}
                    <span>Triggered: {new Date(alert.triggered_at).toLocaleString()}</span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`px-2 py-1 rounded-full text-xs ${getSeverityColor(alert.severity)}`}>
                  {alert.severity}
                </span>
                {alert.status === 'active' && (
                  <>
                    <button
                      onClick={() => acknowledgeAlert(alert.id)}
                      className="px-3 py-1.5 text-sm bg-yellow-600/20 text-yellow-400 rounded hover:bg-yellow-600/30"
                    >
                      Acknowledge
                    </button>
                    <button
                      onClick={() => resolveAlert(alert.id)}
                      className="px-3 py-1.5 text-sm bg-green-600/20 text-green-400 rounded hover:bg-green-600/30"
                    >
                      Resolve
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        ))}
        {alerts.length === 0 && (
          <div className="text-center py-12 text-muted-foreground">
            <CheckCircle className="h-12 w-12 mx-auto mb-4 text-green-400 opacity-50" />
            <p>No active alerts</p>
            <p className="text-sm mt-1">All network devices are operating normally</p>
          </div>
        )}
      </div>
    </div>
  );

  const renderTopology = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Network Topology</h3>
        <button
          onClick={fetchTopology}
          className="flex items-center gap-2 px-3 py-1.5 text-sm bg-muted hover:bg-muted/80 rounded-lg"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      <div className="bg-card border border-border rounded-lg p-6 min-h-[500px]">
        {topology && topology.devices.length > 0 ? (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {topology.devices.map((device) => {
              const DeviceIcon = getDeviceTypeIcon(device.device_type);
              return (
                <div
                  key={device.id}
                  className="p-4 bg-muted/30 rounded-lg border border-border hover:border-blue-500/50 transition-colors cursor-pointer"
                  onClick={() => {
                    setSelectedDevice(device);
                    fetchDeviceInterfaces(device.id);
                    setShowDeviceModal(true);
                  }}
                >
                  <div className="flex items-center gap-3 mb-2">
                    <div className={`p-2 rounded-lg ${getStatusBg(device.status)}`}>
                      <DeviceIcon className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="font-medium text-sm">{device.display_name || device.name}</div>
                      <div className="text-xs text-muted-foreground">{device.management_ip}</div>
                    </div>
                  </div>
                  <div className="text-xs text-muted-foreground capitalize">
                    {device.device_type.replace('_', ' ')}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
            <Globe className="h-16 w-16 mb-4 opacity-50" />
            <p>No topology data available</p>
            <p className="text-sm mt-1">Add network devices to build topology</p>
          </div>
        )}
      </div>
    </div>
  );

  // Device Detail Modal
  const DeviceModal = () => {
    if (!selectedDevice) return null;
    const DeviceIcon = getDeviceTypeIcon(selectedDevice.device_type);

    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
        <div className="bg-card border border-border rounded-lg w-full max-w-4xl max-h-[90vh] overflow-auto">
          <div className="p-6 border-b border-border">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className={`p-3 rounded-lg ${getStatusBg(selectedDevice.status)}`}>
                  <DeviceIcon className="h-6 w-6" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold">
                    {selectedDevice.display_name || selectedDevice.name}
                  </h2>
                  <div className="text-sm text-muted-foreground">
                    {selectedDevice.vendor} {selectedDevice.model}
                  </div>
                </div>
              </div>
              <button
                onClick={() => {
                  setShowDeviceModal(false);
                  setSelectedDevice(null);
                }}
                className="p-2 hover:bg-muted rounded-lg"
              >
                <XCircle className="h-5 w-5" />
              </button>
            </div>
          </div>

          <div className="p-6 space-y-6">
            {/* Device Info */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-3 bg-muted/30 rounded-lg">
                <div className="text-xs text-muted-foreground mb-1">Status</div>
                <span className={`px-2 py-1 rounded text-sm ${getStatusBg(selectedDevice.status)}`}>
                  {selectedDevice.status}
                </span>
              </div>
              <div className="p-3 bg-muted/30 rounded-lg">
                <div className="text-xs text-muted-foreground mb-1">Management IP</div>
                <div className="font-medium">{selectedDevice.management_ip || '-'}</div>
              </div>
              <div className="p-3 bg-muted/30 rounded-lg">
                <div className="text-xs text-muted-foreground mb-1">Location</div>
                <div className="font-medium">{selectedDevice.location || '-'}</div>
              </div>
              <div className="p-3 bg-muted/30 rounded-lg">
                <div className="text-xs text-muted-foreground mb-1">Uptime</div>
                <div className="font-medium">{formatUptime(selectedDevice.uptime_seconds)}</div>
              </div>
            </div>

            {/* Resource Metrics */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-3 bg-muted/30 rounded-lg">
                <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
                  <Cpu className="h-4 w-4" /> CPU
                </div>
                <div className="text-2xl font-bold">
                  {selectedDevice.cpu_utilization?.toFixed(1) || '-'}%
                </div>
              </div>
              <div className="p-3 bg-muted/30 rounded-lg">
                <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
                  <HardDrive className="h-4 w-4" /> Memory
                </div>
                <div className="text-2xl font-bold">
                  {selectedDevice.memory_utilization?.toFixed(1) || '-'}%
                </div>
              </div>
              <div className="p-3 bg-muted/30 rounded-lg">
                <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
                  <Thermometer className="h-4 w-4" /> Temperature
                </div>
                <div className="text-2xl font-bold">
                  {selectedDevice.temperature_celsius?.toFixed(1) || '-'}°C
                </div>
              </div>
              <div className="p-3 bg-muted/30 rounded-lg">
                <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
                  <Network className="h-4 w-4" /> Interfaces
                </div>
                <div className="text-2xl font-bold">
                  <span className="text-green-400">{selectedDevice.interfaces_up}</span>
                  <span className="text-muted-foreground">/</span>
                  {selectedDevice.interface_count}
                </div>
              </div>
            </div>

            {/* Interfaces List */}
            <div>
              <h3 className="text-lg font-semibold mb-3">Interfaces</h3>
              <div className="bg-muted/30 rounded-lg overflow-hidden">
                <table className="w-full">
                  <thead className="bg-muted/50">
                    <tr>
                      <th className="text-left px-4 py-2 text-xs font-medium">Name</th>
                      <th className="text-left px-4 py-2 text-xs font-medium">Status</th>
                      <th className="text-left px-4 py-2 text-xs font-medium">IP</th>
                      <th className="text-right px-4 py-2 text-xs font-medium">In</th>
                      <th className="text-right px-4 py-2 text-xs font-medium">Out</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {interfaces.map((iface) => (
                      <tr key={iface.id} className="hover:bg-muted/20">
                        <td className="px-4 py-2 text-sm">{iface.display_name || iface.name}</td>
                        <td className="px-4 py-2">
                          <span className={`px-2 py-0.5 rounded text-xs ${getStatusBg(iface.oper_status)}`}>
                            {iface.oper_status}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-sm">{iface.ip_address || '-'}</td>
                        <td className="px-4 py-2 text-sm text-right">{formatBytes(iface.bytes_in)}</td>
                        <td className="px-4 py-2 text-sm text-right">{formatBytes(iface.bytes_out)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {interfaces.length === 0 && (
                  <div className="text-center py-4 text-muted-foreground text-sm">
                    No interfaces found
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // Create Device Modal
  const CreateDeviceModal = () => {
    const [formData, setFormData] = useState({
      name: '',
      display_name: '',
      device_type: 'router',
      vendor: '',
      model: '',
      management_ip: '',
      location: '',
      description: '',
      snmp_enabled: false,
      snmp_version: 'v2c',
      snmp_community: '',
    });
    const [creating, setCreating] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
      e.preventDefault();
      setCreating(true);
      try {
        const response = await fetch(`${API_BASE}/network/devices`, {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify(formData),
        });
        if (response.ok) {
          setShowCreateModal(false);
          fetchDevices();
          fetchStats();
        }
      } catch (error) {
        console.error('Failed to create device:', error);
      }
      setCreating(false);
    };

    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
        <div className="bg-card border border-border rounded-lg w-full max-w-lg">
          <div className="p-4 border-b border-border">
            <h2 className="text-lg font-semibold">Add Network Device</h2>
          </div>
          <form onSubmit={handleSubmit} className="p-4 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">Device Name *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Display Name</label>
                <input
                  type="text"
                  value={formData.display_name}
                  onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">Device Type *</label>
                <select
                  value={formData.device_type}
                  onChange={(e) => setFormData({ ...formData, device_type: e.target.value })}
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg"
                >
                  <option value="router">Router</option>
                  <option value="switch">Switch</option>
                  <option value="firewall">Firewall</option>
                  <option value="load_balancer">Load Balancer</option>
                  <option value="access_point">Access Point</option>
                  <option value="vpn_gateway">VPN Gateway</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Management IP</label>
                <input
                  type="text"
                  value={formData.management_ip}
                  onChange={(e) => setFormData({ ...formData, management_ip: e.target.value })}
                  placeholder="192.168.1.1"
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">Vendor</label>
                <input
                  type="text"
                  value={formData.vendor}
                  onChange={(e) => setFormData({ ...formData, vendor: e.target.value })}
                  placeholder="Cisco"
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Model</label>
                <input
                  type="text"
                  value={formData.model}
                  onChange={(e) => setFormData({ ...formData, model: e.target.value })}
                  placeholder="ISR 4000"
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Location</label>
              <input
                type="text"
                value={formData.location}
                onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                placeholder="Data Center A, Rack 12"
                className="w-full px-3 py-2 bg-muted border border-border rounded-lg"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Description</label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={2}
                className="w-full px-3 py-2 bg-muted border border-border rounded-lg"
              />
            </div>

            <div className="border-t border-border pt-4">
              <label className="flex items-center gap-2 mb-3">
                <input
                  type="checkbox"
                  checked={formData.snmp_enabled}
                  onChange={(e) => setFormData({ ...formData, snmp_enabled: e.target.checked })}
                  className="rounded"
                />
                <span className="text-sm font-medium">Enable SNMP Monitoring</span>
              </label>

              {formData.snmp_enabled && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-1">SNMP Version</label>
                    <select
                      value={formData.snmp_version}
                      onChange={(e) => setFormData({ ...formData, snmp_version: e.target.value })}
                      className="w-full px-3 py-2 bg-muted border border-border rounded-lg"
                    >
                      <option value="v1">v1</option>
                      <option value="v2c">v2c</option>
                      <option value="v3">v3</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Community String</label>
                    <input
                      type="password"
                      value={formData.snmp_community}
                      onChange={(e) => setFormData({ ...formData, snmp_community: e.target.value })}
                      placeholder="public"
                      className="w-full px-3 py-2 bg-muted border border-border rounded-lg"
                    />
                  </div>
                </div>
              )}
            </div>

            <div className="flex justify-end gap-3 pt-4 border-t border-border">
              <button
                type="button"
                onClick={() => setShowCreateModal(false)}
                className="px-4 py-2 text-muted-foreground hover:text-foreground"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={creating || !formData.name}
                className="px-4 py-2 bg-blue-600 text-foreground rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {creating ? 'Creating...' : 'Create Device'}
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl bg-purple-500/10">
              <Network className="w-6 h-6 text-purple-400" />
            </div>
            <div>
              <h1 className="text-base font-medium text-foreground">Network Monitoring</h1>
              <p className="text-muted-foreground text-sm">
                Monitor network devices, interfaces, traffic flows, and topology
              </p>
            </div>
          </div>
        </div>
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="h-8 w-8 animate-spin text-blue-500" />
        </div>
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
              <div className="p-3 rounded-xl bg-purple-500/10">
                <Network className="w-6 h-6 text-purple-400" />
              </div>
              <div>
                <h1 className="text-base font-medium text-foreground">Network Monitoring</h1>
                <p className="text-muted-foreground text-sm">Monitor network devices, interfaces, traffic flows, and topology</p>
              </div>
            </div>
            <button
              onClick={() => {
                fetchStats();
                fetchDevices();
                fetchAlerts();
              }}
              className="flex items-center gap-2 px-4 py-2 bg-muted hover:bg-muted/80 rounded-lg"
            >
              <RefreshCw className="h-4 w-4" />
              Refresh
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
      {/* Tabs */}
      <div className="flex gap-1 border-b border-border">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-500'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
              {tab.id === 'alerts' && alerts.length > 0 && (
                <span className="px-1.5 py-0.5 bg-red-500/20 text-red-400 rounded-full text-xs">
                  {alerts.length}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && renderOverview()}
      {activeTab === 'devices' && renderDevices()}
      {activeTab === 'interfaces' && renderInterfaces()}
      {activeTab === 'flows' && renderFlows()}
      {activeTab === 'alerts' && renderAlerts()}
      {activeTab === 'topology' && renderTopology()}
      </div>

      {/* Modals */}
      {showDeviceModal && <DeviceModal />}
      {showCreateModal && <CreateDeviceModal />}
    </div>
  );
}
