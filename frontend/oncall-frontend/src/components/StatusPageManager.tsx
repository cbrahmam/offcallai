// StatusPageManager.tsx - Manage public status page
import React, { useState, useEffect, useCallback } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle,
  ClipboardCopy,
  Eye,
  Globe,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
  Users,
  Wrench,
  X
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { Button } from './ui/button';

import { API_URL as API_BASE_URL } from '../config/api';

type ServiceStatus = 'operational' | 'degraded' | 'partial_outage' | 'major_outage' | 'maintenance';

interface StatusPageService {
  id: string;
  status_page_id: string;
  name: string;
  description: string | null;
  status: ServiceStatus;
  display_order: number;
  is_visible: boolean;
  group_name: string | null;
  health_check_url: string | null;
  health_check_interval_minutes: number;
  created_at: string;
}

interface StatusPage {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  description: string | null;
  logo_url: string | null;
  primary_color: string;
  is_public: boolean;
  show_historical_uptime: boolean;
  historical_days: number;
  show_incident_history: boolean;
  incident_history_days: number;
  allow_subscriptions: boolean;
  support_url: string | null;
  support_email: string | null;
  services: StatusPageService[];
  created_at: string;
}

interface Subscriber {
  id: string;
  email: string;
  is_verified: boolean;
  subscribed_at: string;
}

const statusConfig: Record<ServiceStatus, { label: string; color: string; bgColor: string; icon: React.ReactNode }> = {
  operational: {
    label: 'Operational',
    color: 'text-green-400',
    bgColor: 'bg-green-500/20',
    icon: <CheckCircle className="h-5 w-5 text-green-400" />
  },
  degraded: {
    label: 'Degraded Performance',
    color: 'text-yellow-400',
    bgColor: 'bg-yellow-500/20',
    icon: <AlertTriangle className="h-5 w-5 text-yellow-400" />
  },
  partial_outage: {
    label: 'Partial Outage',
    color: 'text-orange-400',
    bgColor: 'bg-orange-500/20',
    icon: <AlertCircle className="h-5 w-5 text-orange-400" />
  },
  major_outage: {
    label: 'Major Outage',
    color: 'text-red-400',
    bgColor: 'bg-red-500/20',
    icon: <AlertCircle className="h-5 w-5 text-red-400" />
  },
  maintenance: {
    label: 'Under Maintenance',
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/20',
    icon: <Wrench className="h-5 w-5 text-blue-400" />
  }
};

