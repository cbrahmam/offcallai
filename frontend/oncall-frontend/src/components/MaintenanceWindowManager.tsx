// MaintenanceWindowManager.tsx - Refactored with shadcn/ui
import React, { useState, useEffect, useCallback } from 'react';
import {
  WrenchScrewdriverIcon,
  PlusIcon,
  CalendarDaysIcon,
  XMarkIcon,
  TrashIcon,
  PencilIcon,
  BellSlashIcon
} from '@heroicons/react/24/outline';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Label } from './ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';

import { API_URL as API_BASE_URL } from '../config/api';

interface MaintenanceWindow {
  id: string;
  name: string;
  description: string | null;
  start_time: string;
  end_time: string;
  services: string[];
  tags: string[];
  suppress_alerts: boolean;
  auto_resolve_incidents: boolean;
  is_recurring: boolean;
  recurrence_pattern: any;
  is_active: boolean;
  is_cancelled: boolean;
  cancelled_at: string | null;
  notify_before_minutes: number;
  created_by_name: string | null;
  created_at: string;
  is_currently_active: boolean;
}

interface MaintenanceWindowFormData {
  name: string;
  description: string;
  start_time: string;
  end_time: string;
  services: string;
  tags: string;
  suppress_alerts: boolean;
  auto_resolve_incidents: boolean;
  notify_before_minutes: number;
}

