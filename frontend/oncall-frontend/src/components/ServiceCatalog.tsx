// frontend/oncall-frontend/src/components/ServiceCatalog.tsx
import React, { useState, useEffect } from 'react';
import {
  AlertTriangle,
  BarChart3,
  CheckCircle,
  FileText,
  Link,
  Plus,
  RefreshCw,
  Search,
  Server,
  Settings,
  Share2,
  Tag,
  Trash2,
  User,
  Users,
  XCircle
} from 'lucide-react';
import { API_URL } from '../config/api';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Label } from './ui/label';
import { Select } from './ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';

interface Service {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  tier: string;
  owner_id: string | null;
  owner_name: string | null;
  team_id: string | null;
  team_name: string | null;
  repository_url: string | null;
  documentation_url: string | null;
  dashboard_url: string | null;
  health_check_url: string | null;
  health_status: string;
  tags: string[];
  environment: string;
  service_type: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface User {
  id: string;
  full_name: string;
  email: string;
}

interface Team {
  id: string;
  name: string;
}

interface DependencyGraphData {
  nodes: { id: string; name: string; tier: string; health_status: string }[];
  edges: { from: string; to: string; type: string }[];
}

const ServiceCatalog: React.FC = () => {
  const [services, setServices] = useState<Service[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTier, setSelectedTier] = useState<string>('');
  const [selectedEnvironment, setSelectedEnvironment] = useState<string>('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showDependencyGraph, setShowDependencyGraph] = useState(false);
  const [selectedService, setSelectedService] = useState<Service | null>(null);
  const [dependencyGraph, setDependencyGraph] = useState<DependencyGraphData | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    slug: '',
    description: '',
    tier: 'tier3',
    owner_id: '',
    team_id: '',
    repository_url: '',
    documentation_url: '',
    dashboard_url: '',
    health_check_url: '',
    tags: '',
    environment: 'production',
    service_type: ''
  });

  useEffect(() => {
    fetchServices();
    fetchUsersAndTeams();
  }, [selectedTier, selectedEnvironment]);

  const getAuthHeaders = () => ({
    'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
    'Content-Type': 'application/json'
  });

  const fetchServices = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (selectedTier) params.append('tier', selectedTier);
      if (selectedEnvironment) params.append('environment', selectedEnvironment);

      const response = await fetch(`${API_URL}/services/?${params.toString()}`, {
        headers: getAuthHeaders()
      });

      if (!response.ok) throw new Error('Failed to fetch services');

