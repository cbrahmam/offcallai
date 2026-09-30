// frontend/oncall-frontend/src/components/CustomDashboards.tsx
import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity,
  AlertCircle,
  BarChart3,
  Box,
  ChevronDown,
  Clock,
  Copy,
  Download,
  Edit2,
  Eye,
  FileText,
  Gauge,
  LayoutGrid,
  LineChart,
  Plus,
  RefreshCw,
  Save,
  Settings,
  Table,
  Trash2,
  X
} from 'lucide-react';
import {
  LineChart as ReLineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts';
// Magic UI removed for Vercel-style

import { API_URL as API_BASE_URL } from '../config/api';

interface Widget {
  id: string;
  dashboard_id: string;
  title: string;
  description?: string;
  widget_type: string;
  position_x: number;
  position_y: number;
  width: number;
  height: number;
  data_source: string;
  query_config: Record<string, any>;
  display_config: Record<string, any>;
  time_range_override?: string;
  display_order: number;
}

interface Dashboard {
  id: string;
  name: string;
  description?: string;
  slug?: string;
  is_default: boolean;
  is_shared: boolean;
  layout: string;
  columns: number;
  refresh_interval: number;
  default_time_range: string;
  theme: string;
  tags: string[];
  widgets: Widget[];
  created_at: string;
  updated_at: string;
}

interface DashboardListItem {
  id: string;
  name: string;
  description?: string;
  slug?: string;
  is_default: boolean;
  is_shared: boolean;
  widget_count: number;
  tags: string[];
  created_at: string;
  updated_at: string;
}

interface WidgetData {
  widget_id: string;
  series: Array<{
    name: string;
    data: Array<{ timestamp: string; value: number }>;
  }>;
  time_range: { start: string; end: string };
}

const WIDGET_TYPES = [
  { id: 'line_chart', label: 'Line Chart', icon: LineChart },
  { id: 'area_chart', label: 'Area Chart', icon: Activity },
  { id: 'bar_chart', label: 'Bar Chart', icon: BarChart3 },
  { id: 'gauge', label: 'Gauge', icon: Gauge },
  { id: 'stat', label: 'Single Stat', icon: Box },
  { id: 'table', label: 'Table', icon: Table },
  { id: 'log_stream', label: 'Log Stream', icon: FileText },
  { id: 'alert_list', label: 'Alert List', icon: AlertCircle },
];

const DATA_SOURCES = [
  { id: 'metrics', label: 'Metrics' },
  { id: 'logs', label: 'Logs' },
  { id: 'traces', label: 'Traces' },
  { id: 'alerts', label: 'Alerts' },
];

const TIME_RANGES = [
  { id: '15m', label: 'Last 15 minutes' },
  { id: '1h', label: 'Last 1 hour' },
  { id: '6h', label: 'Last 6 hours' },
  { id: '24h', label: 'Last 24 hours' },
  { id: '7d', label: 'Last 7 days' },
  { id: '30d', label: 'Last 30 days' },
];

interface CustomDashboardsProps {
  isDemoMode?: boolean;
}

export default function CustomDashboards({ isDemoMode = false }: CustomDashboardsProps) {
  const [dashboards, setDashboards] = useState<DashboardListItem[]>([]);
  const [selectedDashboard, setSelectedDashboard] = useState<Dashboard | null>(null);
  const [widgetData, setWidgetData] = useState<Record<string, WidgetData>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showWidgetModal, setShowWidgetModal] = useState(false);
  const [editingWidget, setEditingWidget] = useState<Widget | null>(null);
  const [isEditMode, setIsEditMode] = useState(false);

  // New dashboard form
  const [newDashboard, setNewDashboard] = useState({
    name: '',
    description: '',
    default_time_range: '1h',
    refresh_interval: 60,
    columns: 12,
    is_shared: true
  });

  // New widget form
  const [newWidget, setNewWidget] = useState({
    title: '',
    description: '',
    widget_type: 'line_chart',
    data_source: 'metrics',
    width: 4,
    height: 3,
    query_config: { metrics: ['cpu.usage'] },
    display_config: {}
  });

  const getAuthHeaders = useCallback(() => {
    const token = localStorage.getItem('access_token');
    return {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  }, []);

  const fetchDashboards = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/dashboards/`, {
        headers: getAuthHeaders(),
      });

      if (!response.ok) throw new Error('Failed to fetch dashboards');

      const data = await response.json();
      setDashboards(data.dashboards || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch dashboards');
    } finally {
      setLoading(false);
    }
  }, [getAuthHeaders]);

  const fetchDashboard = useCallback(async (dashboardId: string) => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/dashboards/${dashboardId}`, {
        headers: getAuthHeaders(),
      });

      if (!response.ok) throw new Error('Failed to fetch dashboard');

      const data = await response.json();
      setSelectedDashboard(data);

      // Fetch widget data
      for (const widget of data.widgets) {
        fetchWidgetData(widget.id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch dashboard');
    } finally {
      setLoading(false);
    }
  }, [getAuthHeaders]);

  const fetchWidgetData = useCallback(async (widgetId: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/dashboards/widgets/${widgetId}/data`, {
        headers: getAuthHeaders(),
      });

      if (!response.ok) return;

      const data = await response.json();
      setWidgetData(prev => ({ ...prev, [widgetId]: data }));
    } catch (err) {
      console.error('Failed to fetch widget data:', err);
    }
  }, [getAuthHeaders]);

  const createDashboard = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/dashboards/`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(newDashboard),
      });

      if (!response.ok) throw new Error('Failed to create dashboard');

      const data = await response.json();
      setShowCreateModal(false);
      setNewDashboard({
        name: '',
        description: '',
        default_time_range: '1h',
        refresh_interval: 60,
        columns: 12,
        is_shared: true
      });
      fetchDashboards();
      fetchDashboard(data.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create dashboard');
    }
  };

  const deleteDashboard = async (dashboardId: string) => {
    if (!confirm('Are you sure you want to delete this dashboard?')) return;

    try {
      const response = await fetch(`${API_BASE_URL}/dashboards/${dashboardId}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });

      if (!response.ok) throw new Error('Failed to delete dashboard');

      setSelectedDashboard(null);
      fetchDashboards();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete dashboard');
    }
  };

  const addWidget = async () => {
    if (!selectedDashboard) return;

    try {
      // Calculate next position
      const maxY = Math.max(0, ...selectedDashboard.widgets.map(w => w.position_y + w.height));

      const response = await fetch(`${API_BASE_URL}/dashboards/${selectedDashboard.id}/widgets`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          ...newWidget,
          position_x: 0,
          position_y: maxY,
          display_order: selectedDashboard.widgets.length
        }),
      });

      if (!response.ok) throw new Error('Failed to add widget');

      setShowWidgetModal(false);
      setNewWidget({
        title: '',
        description: '',
        widget_type: 'line_chart',
        data_source: 'metrics',
        width: 4,
        height: 3,
        query_config: { metrics: ['cpu.usage'] },
        display_config: {}
      });
      fetchDashboard(selectedDashboard.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add widget');
    }
  };

  const deleteWidget = async (widgetId: string) => {
    if (!confirm('Are you sure you want to delete this widget?')) return;

    try {
      const response = await fetch(`${API_BASE_URL}/dashboards/widgets/${widgetId}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });

      if (!response.ok) throw new Error('Failed to delete widget');

      if (selectedDashboard) {
        fetchDashboard(selectedDashboard.id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete widget');
    }
  };

  useEffect(() => {
    fetchDashboards();
  }, [fetchDashboards]);

  // Auto-refresh
  useEffect(() => {
    if (!selectedDashboard || selectedDashboard.refresh_interval === 0) return;

    const interval = setInterval(() => {
      for (const widget of selectedDashboard.widgets) {
        fetchWidgetData(widget.id);
      }
    }, selectedDashboard.refresh_interval * 1000);

    return () => clearInterval(interval);
  }, [selectedDashboard, fetchWidgetData]);

  const renderWidget = (widget: Widget) => {
    const data = widgetData[widget.id];
    const chartData = data?.series?.[0]?.data?.map(d => ({
      time: new Date(d.timestamp).toLocaleTimeString(),
      value: d.value
    })) || [];

    const gridStyle = {
      gridColumn: `span ${widget.width}`,
      gridRow: `span ${widget.height}`,
    };

    return (
      <div
        key={widget.id}
        style={gridStyle}
        className="bg-accent rounded-lg border border-border overflow-hidden"
      >
        <div className="flex items-center justify-between px-4 py-2 border-b border-border">
          <h3 className="font-medium text-foreground truncate">{widget.title}</h3>
          {isEditMode && (
            <div className="flex items-center gap-1">
              <button
                onClick={() => deleteWidget(widget.id)}
                className="p-1 text-muted-foreground hover:text-red-400"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          )}
        </div>
        <div className="p-4 h-full" style={{ minHeight: widget.height * 80 }}>
          {widget.widget_type === 'line_chart' || widget.widget_type === 'area_chart' ? (
            <ResponsiveContainer width="100%" height={widget.height * 60}>
              {widget.widget_type === 'line_chart' ? (
                <ReLineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="time" stroke="#9CA3AF" tick={{ fontSize: 10 }} />
                  <YAxis stroke="#9CA3AF" tick={{ fontSize: 10 }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
                    labelStyle={{ color: '#9CA3AF' }}
                  />
                  <Line
                    type="monotone"
                    dataKey="value"
                    stroke="#3B82F6"
                    strokeWidth={2}
                    dot={false}
                  />
                </ReLineChart>
              ) : (
                <AreaChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="time" stroke="#9CA3AF" tick={{ fontSize: 10 }} />
                  <YAxis stroke="#9CA3AF" tick={{ fontSize: 10 }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
                    labelStyle={{ color: '#9CA3AF' }}
                  />
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke="#3B82F6"
                    fill="#3B82F6"
                    fillOpacity={0.3}
                  />
                </AreaChart>
              )}
            </ResponsiveContainer>
          ) : widget.widget_type === 'bar_chart' ? (
            <ResponsiveContainer width="100%" height={widget.height * 60}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="time" stroke="#9CA3AF" tick={{ fontSize: 10 }} />
                <YAxis stroke="#9CA3AF" tick={{ fontSize: 10 }} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
                />
                <Bar dataKey="value" fill="#3B82F6" />
              </BarChart>
            </ResponsiveContainer>
          ) : widget.widget_type === 'stat' ? (
            <div className="flex flex-col items-center justify-center h-full">
              <p className="text-4xl font-bold text-foreground">
                {chartData[chartData.length - 1]?.value?.toFixed(2) || '-'}
              </p>
              {widget.description && (
                <p className="text-sm text-muted-foreground mt-2">{widget.description}</p>
              )}
            </div>
          ) : widget.widget_type === 'gauge' ? (
            <div className="flex flex-col items-center justify-center h-full">
              <div className="relative w-32 h-32">
                <svg className="w-full h-full" viewBox="0 0 100 100">
                  <circle
                    cx="50"
                    cy="50"
                    r="40"
                    fill="none"
                    stroke="#374151"
                    strokeWidth="10"
                  />
                  <circle
                    cx="50"
                    cy="50"
                    r="40"
                    fill="none"
                    stroke="#3B82F6"
                    strokeWidth="10"
                    strokeDasharray={`${(chartData[chartData.length - 1]?.value || 0) * 2.51} 251`}
                    strokeLinecap="round"
                    transform="rotate(-90 50 50)"
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-2xl font-bold text-foreground">
                    {chartData[chartData.length - 1]?.value?.toFixed(0) || 0}%
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              <p>Widget type: {widget.widget_type}</p>
            </div>
          )}
        </div>
      </div>
    );
  };

  const renderDashboardList = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-medium text-foreground">Your Dashboards</h2>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground hover:bg-white/90 rounded-lg text-sm"
        >
          <Plus className="h-4 w-4" />
          New Dashboard
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {dashboards.map((dashboard) => (
          <div
            key={dashboard.id}
            onClick={() => fetchDashboard(dashboard.id)}
            className="p-4 bg-accent rounded-lg border border-border hover:border-white/20 cursor-pointer transition-colors"
          >
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-medium text-foreground">{dashboard.name}</h3>
              <LayoutGrid className="h-5 w-5 text-muted-foreground" />
            </div>
            {dashboard.description && (
              <p className="text-sm text-muted-foreground mb-3 line-clamp-2">{dashboard.description}</p>
            )}
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>{dashboard.widget_count} widgets</span>
              <span>{new Date(dashboard.updated_at).toLocaleDateString()}</span>
            </div>
            {dashboard.tags.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {dashboard.tags.map((tag) => (
                  <span key={tag} className="px-2 py-0.5 bg-secondary rounded text-xs text-foreground">
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}

        {dashboards.length === 0 && !loading && (
          <div className="col-span-full py-12 text-center text-muted-foreground">
            <LayoutGrid className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>No dashboards yet</p>
            <p className="text-sm mt-1">Create your first custom dashboard to get started</p>
          </div>
        )}
      </div>
    </div>
  );

  const renderDashboardView = () => {
    if (!selectedDashboard) return null;

    return (
      <div className="space-y-4">
        {/* Dashboard header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setSelectedDashboard(null)}
              className="text-muted-foreground hover:text-foreground"
            >
              <ChevronDown className="h-5 w-5 rotate-90" />
            </button>
            <div>
              <h2 className="text-base font-medium text-foreground">{selectedDashboard.name}</h2>
              {selectedDashboard.description && (
                <p className="text-sm text-muted-foreground">{selectedDashboard.description}</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <Clock className="h-3 w-3" />
              {TIME_RANGES.find(t => t.id === selectedDashboard.default_time_range)?.label}
            </span>
            <button
              onClick={() => fetchDashboard(selectedDashboard.id)}
              className="p-2 text-muted-foreground hover:text-foreground hover:bg-secondary rounded-lg"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
            <button
              onClick={() => setIsEditMode(!isEditMode)}
              className={`p-2 rounded-lg ${isEditMode ? 'bg-secondary text-foreground' : 'text-muted-foreground hover:text-foreground hover:bg-accent'}`}
            >
              <Edit2 className="h-4 w-4" />
            </button>
            {isEditMode && (
              <button
                onClick={() => setShowWidgetModal(true)}
                className="flex items-center gap-2 px-3 py-2 bg-primary text-primary-foreground hover:bg-white/90 rounded-lg text-sm"
              >
                <Plus className="h-4 w-4" />
                Add Widget
              </button>
            )}
            <button
              onClick={() => deleteDashboard(selectedDashboard.id)}
              className="p-2 text-muted-foreground hover:text-red-400 hover:bg-secondary rounded-lg"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Widgets grid */}
        <div
          className="grid gap-4"
          style={{ gridTemplateColumns: `repeat(${selectedDashboard.columns}, minmax(0, 1fr))` }}
        >
          {selectedDashboard.widgets.map(renderWidget)}
        </div>

        {selectedDashboard.widgets.length === 0 && (
          <div className="py-12 text-center text-muted-foreground border-2 border-dashed border-border rounded-lg">
            <LayoutGrid className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>No widgets yet</p>
            <p className="text-sm mt-1">Click "Add Widget" to start building your dashboard</p>
            <button
              onClick={() => setShowWidgetModal(true)}
              className="mt-4 px-4 py-2 bg-primary text-primary-foreground hover:bg-white/90 rounded-lg text-sm"
            >
              Add Widget
            </button>
          </div>
        )}
      </div>
    );
  };

  const renderCreateModal = () => (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-lg bg-background rounded-lg border border-border">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h3 className="text-base font-medium text-foreground">Create Dashboard</h3>
          <button onClick={() => setShowCreateModal(false)} className="text-muted-foreground hover:text-foreground">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">Name</label>
            <input
              type="text"
              value={newDashboard.name}
              onChange={(e) => setNewDashboard({ ...newDashboard, name: e.target.value })}
              className="w-full px-4 py-2 bg-secondary border border-border rounded-lg text-foreground focus:outline-none focus:ring-1 focus:ring-white/10"
              placeholder="My Dashboard"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">Description</label>
            <textarea
              value={newDashboard.description}
              onChange={(e) => setNewDashboard({ ...newDashboard, description: e.target.value })}
              className="w-full px-4 py-2 bg-secondary border border-border rounded-lg text-foreground focus:outline-none focus:ring-1 focus:ring-white/10"
              placeholder="Optional description..."
              rows={2}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Default Time Range</label>
              <select
                value={newDashboard.default_time_range}
                onChange={(e) => setNewDashboard({ ...newDashboard, default_time_range: e.target.value })}
                className="w-full px-4 py-2 bg-secondary border border-border rounded-lg text-foreground focus:outline-none focus:ring-1 focus:ring-white/10"
              >
                {TIME_RANGES.map((tr) => (
                  <option key={tr.id} value={tr.id}>{tr.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Refresh Interval</label>
              <select
                value={newDashboard.refresh_interval}
                onChange={(e) => setNewDashboard({ ...newDashboard, refresh_interval: parseInt(e.target.value) })}
                className="w-full px-4 py-2 bg-secondary border border-border rounded-lg text-foreground focus:outline-none focus:ring-1 focus:ring-white/10"
              >
                <option value={0}>Manual</option>
                <option value={30}>30 seconds</option>
                <option value={60}>1 minute</option>
                <option value={300}>5 minutes</option>
              </select>
            </div>
          </div>
          <div className="flex items-center">
            <input
              type="checkbox"
              id="is_shared"
              checked={newDashboard.is_shared}
              onChange={(e) => setNewDashboard({ ...newDashboard, is_shared: e.target.checked })}
              className="mr-2"
            />
            <label htmlFor="is_shared" className="text-sm text-foreground">Share with team members</label>
          </div>
        </div>
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-border">
          <button
            onClick={() => setShowCreateModal(false)}
            className="px-4 py-2 text-muted-foreground hover:text-foreground"
          >
            Cancel
          </button>
          <button
            onClick={createDashboard}
            disabled={!newDashboard.name}
            className="px-4 py-2 bg-primary text-primary-foreground hover:bg-white/90 disabled:opacity-50 rounded-lg text-foreground"
          >
            Create Dashboard
          </button>
        </div>
      </div>
    </div>
  );

  const renderWidgetModal = () => (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-lg bg-background rounded-lg border border-border">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h3 className="text-base font-medium text-foreground">Add Widget</h3>
          <button onClick={() => setShowWidgetModal(false)} className="text-muted-foreground hover:text-foreground">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">Title</label>
            <input
              type="text"
              value={newWidget.title}
              onChange={(e) => setNewWidget({ ...newWidget, title: e.target.value })}
              className="w-full px-4 py-2 bg-secondary border border-border rounded-lg text-foreground focus:outline-none focus:ring-1 focus:ring-white/10"
              placeholder="CPU Usage"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">Widget Type</label>
            <div className="grid grid-cols-4 gap-2">
              {WIDGET_TYPES.map((type) => {
                const Icon = type.icon;
                return (
                  <button
                    key={type.id}
                    onClick={() => setNewWidget({ ...newWidget, widget_type: type.id })}
                    className={`flex flex-col items-center gap-1 p-3 rounded-lg border transition-colors ${
                      newWidget.widget_type === type.id
                        ? 'border-white bg-secondary'
                        : 'border-border hover:border-white/20'
                    }`}
                  >
                    <Icon className="h-5 w-5" />
                    <span className="text-xs">{type.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">Data Source</label>
            <select
              value={newWidget.data_source}
              onChange={(e) => setNewWidget({ ...newWidget, data_source: e.target.value })}
              className="w-full px-4 py-2 bg-secondary border border-border rounded-lg text-foreground focus:outline-none focus:ring-1 focus:ring-white/10"
            >
              {DATA_SOURCES.map((ds) => (
                <option key={ds.id} value={ds.id}>{ds.label}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Width (columns)</label>
              <select
                value={newWidget.width}
                onChange={(e) => setNewWidget({ ...newWidget, width: parseInt(e.target.value) })}
                className="w-full px-4 py-2 bg-secondary border border-border rounded-lg text-foreground focus:outline-none focus:ring-1 focus:ring-white/10"
              >
                {[2, 3, 4, 6, 8, 12].map((w) => (
                  <option key={w} value={w}>{w}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Height (rows)</label>
              <select
                value={newWidget.height}
                onChange={(e) => setNewWidget({ ...newWidget, height: parseInt(e.target.value) })}
                className="w-full px-4 py-2 bg-secondary border border-border rounded-lg text-foreground focus:outline-none focus:ring-1 focus:ring-white/10"
              >
                {[2, 3, 4, 5, 6].map((h) => (
                  <option key={h} value={h}>{h}</option>
                ))}
              </select>
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-border">
          <button
            onClick={() => setShowWidgetModal(false)}
            className="px-4 py-2 text-muted-foreground hover:text-foreground"
          >
            Cancel
          </button>
          <button
            onClick={addWidget}
            disabled={!newWidget.title}
            className="px-4 py-2 bg-primary text-primary-foreground hover:bg-white/90 disabled:opacity-50 rounded-lg text-foreground"
          >
            Add Widget
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="p-2.5 rounded-lg bg-secondary">
                <LayoutGrid className="w-5 h-5 text-muted-foreground" />
              </div>
              <div>
                <h1 className="text-base font-medium text-foreground">Custom Dashboards</h1>
                <p className="text-muted-foreground text-sm">Create personalized dashboards to visualize your monitoring data</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* Loading state */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="h-8 w-8 animate-spin text-blue-500" />
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="p-4 bg-red-500/20 border border-red-500/30 rounded-lg text-red-400 mb-4">
            {error}
          </div>
        )}

        {/* Content */}
        {!loading && !error && (
          <>
            {selectedDashboard ? renderDashboardView() : renderDashboardList()}
          </>
        )}
      </div>

      {/* Modals */}
      {showCreateModal && renderCreateModal()}
      {showWidgetModal && renderWidgetModal()}
    </div>
  );
}