const StatusPageManager: React.FC = () => {
  const { token } = useAuth();
  const [statusPage, setStatusPage] = useState<StatusPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreatePage, setShowCreatePage] = useState(false);
  const [showAddService, setShowAddService] = useState(false);
  const [editingService, setEditingService] = useState<StatusPageService | null>(null);
  const [subscribers, setSubscribers] = useState<Subscriber[]>([]);
  const [showSubscribers, setShowSubscribers] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [activeTab, setActiveTab] = useState<'services' | 'settings'>('services');

  // Page form
  const [pageForm, setPageForm] = useState({
    name: '',
    slug: '',
    description: '',
    primary_color: '#3B82F6',
    is_public: true,
    show_historical_uptime: true,
    historical_days: 90,
    show_incident_history: true,
    incident_history_days: 14,
    allow_subscriptions: true,
    support_url: '',
    support_email: ''
  });

  // Service form
  const [serviceForm, setServiceForm] = useState({
    name: '',
    description: '',
    status: 'operational' as ServiceStatus,
    display_order: 0,
    is_visible: true,
    group_name: ''
  });

  const loadStatusPage = useCallback(async () => {
    if (!token) return;

    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/status-pages/`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.status === 404) {
        setStatusPage(null);
        return;
      }

      if (!response.ok) throw new Error('Failed to fetch status page');

      const data = await response.json();
      setStatusPage(data);
    } catch (err: any) {
      if (!err.message.includes('404')) {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, [token]);

  const loadSubscribers = useCallback(async () => {
    if (!token || !statusPage) return;

    try {
      const response = await fetch(`${API_BASE_URL}/status-pages/subscribers`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setSubscribers(data.subscribers);
      }
    } catch (err) {
      console.error('Failed to load subscribers:', err);
    }
  }, [token, statusPage]);

  useEffect(() => {
    loadStatusPage();
  }, [loadStatusPage]);

  useEffect(() => {
    if (showSubscribers) {
      loadSubscribers();
    }
  }, [showSubscribers, loadSubscribers]);

  const handleCreatePage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;

    setSubmitting(true);
    try {
      const response = await fetch(`${API_BASE_URL}/status-pages/`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(pageForm)
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Failed to create status page');
      }

      setShowCreatePage(false);
      loadStatusPage();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleUpdatePage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !statusPage) return;

    setSubmitting(true);
    try {
      const response = await fetch(`${API_BASE_URL}/status-pages/`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(pageForm)
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Failed to update status page');
      }

      loadStatusPage();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleAddService = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;

    setSubmitting(true);
    try {
      const url = editingService
        ? `${API_BASE_URL}/status-pages/services/${editingService.id}`
        : `${API_BASE_URL}/status-pages/services`;

      const response = await fetch(url, {
        method: editingService ? 'PATCH' : 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          ...serviceForm,
          group_name: serviceForm.group_name || null
        })
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Failed to save service');
      }

      setShowAddService(false);
      setEditingService(null);
      setServiceForm({
        name: '',
        description: '',
        status: 'operational',
        display_order: 0,
        is_visible: true,
        group_name: ''
      });
      loadStatusPage();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleUpdateServiceStatus = async (serviceId: string, status: ServiceStatus) => {
    if (!token) return;

    try {
      const response = await fetch(
        `${API_BASE_URL}/status-pages/services/${serviceId}/status?status=${status}`,
        {
          method: 'PATCH',
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );

      if (!response.ok) throw new Error('Failed to update status');

      loadStatusPage();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDeleteService = async (serviceId: string) => {
    if (!token || !window.confirm('Are you sure you want to delete this service?')) return;

    try {
      const response = await fetch(`${API_BASE_URL}/status-pages/services/${serviceId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) throw new Error('Failed to delete service');

      loadStatusPage();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const openEditService = (service: StatusPageService) => {
    setServiceForm({
      name: service.name,
      description: service.description || '',
      status: service.status,
      display_order: service.display_order,
      is_visible: service.is_visible,
      group_name: service.group_name || ''
    });
    setEditingService(service);
    setShowAddService(true);
  };

  const copyPublicUrl = () => {
    if (statusPage) {
      const url = `${window.location.origin}/status/${statusPage.slug}`;
      navigator.clipboard.writeText(url);
    }
  };

  // Initialize page form when status page is loaded
  useEffect(() => {
    if (statusPage) {
      setPageForm({
        name: statusPage.name,
        slug: statusPage.slug,
        description: statusPage.description || '',
        primary_color: statusPage.primary_color,
        is_public: statusPage.is_public,
        show_historical_uptime: statusPage.show_historical_uptime,
        historical_days: statusPage.historical_days,
        show_incident_history: statusPage.show_incident_history,
        incident_history_days: statusPage.incident_history_days,
        allow_subscriptions: statusPage.allow_subscriptions,
        support_url: statusPage.support_url || '',
        support_email: statusPage.support_email || ''
      });
    }
  }, [statusPage]);

  if (loading) {
    return (
      <div className="min-h-screen bg-background">
        <div className="p-6 max-w-7xl mx-auto">
          <div className="text-center py-12 text-muted-foreground">Loading...</div>
        </div>
      </div>
    );
  }

  // No status page - show create option
  if (!statusPage && !showCreatePage) {
    return (
      <div className="min-h-screen bg-background">
        <div className="p-6 max-w-7xl mx-auto">
          <div className="border border-border rounded-lg bg-transparent text-center py-16 px-8">
            <div className="p-4 rounded-2xl bg-secondary w-20 h-20 flex items-center justify-center mx-auto mb-4">
              <Globe className="h-10 w-10 text-muted-foreground" />
            </div>
            <h2 className="text-base font-medium text-foreground mb-2">No Status Page Yet</h2>
            <p className="text-muted-foreground text-sm mb-6 max-w-md mx-auto">
              Create a public status page to keep your users informed about service health and incidents.
            </p>
            <Button
              onClick={() => setShowCreatePage(true)}
              className="bg-primary text-primary-foreground hover:bg-white/90"
            >
              <Plus className="h-5 w-5 mr-2" />
              Create Status Page
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // Create page form
  if (showCreatePage && !statusPage) {
    return (
      <div className="min-h-screen bg-background">
        <div className="p-6 max-w-3xl mx-auto">
          <h1 className="text-base font-medium text-foreground mb-6">Create Status Page</h1>

          <div className="border border-border rounded-lg bg-transparent p-6">
            <form onSubmit={handleCreatePage} className="space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1">Page Name *</label>
                  <input
                    type="text"
                    value={pageForm.name}
                    onChange={(e) => setPageForm({ ...pageForm, name: e.target.value })}
                    required
                    className="w-full bg-accent border border-border rounded-md px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-white/10"
                    placeholder="Acme Inc Status"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1">URL Slug *</label>
                  <input
                    type="text"
                    value={pageForm.slug}
                    onChange={(e) => setPageForm({ ...pageForm, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-') })}
                    required
                    pattern="^[a-z0-9-]+$"
                    className="w-full bg-accent border border-border rounded-md px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-white/10"
                    placeholder="acme-status"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Your page will be at: /status/{pageForm.slug || 'your-slug'}
                  </p>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Description</label>
                <textarea
                  value={pageForm.description}
                  onChange={(e) => setPageForm({ ...pageForm, description: e.target.value })}
                  rows={2}
                  className="w-full bg-accent border border-border rounded-md px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-white/10"
                  placeholder="Current status of Acme Inc services"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1">Primary Color</label>
                  <input
                    type="color"
                    value={pageForm.primary_color}
                    onChange={(e) => setPageForm({ ...pageForm, primary_color: e.target.value })}
                    className="w-full h-10 bg-accent border border-border rounded-md cursor-pointer"
                  />
                </div>
                <div className="flex items-end gap-4">
                  <label className="flex items-center gap-2 text-sm text-foreground">
                    <input
                      type="checkbox"
                      checked={pageForm.is_public}
                      onChange={(e) => setPageForm({ ...pageForm, is_public: e.target.checked })}
                      className="rounded"
                    />
                    Public Page
                  </label>
                  <label className="flex items-center gap-2 text-sm text-foreground">
                    <input
                      type="checkbox"
                      checked={pageForm.allow_subscriptions}
                      onChange={(e) => setPageForm({ ...pageForm, allow_subscriptions: e.target.checked })}
                      className="rounded"
                    />
                    Allow Subscriptions
                  </label>
                </div>
              </div>

              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowCreatePage(false)}
                  className="px-4 py-2 text-muted-foreground hover:text-foreground transition-colors"
                >
                  Cancel
                </button>
                <Button
                  type="submit"
                  disabled={submitting}
                  className="bg-primary text-primary-foreground hover:bg-white/90"
                >
                  {submitting ? 'Creating...' : 'Create Status Page'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      </div>
    );
  }

  // Main view with status page
  return (
    <div className="min-h-screen bg-background">
      <div className="border-b border-border">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-sky-500/10">
                <Globe className="w-6 h-6 text-sky-400" />
              </div>
              <div>
                <h1 className="text-base font-medium text-foreground">
                  Status Page
                </h1>
                <p className="text-muted-foreground text-sm mt-1">Manage your public status page and services</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Button
                onClick={() => setShowSubscribers(true)}
                variant="outline"
                size="sm"
                className="border-border text-foreground hover:bg-accent"
              >
                <Users className="h-5 w-5 mr-1" />
                Subscribers
              </Button>
              <Button
                onClick={copyPublicUrl}
                variant="ghost"
                size="sm"
              >
                <ClipboardCopy className="h-5 w-5 mr-1" />
                Copy URL
              </Button>
              <a
                href={`/status/${statusPage?.slug}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                <Button size="sm" className="bg-primary text-primary-foreground hover:bg-white/90">
                  <Eye className="h-5 w-5 mr-1" />
                  View Page
                </Button>
              </a>
            </div>
          </div>
        </div>
      </div>
      <div className="p-6 max-w-7xl mx-auto">

        {/* Error */}
        {error && (
          <div className="mb-4 p-4 border border-red-500/20 bg-red-500/10 rounded-lg">
            <div className="flex items-center gap-2 text-red-400">
              <AlertTriangle className="h-5 w-5" />
              {error}
              <button onClick={() => setError(null)} className="ml-auto">
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div className="border-b border-border mb-6">
          <div className="flex gap-6">
            <button
              onClick={() => setActiveTab('services')}
              className={`pb-3 px-1 border-b-2 transition-colors ${
                activeTab === 'services'
                  ? 'border-white text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              Services
            </button>
            <button
              onClick={() => setActiveTab('settings')}
              className={`pb-3 px-1 border-b-2 transition-colors ${
                activeTab === 'settings'
                  ? 'border-white text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              Settings
            </button>
          </div>
        </div>

        {/* Services Tab */}
        {activeTab === 'services' && statusPage && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-foreground">Services ({statusPage.services.length})</h2>
              <Button
                onClick={() => setShowAddService(true)}
                size="sm"
                className="bg-primary text-primary-foreground hover:bg-white/90"
              >
                <Plus className="h-5 w-5 mr-1" />
                Add Service
              </Button>
            </div>

            {statusPage.services.length === 0 ? (
              <div className="border border-border rounded-lg bg-transparent text-center py-12 px-4">
                <p className="text-muted-foreground">No services added yet</p>
                <p className="text-muted-foreground text-sm mt-1">Add services to display on your status page</p>
              </div>
            ) : (
              <div className="space-y-3">
                {statusPage.services.map((service) => (
                  <div
                    key={service.id}
                    className="border border-border rounded-lg bg-transparent p-4 flex items-center justify-between"
                  >
                    <div className="flex items-center gap-4">
                      {statusConfig[service.status].icon}
                      <div>
                        <h3 className="font-medium text-foreground">{service.name}</h3>
                        {service.description && (
                          <p className="text-sm text-muted-foreground">{service.description}</p>
                        )}
                        {service.group_name && (
                          <span className="text-xs text-muted-foreground">Group: {service.group_name}</span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <select
                        value={service.status}
                        onChange={(e) => handleUpdateServiceStatus(service.id, e.target.value as ServiceStatus)}
                        className={`text-sm px-3 py-1.5 rounded-lg border-0 ${statusConfig[service.status].bgColor} ${statusConfig[service.status].color} focus:outline-none focus:ring-2 focus:ring-white/10`}
                      >
                        <option value="operational">Operational</option>
                        <option value="degraded">Degraded</option>
                        <option value="partial_outage">Partial Outage</option>
                        <option value="major_outage">Major Outage</option>
                        <option value="maintenance">Maintenance</option>
                      </select>
                      <button
                        onClick={() => openEditService(service)}
                        className="p-2 text-muted-foreground hover:text-foreground transition-colors"
                      >
                        <Pencil className="h-5 w-5" />
                      </button>
                      <button
                        onClick={() => handleDeleteService(service.id)}
                        className="p-2 text-muted-foreground hover:text-red-400 transition-colors"
                      >
                        <Trash2 className="h-5 w-5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Settings Tab */}
        {activeTab === 'settings' && statusPage && (
          <div className="border border-border rounded-lg bg-transparent p-6 max-w-2xl">
            <form onSubmit={handleUpdatePage} className="space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1">Page Name</label>
                  <input
                    type="text"
                    value={pageForm.name}
                    onChange={(e) => setPageForm({ ...pageForm, name: e.target.value })}
                    className="w-full bg-accent border border-border rounded-md px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-white/10"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1">URL Slug</label>
                  <input
                    type="text"
                    value={pageForm.slug}
                    onChange={(e) => setPageForm({ ...pageForm, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-') })}
                    className="w-full bg-accent border border-border rounded-md px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-white/10"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Description</label>
                <textarea
                  value={pageForm.description}
                  onChange={(e) => setPageForm({ ...pageForm, description: e.target.value })}
                  rows={2}
                  className="w-full bg-accent border border-border rounded-md px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-white/10"
                />
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1">Primary Color</label>
                  <input
                    type="color"
                    value={pageForm.primary_color}
                    onChange={(e) => setPageForm({ ...pageForm, primary_color: e.target.value })}
                    className="w-full h-10 bg-accent border border-border rounded-md cursor-pointer"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1">Historical Days</label>
                  <input
                    type="number"
                    value={pageForm.historical_days}
                    onChange={(e) => setPageForm({ ...pageForm, historical_days: parseInt(e.target.value) })}
                    className="w-full bg-accent border border-border rounded-md px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-white/10"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1">Incident History Days</label>
                  <input
                    type="number"
                    value={pageForm.incident_history_days}
                    onChange={(e) => setPageForm({ ...pageForm, incident_history_days: parseInt(e.target.value) })}
                    className="w-full bg-accent border border-border rounded-md px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-white/10"
                  />
                </div>
              </div>

              <div className="space-y-3">
                <label className="flex items-center gap-2 text-sm text-foreground">
                  <input
                    type="checkbox"
                    checked={pageForm.is_public}
                    onChange={(e) => setPageForm({ ...pageForm, is_public: e.target.checked })}
                    className="rounded"
                  />
                  Public Page (visible to anyone)
                </label>
                <label className="flex items-center gap-2 text-sm text-foreground">
                  <input
                    type="checkbox"
                    checked={pageForm.show_historical_uptime}
                    onChange={(e) => setPageForm({ ...pageForm, show_historical_uptime: e.target.checked })}
                    className="rounded"
                  />
                  Show Historical Uptime
                </label>
                <label className="flex items-center gap-2 text-sm text-foreground">
                  <input
                    type="checkbox"
                    checked={pageForm.show_incident_history}
                    onChange={(e) => setPageForm({ ...pageForm, show_incident_history: e.target.checked })}
                    className="rounded"
                  />
                  Show Incident History
                </label>
                <label className="flex items-center gap-2 text-sm text-foreground">
                  <input
                    type="checkbox"
                    checked={pageForm.allow_subscriptions}
                    onChange={(e) => setPageForm({ ...pageForm, allow_subscriptions: e.target.checked })}
                    className="rounded"
                  />
                  Allow Email Subscriptions
                </label>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1">Support URL</label>
                  <input
                    type="url"
                    value={pageForm.support_url}
                    onChange={(e) => setPageForm({ ...pageForm, support_url: e.target.value })}
                    className="w-full bg-accent border border-border rounded-md px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-white/10"
                    placeholder="https://support.example.com"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1">Support Email</label>
                  <input
                    type="email"
                    value={pageForm.support_email}
                    onChange={(e) => setPageForm({ ...pageForm, support_email: e.target.value })}
                    className="w-full bg-accent border border-border rounded-md px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-white/10"
                    placeholder="support@example.com"
                  />
                </div>
              </div>

              <Button
                type="submit"
                disabled={submitting}
                className="bg-primary text-primary-foreground hover:bg-white/90"
              >
                {submitting ? 'Saving...' : 'Save Settings'}
              </Button>
            </form>
          </div>
        )}

        {/* Add/Edit Service Modal */}
        {showAddService && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="w-full max-w-md border border-border rounded-lg bg-background">
              <div className="px-6 py-4 border-b border-border flex items-center justify-between">
                <h2 className="text-lg font-semibold text-foreground">
                  {editingService ? 'Edit Service' : 'Add Service'}
                </h2>
                <button onClick={() => { setShowAddService(false); setEditingService(null); }} className="text-muted-foreground hover:text-foreground transition-colors">
                  <X className="h-5 w-5" />
                </button>
              </div>

              <form onSubmit={handleAddService} className="p-6 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1">Service Name *</label>
                  <input
                    type="text"
                    value={serviceForm.name}
                    onChange={(e) => setServiceForm({ ...serviceForm, name: e.target.value })}
                    required
                    className="w-full bg-accent border border-border rounded-md px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-white/10"
                    placeholder="API Server"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-foreground mb-1">Description</label>
                  <input
                    type="text"
                    value={serviceForm.description}
                    onChange={(e) => setServiceForm({ ...serviceForm, description: e.target.value })}
                    className="w-full bg-accent border border-border rounded-md px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-white/10"
                    placeholder="Main API endpoints"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-foreground mb-1">Status</label>
                    <select
                      value={serviceForm.status}
                      onChange={(e) => setServiceForm({ ...serviceForm, status: e.target.value as ServiceStatus })}
                      className="w-full bg-accent border border-border rounded-md px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-white/10"
                    >
                      <option value="operational">Operational</option>
                      <option value="degraded">Degraded</option>
                      <option value="partial_outage">Partial Outage</option>
                      <option value="major_outage">Major Outage</option>
                      <option value="maintenance">Maintenance</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-foreground mb-1">Display Order</label>
                    <input
                      type="number"
                      value={serviceForm.display_order}
                      onChange={(e) => setServiceForm({ ...serviceForm, display_order: parseInt(e.target.value) })}
                      className="w-full bg-accent border border-border rounded-md px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-white/10"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-foreground mb-1">Group Name (optional)</label>
                  <input
                    type="text"
                    value={serviceForm.group_name}
                    onChange={(e) => setServiceForm({ ...serviceForm, group_name: e.target.value })}
                    className="w-full bg-accent border border-border rounded-md px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-white/10"
                    placeholder="Core Services"
                  />
                </div>

                <label className="flex items-center gap-2 text-sm text-foreground">
                  <input
                    type="checkbox"
                    checked={serviceForm.is_visible}
                    onChange={(e) => setServiceForm({ ...serviceForm, is_visible: e.target.checked })}
                    className="rounded"
                  />
                  Visible on status page
                </label>

                <div className="flex justify-end gap-3 pt-4">
                  <button
                    type="button"
                    onClick={() => { setShowAddService(false); setEditingService(null); }}
                    className="px-4 py-2 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    Cancel
                  </button>
                  <Button
                    type="submit"
                    disabled={submitting}
                    className="bg-primary text-primary-foreground hover:bg-white/90"
                  >
                    {submitting ? 'Saving...' : editingService ? 'Update' : 'Add Service'}
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Subscribers Modal */}
        {showSubscribers && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="w-full max-w-lg max-h-[80vh] flex flex-col border border-border rounded-lg bg-background">
              <div className="px-6 py-4 border-b border-border flex items-center justify-between">
                <h2 className="text-lg font-semibold text-foreground">Subscribers ({subscribers.length})</h2>
                <button onClick={() => setShowSubscribers(false)} className="text-muted-foreground hover:text-foreground transition-colors">
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto p-6">
                {subscribers.length === 0 ? (
                  <p className="text-muted-foreground text-center py-8">No subscribers yet</p>
                ) : (
                  <div className="space-y-2">
                    {subscribers.map((sub) => (
                      <div key={sub.id} className="flex items-center justify-between p-3 bg-accent rounded-lg border border-border/50">
                        <div>
                          <div className="text-foreground">{sub.email}</div>
                          <div className="text-xs text-muted-foreground">
                            Subscribed: {new Date(sub.subscribed_at).toLocaleDateString()}
                          </div>
                        </div>
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${
                          sub.is_verified ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20'
                        }`}>
                          {sub.is_verified ? 'Verified' : 'Pending'}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default StatusPageManager;