      const data = await response.json();
      setServices(data.services || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load services');
    } finally {
      setLoading(false);
    }
  };

  const fetchUsersAndTeams = async () => {
    try {
      const [usersRes, teamsRes] = await Promise.all([
        fetch(`${API_URL}/users/`, { headers: getAuthHeaders() }),
        fetch(`${API_URL}/organizations/teams`, { headers: getAuthHeaders() })
      ]);

      if (usersRes.ok) {
        const usersData = await usersRes.json();
        setUsers(usersData.users || []);
      }
      if (teamsRes.ok) {
        const teamsData = await teamsRes.json();
        setTeams(teamsData.teams || []);
      }
    } catch (err) {
      console.error('Failed to fetch users/teams:', err);
    }
  };

  const fetchDependencyGraph = async () => {
    try {
      const response = await fetch(`${API_URL}/services/graph`, {
        headers: getAuthHeaders()
      });

      if (!response.ok) throw new Error('Failed to fetch dependency graph');

      const data = await response.json();
      setDependencyGraph(data);
      setShowDependencyGraph(true);
    } catch (err) {
      console.error('Failed to fetch dependency graph:', err);
    }
  };

  const handleCreateService = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const response = await fetch(`${API_URL}/services/`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          ...formData,
          tags: formData.tags.split(',').map(t => t.trim()).filter(Boolean),
          owner_id: formData.owner_id || null,
          team_id: formData.team_id || null
        })
      });

      if (!response.ok) throw new Error('Failed to create service');

      setShowCreateModal(false);
      resetForm();
      fetchServices();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create service');
    }
  };

  const handleDeleteService = async (serviceId: string) => {
    if (!confirm('Are you sure you want to delete this service?')) return;

    try {
      const response = await fetch(`${API_URL}/services/${serviceId}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });

      if (!response.ok) throw new Error('Failed to delete service');
      fetchServices();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete service');
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      slug: '',
      description: '',
      tier: 'tier3',
      owner_id: '',
      team_id: '',
      repository_url: '',
      documentation_url: '',
      dashboard_url: '',
      health_check_url: '',
      tags: '',
      environment: 'production',
      service_type: ''
    });
  };

  const getHealthBadgeVariant = (status: string): 'success' | 'warning' | 'error' | 'default' => {
    switch (status) {
      case 'healthy': return 'success';
      case 'degraded': return 'warning';
      case 'down': return 'error';
      default: return 'default';
    }
  };

  const getHealthStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy': return <CheckCircle className="w-4 h-4" />;
      case 'degraded': return <AlertTriangle className="w-4 h-4" />;
      case 'down': return <XCircle className="w-4 h-4" />;
      default: return <RefreshCw className="w-4 h-4" />;
    }
  };

  const getTierBadgeVariant = (tier: string): 'error' | 'warning' | 'info' | 'default' => {
    switch (tier) {
      case 'tier1': return 'error';
      case 'tier2': return 'warning';
      case 'tier3': return 'info';
      default: return 'default';
    }
  };

  const filteredServices = services.filter(service => {
    const matchesSearch = service.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         service.slug.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         (service.description?.toLowerCase().includes(searchTerm.toLowerCase()) || false);
    return matchesSearch;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
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
              <div className="p-3 rounded-xl bg-violet-500/10">
                <Server className="w-6 h-6 text-violet-400" />
              </div>
              <div>
                <h1 className="text-base font-medium text-foreground">Service Catalog</h1>
                <p className="text-muted-foreground text-sm">Manage your services and dependencies</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Button
                onClick={fetchDependencyGraph}
                variant="outline"
                className="gap-2 border-border text-foreground hover:bg-accent"
              >
                <Share2 className="w-4 h-4" />
                Dependency Graph
              </Button>
              <Button
                onClick={() => setShowCreateModal(true)}
                className="gap-2 bg-primary text-primary-foreground hover:bg-white/90"
              >
                <Plus className="w-4 h-4" />
                Add Service
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* Filters */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search services..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
        <Select
          value={selectedTier}
          onChange={(e) => setSelectedTier(e.target.value)}
        >
          <option value="">All Tiers</option>
          <option value="tier1">Tier 1 (Critical)</option>
          <option value="tier2">Tier 2 (Important)</option>
          <option value="tier3">Tier 3 (Standard)</option>
        </Select>
        <Select
          value={selectedEnvironment}
          onChange={(e) => setSelectedEnvironment(e.target.value)}
        >
          <option value="">All Environments</option>
          <option value="production">Production</option>
          <option value="staging">Staging</option>
          <option value="development">Development</option>
        </Select>
        <Button
          onClick={fetchServices}
          variant="secondary"
          className="gap-2"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div className="border border-border rounded-lg bg-transparent p-6">
          <div className="text-base font-medium text-foreground">{services.length}</div>
          <div className="text-muted-foreground text-sm">Total Services</div>
        </div>
        <div className="border border-border rounded-lg bg-transparent p-6">
          <div className="text-base font-medium text-emerald-400">
            {services.filter(s => s.health_status === 'healthy').length}
          </div>
          <div className="text-muted-foreground text-sm">Healthy</div>
        </div>
        <div className="border border-border rounded-lg bg-transparent p-6">
          <div className="text-base font-medium text-yellow-400">
            {services.filter(s => s.health_status === 'degraded').length}
          </div>
          <div className="text-muted-foreground text-sm">Degraded</div>
        </div>
        <div className="border border-border rounded-lg bg-transparent p-6">
          <div className="text-base font-medium text-red-400">
            {services.filter(s => s.tier === 'tier1').length}
          </div>
          <div className="text-muted-foreground text-sm">Critical (Tier 1)</div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-destructive/10 border border-destructive/30 text-red-400 px-4 py-3 rounded-lg mb-6">
          {error}
        </div>
      )}

      {/* Services Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredServices.map(service => (
          <div key={service.id} className="border border-border rounded-lg bg-transparent hover:bg-accent/50 transition-colors overflow-hidden">
            <div className="p-6">
              {/* Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-secondary">
                    {getHealthStatusIcon(service.health_status)}
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-foreground">{service.name}</h3>
                    <p className="text-muted-foreground text-sm">{service.slug}</p>
                  </div>
                </div>
                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${
                  getTierBadgeVariant(service.tier) === 'error' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                  getTierBadgeVariant(service.tier) === 'warning' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                  getTierBadgeVariant(service.tier) === 'info' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' :
                  'bg-secondary text-muted-foreground border-border'
                }`}>
                  {service.tier.toUpperCase()}
                </span>
              </div>

              {/* Description */}
              {service.description && (
                <p className="text-muted-foreground text-sm mb-4 line-clamp-2">{service.description}</p>
              )}

              {/* Tags */}
              {service.tags && service.tags.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-4">
                  {service.tags.slice(0, 3).map((tag, idx) => (
                    <span key={idx} className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-secondary text-muted-foreground border-border text-xs">
                      {tag}
                    </span>
                  ))}
                  {service.tags.length > 3 && (
                    <span className="px-2 py-1 text-xs text-muted-foreground">+{service.tags.length - 3} more</span>
                  )}
                </div>
              )}

              {/* Metadata */}
              <div className="space-y-2 mb-4">
                {service.owner_name && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <User className="w-4 h-4" />
                    <span>{service.owner_name}</span>
                  </div>
                )}
                {service.team_name && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Users className="w-4 h-4" />
                    <span>{service.team_name}</span>
                  </div>
                )}
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Tag className="w-4 h-4" />
                  <span className="capitalize">{service.environment}</span>
                  {service.service_type && <span>/ {service.service_type}</span>}
                </div>
              </div>

              {/* Quick Links */}
              <div className="flex items-center gap-2 pt-4 border-t border-border">
                {service.repository_url && (
                  <a
                    href={service.repository_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-2 text-muted-foreground hover:text-foreground hover:bg-accent rounded transition-colors"
                    title="Repository"
                  >
                    <Link className="w-4 h-4" />
                  </a>
                )}
                {service.documentation_url && (
                  <a
                    href={service.documentation_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-2 text-muted-foreground hover:text-foreground hover:bg-accent rounded transition-colors"
                    title="Documentation"
                  >
                    <FileText className="w-4 h-4" />
                  </a>
                )}
                {service.dashboard_url && (
                  <a
                    href={service.dashboard_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-2 text-muted-foreground hover:text-foreground hover:bg-accent rounded transition-colors"
                    title="Dashboard"
                  >
                    <BarChart3 className="w-4 h-4" />
                  </a>
                )}
                <div className="flex-1" />
                <button
                  onClick={() => setSelectedService(service)}
                  className="p-2 text-muted-foreground hover:text-foreground hover:bg-accent rounded transition-colors"
                  title="View Details"
                >
                  <Settings className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleDeleteService(service.id)}
                  className="p-2 text-muted-foreground hover:text-red-400 hover:bg-accent rounded transition-colors"
                  title="Delete"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {filteredServices.length === 0 && (
        <div className="text-center py-12">
          <Server className="w-16 h-16 text-muted-foreground/50 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-muted-foreground mb-2">No services found</h3>
          <p className="text-muted-foreground/70">Add your first service to get started.</p>
        </div>
      )}

      {/* Create Service Modal */}
      <Dialog open={showCreateModal} onOpenChange={setShowCreateModal}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Add New Service</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreateService} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="name">Name *</Label>
                <Input
                  id="name"
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => {
                    setFormData({
                      ...formData,
                      name: e.target.value,
                      slug: e.target.value.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '')
                    });
                  }}
                  placeholder="Payment Service"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="slug">Slug *</Label>
                <Input
                  id="slug"
                  type="text"
                  required
                  value={formData.slug}
                  onChange={(e) => setFormData({ ...formData, slug: e.target.value })}
                  placeholder="payment-service"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={3}
                placeholder="Handles all payment processing..."
              />
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="tier">Tier</Label>
                <Select
                  id="tier"
                  value={formData.tier}
                  onChange={(e) => setFormData({ ...formData, tier: e.target.value })}
                >
                  <option value="tier1">Tier 1 (Critical)</option>
                  <option value="tier2">Tier 2 (Important)</option>
                  <option value="tier3">Tier 3 (Standard)</option>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="environment">Environment</Label>
                <Select
                  id="environment"
                  value={formData.environment}
                  onChange={(e) => setFormData({ ...formData, environment: e.target.value })}
                >
                  <option value="production">Production</option>
                  <option value="staging">Staging</option>
                  <option value="development">Development</option>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="service_type">Type</Label>
                <Select
                  id="service_type"
                  value={formData.service_type}
                  onChange={(e) => setFormData({ ...formData, service_type: e.target.value })}
                >
                  <option value="">Select type</option>
                  <option value="api">API</option>
                  <option value="web">Web App</option>
                  <option value="worker">Worker</option>
                  <option value="database">Database</option>
                  <option value="cache">Cache</option>
                  <option value="queue">Queue</option>
                  <option value="storage">Storage</option>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="owner_id">Owner</Label>
                <Select
                  id="owner_id"
                  value={formData.owner_id}
                  onChange={(e) => setFormData({ ...formData, owner_id: e.target.value })}
                >
                  <option value="">Select owner</option>
                  {users.map(user => (
                    <option key={user.id} value={user.id}>{user.full_name}</option>
                  ))}
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="team_id">Team</Label>
                <Select
                  id="team_id"
                  value={formData.team_id}
                  onChange={(e) => setFormData({ ...formData, team_id: e.target.value })}
                >
                  <option value="">Select team</option>
                  {teams.map(team => (
                    <option key={team.id} value={team.id}>{team.name}</option>
                  ))}
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="tags">Tags (comma-separated)</Label>
              <Input
                id="tags"
                type="text"
                value={formData.tags}
                onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
                placeholder="payments, critical, external"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="repository_url">Repository URL</Label>
                <Input
                  id="repository_url"
                  type="url"
                  value={formData.repository_url}
                  onChange={(e) => setFormData({ ...formData, repository_url: e.target.value })}
                  placeholder="https://github.com/..."
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="documentation_url">Documentation URL</Label>
                <Input
                  id="documentation_url"
                  type="url"
                  value={formData.documentation_url}
                  onChange={(e) => setFormData({ ...formData, documentation_url: e.target.value })}
                  placeholder="https://docs.example.com/..."
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="dashboard_url">Dashboard URL</Label>
                <Input
                  id="dashboard_url"
                  type="url"
                  value={formData.dashboard_url}
                  onChange={(e) => setFormData({ ...formData, dashboard_url: e.target.value })}
                  placeholder="https://grafana.example.com/..."
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="health_check_url">Health Check URL</Label>
                <Input
                  id="health_check_url"
                  type="url"
                  value={formData.health_check_url}
                  onChange={(e) => setFormData({ ...formData, health_check_url: e.target.value })}
                  placeholder="https://api.example.com/health"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-4 border-t border-border">
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setShowCreateModal(false);
                  resetForm();
                }}
              >
                Cancel
              </Button>
              <Button type="submit">
                Create Service
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

        {/* Dependency Graph Modal */}
        <Dialog open={showDependencyGraph} onOpenChange={setShowDependencyGraph}>
          <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden">
            <DialogHeader>
              <DialogTitle>Service Dependency Graph</DialogTitle>
            </DialogHeader>
            {dependencyGraph && (
              <div className="bg-secondary rounded-lg p-6 min-h-[400px] overflow-y-auto">
                <div className="space-y-4">
                  <p className="text-muted-foreground mb-4">
                    {dependencyGraph.nodes.length} services, {dependencyGraph.edges.length} dependencies
                  </p>
                  {dependencyGraph.nodes.map(node => {
                    const deps = dependencyGraph.edges.filter(e => e.from === node.id);
                    const dependents = dependencyGraph.edges.filter(e => e.to === node.id);
                    return (
                      <div key={node.id} className="border border-border rounded-lg bg-transparent">
                        <div className="p-4">
                          <div className="flex items-center gap-3 mb-2">
                            <span className={`w-3 h-3 rounded-full ${
                              node.health_status === 'healthy' ? 'bg-green-500' :
                              node.health_status === 'degraded' ? 'bg-yellow-500' :
                              node.health_status === 'down' ? 'bg-red-500' : 'bg-muted'
                            }`} />
                            <span className="font-medium text-foreground">{node.name}</span>
                            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${
                              getTierBadgeVariant(node.tier) === 'error' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                              getTierBadgeVariant(node.tier) === 'warning' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                              getTierBadgeVariant(node.tier) === 'info' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' :
                              'bg-secondary text-muted-foreground border-border'
                            }`}>
                              {node.tier}
                            </span>
                          </div>
                          {deps.length > 0 && (
                            <div className="ml-6 text-sm">
                              <span className="text-muted-foreground">Depends on: </span>
                              <span className="text-foreground">
                                {deps.map(d => dependencyGraph.nodes.find(n => n.id === d.to)?.name).join(', ')}
                              </span>
                            </div>
                          )}
                          {dependents.length > 0 && (
                            <div className="ml-6 text-sm">
                              <span className="text-muted-foreground">Required by: </span>
                              <span className="text-foreground">
                                {dependents.map(d => dependencyGraph.nodes.find(n => n.id === d.from)?.name).join(', ')}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
};

export default ServiceCatalog;
