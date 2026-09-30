// SLODashboard.tsx - Refactored with shadcn/ui
import React, { useState, useEffect } from 'react';
import {
  AlertTriangle,
  BarChart3,
  CheckCircle,
  Clock,
  Eye,
  Flame,
  Plus,
  RefreshCw,
  Server,
  Trash2,
  XCircle
} from 'lucide-react';
import { API_URL } from '../config/api';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Label } from './ui/label';
import { Select } from './ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from './ui/table';

interface SLO {
  id: string;
  name: string;
  description: string | null;
  slo_type: string;
  target_percentage: number;
  target_value: number | null;
  measurement_window: string;
  current_percentage: number;
  error_budget_remaining: number;
  error_budget_consumed: number;
  is_breached: boolean;
  is_active: boolean;
  service_id: string | null;
  service_name: string | null;
  last_calculated_at: string | null;
  created_at: string;
}

interface SLOSummary {
  total: number;
  breached: number;
  at_risk: number;
  healthy: number;
  slos: SLO[];
}

interface SLIRecord {
  id: string;
  timestamp: string;
  period: string;
  total_requests: number;
  good_requests: number;
  bad_requests: number;
  sli_value: number;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  p99_latency_ms: number | null;
}

interface Service {
  id: string;
  name: string;
}

const SLODashboard: React.FC = () => {
  const [slos, setSLOs] = useState<SLO[]>([]);
  const [summary, setSummary] = useState<SLOSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [selectedSLO, setSelectedSLO] = useState<SLO | null>(null);
  const [sliRecords, setSLIRecords] = useState<SLIRecord[]>([]);
  const [burnRate, setBurnRate] = useState<{ burn_rate: number; projected_exhaustion_hours: number | null } | null>(null);
  const [services, setServices] = useState<Service[]>([]);
  const [filterType, setFilterType] = useState<string>('');
  const [filterBreached, setFilterBreached] = useState<string>('');

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    slo_type: 'availability',
    target_percentage: 9990,
    target_value: '',
    measurement_window: '30d',
    service_id: '',
    error_budget_policy: '',
    alert_threshold_warning: 5000,
    alert_threshold_critical: 8000
  });

  useEffect(() => {
    fetchSLOs();
    fetchSummary();
    fetchServices();
  }, [filterType, filterBreached]);

  const getAuthHeaders = () => ({
    'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
    'Content-Type': 'application/json'
  });

  const fetchSLOs = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (filterType) params.append('slo_type', filterType);
      if (filterBreached) params.append('is_breached', filterBreached);

      const response = await fetch(`${API_URL}/slos/?${params.toString()}`, {
        headers: getAuthHeaders()
      });

      if (!response.ok) throw new Error('Failed to fetch SLOs');

      const data = await response.json();
      setSLOs(data.slos || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load SLOs');
    } finally {
      setLoading(false);
    }
  };

  const fetchSummary = async () => {
    try {
      const response = await fetch(`${API_URL}/slos/summary`, {
        headers: getAuthHeaders()
      });

      if (!response.ok) throw new Error('Failed to fetch summary');

      const data = await response.json();
      setSummary(data);
    } catch (err) {
      console.error('Failed to fetch summary:', err);
    }
  };

  const fetchServices = async () => {
    try {
      const response = await fetch(`${API_URL}/services/`, {
        headers: getAuthHeaders()
      });

      if (response.ok) {
        const data = await response.json();
        setServices(data.services || []);
      }
    } catch (err) {
      console.error('Failed to fetch services:', err);
    }
  };

  const fetchSLODetails = async (sloId: string) => {
    try {
      const [sloRes, recordsRes, burnRes] = await Promise.all([
        fetch(`${API_URL}/slos/${sloId}`, { headers: getAuthHeaders() }),
        fetch(`${API_URL}/slos/${sloId}/records?days=7`, { headers: getAuthHeaders() }),
        fetch(`${API_URL}/slos/${sloId}/burn-rate?hours=24`, { headers: getAuthHeaders() })
      ]);

      if (sloRes.ok) {
        const sloData = await sloRes.json();
        setSelectedSLO(sloData);
      }
      if (recordsRes.ok) {
        const recordsData = await recordsRes.json();
        setSLIRecords(recordsData.records || []);
      }
      if (burnRes.ok) {
        const burnData = await burnRes.json();
        setBurnRate(burnData);
      }

      setShowDetailModal(true);
    } catch (err) {
      console.error('Failed to fetch SLO details:', err);
    }
  };

  const handleCreateSLO = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const response = await fetch(`${API_URL}/slos/`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          ...formData,
          target_value: formData.target_value ? parseInt(formData.target_value) : null,
          service_id: formData.service_id || null
        })
      });

      if (!response.ok) throw new Error('Failed to create SLO');

      setShowCreateModal(false);
      resetForm();
      fetchSLOs();
      fetchSummary();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create SLO');
    }
  };

  const handleDeleteSLO = async (sloId: string) => {
    if (!confirm('Are you sure you want to delete this SLO?')) return;

    try {
      const response = await fetch(`${API_URL}/slos/${sloId}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });

      if (!response.ok) throw new Error('Failed to delete SLO');

      fetchSLOs();
      fetchSummary();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete SLO');
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      slo_type: 'availability',
      target_percentage: 9990,
      target_value: '',
      measurement_window: '30d',
      service_id: '',
      error_budget_policy: '',
      alert_threshold_warning: 5000,
      alert_threshold_critical: 8000
    });
  };

  const formatPercentage = (value: number) => {
    return (value).toFixed(2) + '%';
  };

  const getStatusVariant = (slo: SLO): "success" | "warning" | "error" => {
    if (slo.is_breached) return 'error';
    if (slo.error_budget_remaining < 50) return 'warning';
    return 'success';
  };

  const getStatusIcon = (slo: SLO) => {
    if (slo.is_breached) return <XCircle className="w-5 h-5" />;
    if (slo.error_budget_remaining < 50) return <AlertTriangle className="w-5 h-5" />;
    return <CheckCircle className="w-5 h-5" />;
  };

  const getSLOTypeLabel = (type: string) => {
    switch (type) {
      case 'availability': return 'Availability';
      case 'latency': return 'Latency';
      case 'error_rate': return 'Error Rate';
      case 'throughput': return 'Throughput';
      default: return type;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="p-2 rounded-lg bg-secondary">
                <BarChart3 className="w-5 h-5 text-muted-foreground" />
              </div>
              <div>
                <h1 className="text-base font-medium text-foreground">SLO Dashboard</h1>
                <p className="text-muted-foreground text-sm">Monitor service level objectives and error budgets</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Button variant="outline" onClick={() => { fetchSLOs(); fetchSummary(); }}>
                <RefreshCw className="w-4 h-4 mr-2" />
                Refresh
              </Button>
              <Button onClick={() => setShowCreateModal(true)}>
                <Plus className="w-4 h-4 mr-2" />
                Create SLO
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div className="border border-border rounded-lg bg-transparent">
            <div className="p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs uppercase tracking-wider text-muted-foreground">Total SLOs</span>
                <div className="p-2 rounded-lg bg-secondary">
                  <BarChart3 className="w-4 h-4 text-muted-foreground" />
                </div>
              </div>
              <p className="text-base font-medium text-foreground">{summary.total}</p>
            </div>
          </div>
          <div className="border border-border rounded-lg bg-transparent">
            <div className="p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs uppercase tracking-wider text-muted-foreground">Healthy</span>
                <div className="p-2 rounded-lg bg-emerald-500/10">
                  <CheckCircle className="w-4 h-4 text-emerald-400" />
                </div>
              </div>
              <p className="text-base font-medium text-emerald-400">{summary.healthy}</p>
            </div>
          </div>
          <div className="border border-border rounded-lg bg-transparent">
            <div className="p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs uppercase tracking-wider text-muted-foreground">At Risk</span>
                <div className="p-2 rounded-lg bg-yellow-500/10">
                  <AlertTriangle className="w-4 h-4 text-yellow-500" />
                </div>
              </div>
              <p className="text-base font-medium text-yellow-500">{summary.at_risk}</p>
            </div>
          </div>
          <div className="border border-border rounded-lg bg-transparent">
            <div className="p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs uppercase tracking-wider text-muted-foreground">Breached</span>
                <div className="p-2 rounded-lg bg-red-500/10">
                  <XCircle className="w-4 h-4 text-red-400" />
                </div>
              </div>
              <p className="text-base font-medium text-red-400">{summary.breached}</p>
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4 mb-6">
        <Select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
        >
          <option value="">All Types</option>
          <option value="availability">Availability</option>
          <option value="latency">Latency</option>
          <option value="error_rate">Error Rate</option>
          <option value="throughput">Throughput</option>
        </Select>
        <Select
          value={filterBreached}
          onChange={(e) => setFilterBreached(e.target.value)}
        >
          <option value="">All Status</option>
          <option value="true">Breached</option>
          <option value="false">Not Breached</option>
        </Select>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-6 border border-red-500/20 bg-red-500/10 rounded-lg">
          <div className="p-4 text-red-400">
            {error}
          </div>
        </div>
      )}

      {/* SLO List */}
      <div className="space-y-4">
        {slos.map(slo => (
          <div key={slo.id} className="border border-border rounded-lg bg-transparent hover:bg-accent/50 transition-colors">
            <div className="p-6">
              <div className="flex flex-col lg:flex-row lg:items-center gap-6">
                {/* Status & Name */}
                <div className="flex items-center gap-4 lg:w-1/4">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border p-3 ${
                    getStatusVariant(slo) === 'success' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
                    getStatusVariant(slo) === 'warning' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                    'bg-red-500/10 text-red-400 border-red-500/20'
                  }`}>
                    {getStatusIcon(slo)}
                  </span>
                  <div>
                    <h3 className="text-lg font-semibold text-foreground">{slo.name}</h3>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-secondary text-muted-foreground border-border">{getSLOTypeLabel(slo.slo_type)}</span>
                      {slo.service_name && (
                        <span className="flex items-center gap-1">
                          <Server className="w-4 h-4" />
                          {slo.service_name}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Target & Current */}
                <div className="flex-1 grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wide">Target</p>
                    <p className="text-xl font-bold text-foreground">{formatPercentage(slo.target_percentage)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wide">Current</p>
                    <p className={`text-xl font-bold ${
                      slo.current_percentage >= slo.target_percentage ? 'text-green-500' : 'text-red-500'
                    }`}>
                      {formatPercentage(slo.current_percentage)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wide">Error Budget</p>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-2 bg-secondary rounded-full overflow-hidden">
                        <div
                          className={`h-full transition-all ${
                            slo.error_budget_remaining < 20 ? 'bg-red-500' :
                            slo.error_budget_remaining < 50 ? 'bg-yellow-500' : 'bg-green-500'
                          }`}
                          style={{ width: `${Math.max(0, slo.error_budget_remaining)}%` }}
                        />
                      </div>
                      <span className="text-sm text-muted-foreground">
                        {formatPercentage(slo.error_budget_remaining)}
                      </span>
                    </div>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wide">Window</p>
                    <p className="text-xl font-bold text-foreground flex items-center gap-1">
                      <Clock className="w-5 h-5 text-muted-foreground" />
                      {slo.measurement_window}
                    </p>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 lg:w-auto">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => fetchSLODetails(slo.id)}
                  >
                    <Eye className="w-5 h-5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDeleteSLO(slo.id)}
                    className="text-red-400 hover:text-red-400"
                  >
                    <Trash2 className="w-5 h-5" />
                  </Button>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {slos.length === 0 && (
        <div className="border border-border rounded-lg bg-transparent">
          <div className="p-6 pt-0 text-center py-12">
            <BarChart3 className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-foreground mb-2">No SLOs configured</h3>
            <p className="text-muted-foreground">Create your first SLO to start tracking service reliability.</p>
          </div>
        </div>
      )}

      {/* Create SLO Modal */}
      <Dialog open={showCreateModal} onOpenChange={(open) => { if (!open) { setShowCreateModal(false); resetForm(); } }}>
        <DialogContent className="max-w-2xl" onClose={() => { setShowCreateModal(false); resetForm(); }}>
          <DialogHeader>
            <DialogTitle>Create New SLO</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreateSLO} className="space-y-4 mt-4">
            <div className="space-y-2">
              <Label>Name *</Label>
              <Input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="API Availability SLO"
              />
            </div>

            <div className="space-y-2">
              <Label>Description</Label>
              <Textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={2}
                placeholder="99.9% of API requests should succeed..."
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>SLO Type *</Label>
                <Select
                  value={formData.slo_type}
                  onChange={(e) => setFormData({ ...formData, slo_type: e.target.value })}
                >
                  <option value="availability">Availability</option>
                  <option value="latency">Latency</option>
                  <option value="error_rate">Error Rate</option>
                  <option value="throughput">Throughput</option>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Service</Label>
                <Select
                  value={formData.service_id}
                  onChange={(e) => setFormData({ ...formData, service_id: e.target.value })}
                >
                  <option value="">All Services</option>
                  {services.map(s => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Target Percentage *</Label>
                <div className="relative">
                  <Input
                    type="number"
                    required
                    min={0}
                    max={10000}
                    value={formData.target_percentage}
                    onChange={(e) => setFormData({ ...formData, target_percentage: parseInt(e.target.value) })}
                  />
                  <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-muted-foreground text-sm">
                    = {(formData.target_percentage / 100).toFixed(2)}%
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">Enter in basis points (9990 = 99.90%)</p>
              </div>
              <div className="space-y-2">
                <Label>Measurement Window</Label>
                <Select
                  value={formData.measurement_window}
                  onChange={(e) => setFormData({ ...formData, measurement_window: e.target.value })}
                >
                  <option value="7d">7 days</option>
                  <option value="30d">30 days</option>
                  <option value="90d">90 days</option>
                </Select>
              </div>
            </div>

            {formData.slo_type === 'latency' && (
              <div className="space-y-2">
                <Label>Target Latency (ms)</Label>
                <Input
                  type="number"
                  value={formData.target_value}
                  onChange={(e) => setFormData({ ...formData, target_value: e.target.value })}
                  placeholder="500"
                />
              </div>
            )}

            <div className="space-y-2">
              <Label>Error Budget Policy</Label>
              <Textarea
                value={formData.error_budget_policy}
                onChange={(e) => setFormData({ ...formData, error_budget_policy: e.target.value })}
                rows={2}
                placeholder="When error budget is exhausted, freeze deployments..."
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Warning Threshold</Label>
                <div className="relative">
                  <Input
                    type="number"
                    min={0}
                    max={10000}
                    value={formData.alert_threshold_warning}
                    onChange={(e) => setFormData({ ...formData, alert_threshold_warning: parseInt(e.target.value) })}
                  />
                  <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-muted-foreground text-sm">
                    = {(formData.alert_threshold_warning / 100).toFixed(0)}% consumed
                  </span>
                </div>
              </div>
              <div className="space-y-2">
                <Label>Critical Threshold</Label>
                <div className="relative">
                  <Input
                    type="number"
                    min={0}
                    max={10000}
                    value={formData.alert_threshold_critical}
                    onChange={(e) => setFormData({ ...formData, alert_threshold_critical: parseInt(e.target.value) })}
                  />
                  <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-muted-foreground text-sm">
                    = {(formData.alert_threshold_critical / 100).toFixed(0)}% consumed
                  </span>
                </div>
              </div>
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => { setShowCreateModal(false); resetForm(); }}>
                Cancel
              </Button>
              <Button type="submit">
                Create SLO
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

        {/* SLO Detail Modal */}
        <Dialog open={showDetailModal && !!selectedSLO} onOpenChange={() => { setShowDetailModal(false); setSelectedSLO(null); }}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto" onClose={() => { setShowDetailModal(false); setSelectedSLO(null); }}>
            <DialogHeader>
              <DialogTitle>{selectedSLO?.name}</DialogTitle>
              {selectedSLO?.service_name && (
                <p className="text-muted-foreground text-sm">{selectedSLO.service_name}</p>
              )}
            </DialogHeader>

            {selectedSLO && (
              <div className="space-y-6 mt-4">
                {/* Stats Row */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="bg-accent rounded-lg p-4">
                    <p className="text-xs text-muted-foreground uppercase">Target</p>
                    <p className="text-2xl font-bold text-foreground">{formatPercentage(selectedSLO.target_percentage)}</p>
                  </div>
                  <div className="bg-accent rounded-lg p-4">
                    <p className="text-xs text-muted-foreground uppercase">Current</p>
                    <p className={`text-2xl font-bold ${
                      selectedSLO.current_percentage >= selectedSLO.target_percentage ? 'text-green-500' : 'text-red-500'
                    }`}>
                      {formatPercentage(selectedSLO.current_percentage)}
                    </p>
                  </div>
                  <div className="bg-accent rounded-lg p-4">
                    <p className="text-xs text-muted-foreground uppercase">Error Budget Left</p>
                    <p className="text-2xl font-bold text-foreground">{formatPercentage(selectedSLO.error_budget_remaining)}</p>
                  </div>
                  <div className="bg-accent rounded-lg p-4">
                    <p className="text-xs text-muted-foreground uppercase">Window</p>
                    <p className="text-2xl font-bold text-foreground">{selectedSLO.measurement_window}</p>
                  </div>
                </div>

                {/* Burn Rate */}
                {burnRate && (
                  <div className="border border-border rounded-lg bg-transparent">
                    <div className="p-6">
                      <h3 className="font-semibold flex items-center gap-4">
                        <Flame className="w-5 h-5 text-orange-500" />
                        Error Budget Burn Rate (24h)
                      </h3>
                    </div>
                    <div className="p-6 pt-0">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <p className="text-xs text-muted-foreground uppercase">Burn Rate</p>
                          <p className="text-xl font-bold text-foreground">
                            {burnRate.burn_rate.toFixed(2)} bps/hour
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground uppercase">Projected Exhaustion</p>
                          <p className={`text-xl font-bold ${
                            burnRate.projected_exhaustion_hours && burnRate.projected_exhaustion_hours < 24
                              ? 'text-red-500'
                              : burnRate.projected_exhaustion_hours && burnRate.projected_exhaustion_hours < 72
                              ? 'text-yellow-500'
                              : 'text-green-500'
                          }`}>
                            {burnRate.projected_exhaustion_hours
                              ? `${burnRate.projected_exhaustion_hours.toFixed(1)} hours`
                              : 'N/A'}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* SLI Records */}
                <div>
                  <h3 className="text-lg font-semibold text-foreground mb-4">Recent SLI Records (7 days)</h3>
                  {sliRecords.length > 0 ? (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Timestamp</TableHead>
                          <TableHead className="text-right">Total</TableHead>
                          <TableHead className="text-right">Good</TableHead>
                          <TableHead className="text-right">Bad</TableHead>
                          <TableHead className="text-right">SLI Value</TableHead>
                          {selectedSLO.slo_type === 'latency' && (
                            <>
                              <TableHead className="text-right">P50</TableHead>
                              <TableHead className="text-right">P95</TableHead>
                              <TableHead className="text-right">P99</TableHead>
                            </>
                          )}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {sliRecords.slice(0, 10).map(record => (
                          <TableRow key={record.id}>
                            <TableCell className="text-muted-foreground text-sm">
                              {new Date(record.timestamp).toLocaleString()}
                            </TableCell>
                            <TableCell className="text-right">{record.total_requests.toLocaleString()}</TableCell>
                            <TableCell className="text-right text-green-500">{record.good_requests.toLocaleString()}</TableCell>
                            <TableCell className="text-right text-red-500">{record.bad_requests.toLocaleString()}</TableCell>
                            <TableCell className={`text-right font-semibold ${
                              record.sli_value >= selectedSLO.target_percentage ? 'text-green-500' : 'text-red-500'
                            }`}>
                              {formatPercentage(record.sli_value)}
                            </TableCell>
                            {selectedSLO.slo_type === 'latency' && (
                              <>
                                <TableCell className="text-right">{record.p50_latency_ms || '-'}ms</TableCell>
                                <TableCell className="text-right">{record.p95_latency_ms || '-'}ms</TableCell>
                                <TableCell className="text-right">{record.p99_latency_ms || '-'}ms</TableCell>
                              </>
                            )}
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  ) : (
                    <p className="text-muted-foreground text-center py-8">No SLI records available</p>
                  )}
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
};

export default SLODashboard;