const MaintenanceWindowManager: React.FC = () => {
  const { token } = useAuth();
  const [windows, setWindows] = useState<MaintenanceWindow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingWindow, setEditingWindow] = useState<MaintenanceWindow | null>(null);
  const [formData, setFormData] = useState<MaintenanceWindowFormData>({
    name: '',
    description: '',
    start_time: '',
    end_time: '',
    services: '',
    tags: '',
    suppress_alerts: true,
    auto_resolve_incidents: false,
    notify_before_minutes: 30
  });
  const [submitting, setSubmitting] = useState(false);
  const [includePast, setIncludePast] = useState(false);

  const loadWindows = useCallback(async () => {
    if (!token) return;

    try {
      setLoading(true);
      const response = await fetch(
        `${API_BASE_URL}/maintenance-windows/?include_past=${includePast}&per_page=50`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );

      if (!response.ok) throw new Error('Failed to fetch maintenance windows');

      const data = await response.json();
      setWindows(data.windows);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token, includePast]);

  useEffect(() => {
    loadWindows();
  }, [loadWindows]);

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      start_time: '',
      end_time: '',
      services: '',
      tags: '',
      suppress_alerts: true,
      auto_resolve_incidents: false,
      notify_before_minutes: 30
    });
    setEditingWindow(null);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;

    setSubmitting(true);
    try {
      const payload = {
        name: formData.name,
        description: formData.description || null,
        start_time: new Date(formData.start_time).toISOString(),
        end_time: new Date(formData.end_time).toISOString(),
        services: formData.services.split(',').map(s => s.trim()).filter(Boolean),
        tags: formData.tags.split(',').map(t => t.trim()).filter(Boolean),
        suppress_alerts: formData.suppress_alerts,
        auto_resolve_incidents: formData.auto_resolve_incidents,
        notify_before_minutes: formData.notify_before_minutes
      };

      const url = editingWindow
        ? `${API_BASE_URL}/maintenance-windows/${editingWindow.id}`
        : `${API_BASE_URL}/maintenance-windows/`;

      const response = await fetch(url, {
        method: editingWindow ? 'PATCH' : 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Failed to save maintenance window');
      }

      await loadWindows();
      setShowCreateModal(false);
      resetForm();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = async (windowId: string) => {
    if (!token || !window.confirm('Are you sure you want to cancel this maintenance window?')) return;

    try {
      const response = await fetch(
        `${API_BASE_URL}/maintenance-windows/${windowId}/cancel`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );

      if (!response.ok) throw new Error('Failed to cancel maintenance window');
      await loadWindows();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDelete = async (windowId: string) => {
    if (!token || !window.confirm('Are you sure you want to permanently delete this maintenance window?')) return;

    try {
      const response = await fetch(
        `${API_BASE_URL}/maintenance-windows/${windowId}`,
        {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );

      if (!response.ok) throw new Error('Failed to delete maintenance window');
      await loadWindows();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const openEditModal = (window: MaintenanceWindow) => {
    setEditingWindow(window);
    setFormData({
      name: window.name,
      description: window.description || '',
      start_time: new Date(window.start_time).toISOString().slice(0, 16),
      end_time: new Date(window.end_time).toISOString().slice(0, 16),
      services: window.services.join(', '),
      tags: window.tags.join(', '),
      suppress_alerts: window.suppress_alerts,
      auto_resolve_incidents: window.auto_resolve_incidents,
      notify_before_minutes: window.notify_before_minutes
    });
    setShowCreateModal(true);
  };

  const formatDateTime = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getStatusBadge = (window: MaintenanceWindow) => {
    if (window.is_cancelled) {
      return <Badge variant="secondary">Cancelled</Badge>;
    }
    if (window.is_currently_active) {
      return (
        <Badge variant="warning" className="flex items-center gap-1">
          <span className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse"></span>
          Active Now
        </Badge>
      );
    }
    if (new Date(window.end_time) < new Date()) {
      return <Badge variant="secondary">Completed</Badge>;
    }
    return <Badge variant="info">Scheduled</Badge>;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <WrenchScrewdriverIcon className="h-7 w-7 text-orange-400" />
            Maintenance Windows
          </h1>
          <p className="text-gray-400 mt-1">Schedule maintenance to suppress alerts</p>
        </div>
        <Button onClick={() => { resetForm(); setShowCreateModal(true); }}>
          <PlusIcon className="h-5 w-5 mr-2" />
          Schedule Maintenance
        </Button>
      </div>

      {error && (
        <Card className="mb-4 border-destructive bg-destructive/10">
          <CardContent className="p-4 flex items-center text-destructive">
            {error}
            <button onClick={() => setError(null)} className="ml-auto underline">Dismiss</button>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <div className="mb-4 flex items-center gap-4">
        <label className="flex items-center gap-2 text-muted-foreground text-sm">
          <input
            type="checkbox"
            checked={includePast}
            onChange={(e) => setIncludePast(e.target.checked)}
            className="rounded border-border bg-background text-primary"
          />
          Show past windows
        </label>
      </div>

      {/* Windows List */}
      {windows.length === 0 ? (
        <Card className="bg-muted/50">
          <CardContent className="text-center py-8">
            <p className="text-muted-foreground mb-4">No maintenance windows scheduled</p>
            <Button onClick={() => { resetForm(); setShowCreateModal(true); }}>
              Schedule Maintenance
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {windows.map((window) => (
            <Card
              key={window.id}
              className={`${
                window.is_currently_active
                  ? 'border-yellow-500/50'
                  : window.is_cancelled
                  ? 'opacity-60'
                  : ''
              }`}
            >
              <CardContent className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-lg font-medium text-foreground">{window.name}</h3>
                      {getStatusBadge(window)}
                      {window.suppress_alerts && (
                        <span className="flex items-center gap-1 text-xs text-orange-500 dark:text-orange-400">
                          <BellSlashIcon className="h-4 w-4" />
                          Alerts Suppressed
                        </span>
                      )}
                    </div>

                    {window.description && (
                      <p className="text-muted-foreground text-sm mb-3">{window.description}</p>
                    )}

                    <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
                      <div className="flex items-center gap-2">
                        <CalendarDaysIcon className="h-4 w-4" />
                        <span>{formatDateTime(window.start_time)}</span>
                        <span>→</span>
                        <span>{formatDateTime(window.end_time)}</span>
                      </div>

                      {window.services.length > 0 && (
                        <div className="flex items-center gap-2">
                          <span className="text-muted-foreground/70">Services:</span>
                          <div className="flex gap-1">
                            {window.services.map((service, idx) => (
                              <Badge key={idx} variant="outline" className="text-xs">
                                {service}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {!window.is_cancelled && new Date(window.end_time) > new Date() && (
                    <div className="flex items-center gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openEditModal(window)}
                      >
                        <PencilIcon className="h-5 w-5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleCancel(window.id)}
                        className="hover:text-yellow-500"
                      >
                        <XMarkIcon className="h-5 w-5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(window.id)}
                        className="text-destructive hover:text-destructive"
                      >
                        <TrashIcon className="h-5 w-5" />
                      </Button>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create/Edit Modal */}
      <Dialog open={showCreateModal} onOpenChange={(open) => { if (!open) { setShowCreateModal(false); resetForm(); } }}>
        <DialogContent onClose={() => { setShowCreateModal(false); resetForm(); }}>
          <DialogHeader>
            <DialogTitle>
              {editingWindow ? 'Edit Maintenance Window' : 'Schedule Maintenance'}
            </DialogTitle>
          </DialogHeader>

          <form onSubmit={handleCreate} className="space-y-4 mt-4">
            <div className="space-y-2">
              <Label>Name *</Label>
              <Input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Database Migration"
                required
              />
            </div>

            <div className="space-y-2">
              <Label>Description</Label>
              <Textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Scheduled database migration and optimization"
                rows={2}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Start Time *</Label>
                <Input
                  type="datetime-local"
                  value={formData.start_time}
                  onChange={(e) => setFormData({ ...formData, start_time: e.target.value })}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label>End Time *</Label>
                <Input
                  type="datetime-local"
                  value={formData.end_time}
                  onChange={(e) => setFormData({ ...formData, end_time: e.target.value })}
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Affected Services</Label>
              <Input
                type="text"
                value={formData.services}
                onChange={(e) => setFormData({ ...formData, services: e.target.value })}
                placeholder="api-gateway, database, web-frontend"
              />
              <p className="text-xs text-muted-foreground">Comma-separated list of service names</p>
            </div>

            <div className="space-y-2">
              <Label>Tags</Label>
              <Input
                type="text"
                value={formData.tags}
                onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
                placeholder="database, migration, scheduled"
              />
            </div>

            <div className="space-y-2">
              <Label>Notify Before (minutes)</Label>
              <Input
                type="number"
                value={formData.notify_before_minutes}
                onChange={(e) => setFormData({ ...formData, notify_before_minutes: parseInt(e.target.value) || 30 })}
                min={0}
                max={1440}
              />
            </div>

            <div className="space-y-3">
              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={formData.suppress_alerts}
                  onChange={(e) => setFormData({ ...formData, suppress_alerts: e.target.checked })}
                  className="rounded border-border bg-background text-primary"
                />
                <span className="text-foreground">Suppress alerts during maintenance</span>
              </label>

              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={formData.auto_resolve_incidents}
                  onChange={(e) => setFormData({ ...formData, auto_resolve_incidents: e.target.checked })}
                  className="rounded border-border bg-background text-primary"
                />
                <span className="text-foreground">Auto-resolve incidents created during window</span>
              </label>
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => { setShowCreateModal(false); resetForm(); }}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={submitting}>
                {submitting ? 'Saving...' : editingWindow ? 'Update' : 'Schedule'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default MaintenanceWindowManager;
