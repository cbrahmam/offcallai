// RunbookManager.tsx - Runbook Management Component
import React, { useState, useEffect, useCallback } from 'react';
import {
  BookOpen,
  ChevronDown,
  ChevronUp,
  Clock,
  Pencil,
  Play,
  Plus,
  Search,
  Server,
  Trash2,
  XCircle
} from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Label } from './ui/label';
import { Select } from './ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { useAuth } from '../contexts/AuthContext';
import { useNotifications } from '../contexts/NotificationContext';

import { API_URL as API_BASE_URL } from '../config/api';

interface AlertPattern {
  field: string;
  operator: string;
  value: string;
}

interface Runbook {
  id: string;
  title: string;
  description: string | null;
  content: string;
  tags: string[];
  service_names: string[];
  alert_patterns: AlertPattern[];
  is_active: boolean;
  usage_count: number;
  last_used_at: string | null;
  created_at: string;
  updated_at: string;
  created_by: {
    id: string;
    email: string;
    full_name: string | null;
  } | null;
}

interface RunbookListResponse {
  runbooks: Runbook[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

interface RunbookManagerProps {
  onSelectRunbook?: (runbook: Runbook) => void;
}

const PATTERN_FIELDS = [
  { value: 'title', label: 'Title' },
  { value: 'description', label: 'Description' },
  { value: 'service_name', label: 'Service Name' },
  { value: 'severity', label: 'Severity' },
  { value: 'source', label: 'Source' },
  { value: 'host', label: 'Host' },
  { value: 'environment', label: 'Environment' }
];

const PATTERN_OPERATORS = [
  { value: 'contains', label: 'Contains' },
  { value: 'equals', label: 'Equals' },
  { value: 'starts_with', label: 'Starts With' },
  { value: 'ends_with', label: 'Ends With' },
  { value: 'regex', label: 'Regex' }
];

const RunbookManager: React.FC<RunbookManagerProps> = ({ onSelectRunbook }) => {
  const { user, token } = useAuth();
  const { showToast } = useNotifications();

  // State
  const [runbooks, setRunbooks] = useState<Runbook[]>([]);
  const [loading, setLoading] = useState(true);
  const [totalPages, setTotalPages] = useState(1);
  const [currentPage, setCurrentPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterActive, setFilterActive] = useState<boolean | null>(null);
  const [filterTag, setFilterTag] = useState<string>('');

  // Modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState<Runbook | null>(null);
  const [editingRunbook, setEditingRunbook] = useState<Runbook | null>(null);
  const [expandedRunbook, setExpandedRunbook] = useState<string | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    content: '',
    tags: [] as string[],
    service_names: [] as string[],
    alert_patterns: [] as AlertPattern[],
    is_active: true
  });
  const [newTag, setNewTag] = useState('');
  const [newServiceName, setNewServiceName] = useState('');
  const [saving, setSaving] = useState(false);

  // Load runbooks
  const loadRunbooks = useCallback(async () => {
    if (!token) return;

    try {
      setLoading(true);
      const params = new URLSearchParams({
        page: currentPage.toString(),
        per_page: '10'
      });

      if (searchQuery) params.append('search', searchQuery);
      if (filterActive !== null) params.append('is_active', filterActive.toString());
      if (filterTag) params.append('tags', filterTag);

      const response = await fetch(`${API_BASE_URL}/runbooks/?${params}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) throw new Error('Failed to fetch runbooks');

      const data: RunbookListResponse = await response.json();
      setRunbooks(data.runbooks);
      setTotalPages(data.total_pages);
    } catch (error) {
      console.error('Error loading runbooks:', error);
      showToast({ message: 'Failed to load runbooks', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [token, currentPage, searchQuery, filterActive, filterTag, showToast]);

  useEffect(() => {
    loadRunbooks();
  }, [loadRunbooks]);

  // Reset form
  const resetForm = () => {
    setFormData({
      title: '',
      description: '',
      content: '',
      tags: [],
      service_names: [],
      alert_patterns: [],
      is_active: true
    });
    setNewTag('');
    setNewServiceName('');
  };

  // Open edit modal
  const openEditModal = (runbook: Runbook) => {
    setEditingRunbook(runbook);
    setFormData({
      title: runbook.title,
      description: runbook.description || '',
      content: runbook.content,
      tags: runbook.tags || [],
      service_names: runbook.service_names || [],
      alert_patterns: runbook.alert_patterns || [],
      is_active: runbook.is_active
    });
    setShowCreateModal(true);
  };

  // Save runbook
  const handleSaveRunbook = async () => {
    if (!token || !formData.title || !formData.content) {
      showToast({ message: 'Title and content are required', type: 'error' });
      return;
    }

    try {
      setSaving(true);

      const payload = {
        ...formData,
        alert_patterns: formData.alert_patterns.map(p => ({
          field: p.field,
          operator: p.operator,
          value: p.value
        }))
      };

      const url = editingRunbook
        ? `${API_BASE_URL}/runbooks/${editingRunbook.id}`
        : `${API_BASE_URL}/runbooks/`;

      const response = await fetch(url, {
        method: editingRunbook ? 'PATCH' : 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to save runbook');
      }

      showToast({
        message: editingRunbook ? 'Runbook updated successfully' : 'Runbook created successfully',
        type: 'success'
      });

      setShowCreateModal(false);
      setEditingRunbook(null);
      resetForm();
      loadRunbooks();
    } catch (error: any) {
      console.error('Error saving runbook:', error);
      showToast({ message: error.message || 'Failed to save runbook', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  // Delete runbook
  const handleDeleteRunbook = async () => {
    if (!token || !showDeleteModal) return;

    try {
      const response = await fetch(`${API_BASE_URL}/runbooks/${showDeleteModal.id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) throw new Error('Failed to delete runbook');

      showToast({ message: 'Runbook deleted successfully', type: 'success' });
      setShowDeleteModal(null);
      loadRunbooks();
    } catch (error) {
      console.error('Error deleting runbook:', error);
      showToast({ message: 'Failed to delete runbook', type: 'error' });
    }
  };

  // Add tag
  const addTag = () => {
    if (newTag && !formData.tags.includes(newTag)) {
      setFormData({ ...formData, tags: [...formData.tags, newTag] });
      setNewTag('');
    }
  };

  // Remove tag
  const removeTag = (tag: string) => {
    setFormData({ ...formData, tags: formData.tags.filter(t => t !== tag) });
  };

  // Add service name
  const addServiceName = () => {
    if (newServiceName && !formData.service_names.includes(newServiceName)) {
      setFormData({ ...formData, service_names: [...formData.service_names, newServiceName] });
      setNewServiceName('');
    }
  };

  // Remove service name
  const removeServiceName = (name: string) => {
    setFormData({ ...formData, service_names: formData.service_names.filter(n => n !== name) });
  };

  // Add pattern
  const addPattern = () => {
    setFormData({
      ...formData,
      alert_patterns: [...formData.alert_patterns, { field: 'title', operator: 'contains', value: '' }]
    });
  };

  // Update pattern
  const updatePattern = (index: number, field: keyof AlertPattern, value: string) => {
    const newPatterns = [...formData.alert_patterns];
    newPatterns[index] = { ...newPatterns[index], [field]: value };
    setFormData({ ...formData, alert_patterns: newPatterns });
  };

  // Remove pattern
  const removePattern = (index: number) => {
    setFormData({
      ...formData,
      alert_patterns: formData.alert_patterns.filter((_, i) => i !== index)
    });
  };

  // Format date
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-amber-500/10">
                <BookOpen className="w-6 h-6 text-amber-400" />
              </div>
              <div>
                <h1 className="text-base font-medium text-foreground">Runbook Automation</h1>
                <p className="text-sm text-muted-foreground">Create and manage automated runbooks for incident response</p>
              </div>
            </div>
            <Button
              onClick={() => {
                resetForm();
                setEditingRunbook(null);
                setShowCreateModal(true);
              }}
              className="bg-primary text-primary-foreground hover:bg-white/90 gap-2"
            >
              <Plus className="h-5 w-5" />
              Create Runbook
            </Button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
      {/* Search and Filters */}
      <div className="flex items-center gap-4 mb-6">
        <div className="flex-1 relative">
          <Search className="h-5 w-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search runbooks..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
        <Select
          value={filterActive === null ? '' : filterActive.toString()}
          onChange={(e) => setFilterActive(e.target.value === '' ? null : e.target.value === 'true')}
        >
          <option value="">All Status</option>
          <option value="true">Active</option>
          <option value="false">Inactive</option>
        </Select>
      </div>

      {/* Runbooks List */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white"></div>
        </div>
      ) : runbooks.length === 0 ? (
        <div className="text-center py-12 border border-border rounded-lg bg-transparent">
          <div className="p-6 pt-6">
            <BookOpen className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-base font-medium text-foreground mb-2">No runbooks yet</h3>
            <p className="text-sm text-muted-foreground mb-4">
              Create your first runbook to automate incident response
            </p>
            <Button onClick={() => setShowCreateModal(true)} className="bg-primary text-primary-foreground hover:bg-white/90">
              Create Runbook
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {runbooks.map((runbook) => (
            <div key={runbook.id} className="border border-border rounded-lg bg-transparent">
              {/* Runbook Header */}
              <div className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="text-base font-medium text-foreground">
                        {runbook.title}
                      </h3>
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${runbook.is_active ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-secondary text-muted-foreground border-border'}`}>
                        {runbook.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                    {runbook.description && (
                      <p className="text-sm text-muted-foreground mt-1">
                        {runbook.description}
                      </p>
                    )}
                    <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Clock className="h-4 w-4" />
                        {formatDate(runbook.created_at)}
                      </span>
                      <span className="flex items-center gap-1">
                        <Play className="h-4 w-4" />
                        Used {runbook.usage_count} times
                      </span>
                      {runbook.service_names.length > 0 && (
                        <span className="flex items-center gap-1">
                          <Server className="h-4 w-4" />
                          {runbook.service_names.join(', ')}
                        </span>
                      )}
                    </div>
                    {runbook.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {runbook.tags.map((tag, i) => (
                          <span key={i} className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-blue-500/10 text-blue-400 border-blue-500/20 text-xs">
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setExpandedRunbook(expandedRunbook === runbook.id ? null : runbook.id)}
                      className="p-2 text-muted-foreground hover:text-foreground rounded transition-colors"
                      title="View details"
                    >
                      {expandedRunbook === runbook.id ? (
                        <ChevronUp className="h-5 w-5" />
                      ) : (
                        <ChevronDown className="h-5 w-5" />
                      )}
                    </button>
                    <button
                      onClick={() => openEditModal(runbook)}
                      className="p-2 text-muted-foreground hover:text-foreground rounded transition-colors"
                      title="Edit"
                    >
                      <Pencil className="h-5 w-5" />
                    </button>
                    <button
                      onClick={() => setShowDeleteModal(runbook)}
                      className="p-2 text-muted-foreground hover:text-red-400 rounded transition-colors"
                      title="Delete"
                    >
                      <Trash2 className="h-5 w-5" />
                    </button>
                  </div>
                </div>
              </div>

              {/* Expanded Content */}
              {expandedRunbook === runbook.id && (
                <div className="border-t border-border p-4 bg-secondary/50">
                  <div className="mb-4">
                    <h4 className="text-sm font-medium text-foreground mb-2">
                      Alert Patterns ({runbook.alert_patterns.length})
                    </h4>
                    {runbook.alert_patterns.length > 0 ? (
                      <div className="space-y-1">
                        {runbook.alert_patterns.map((pattern, i) => (
                          <div key={i} className="text-sm text-muted-foreground">
                            <span className="font-medium">{pattern.field}</span>
                            {' '}{pattern.operator}{' '}
                            <span className="font-mono bg-secondary px-1 rounded">
                              {pattern.value}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">No patterns configured</p>
                    )}
                  </div>
                  <div>
                    <h4 className="text-sm font-medium text-foreground mb-2">
                      Content Preview
                    </h4>
                    <pre className="text-xs bg-transparent text-foreground p-3 rounded-lg overflow-x-auto max-h-48 border border-border">
                      {runbook.content.slice(0, 500)}
                      {runbook.content.length > 500 && '...'}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-6">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={currentPage === 1}
            className="border-border text-foreground hover:bg-accent"
          >
            Previous
          </Button>
          <span className="px-3 py-1 text-muted-foreground text-sm">
            Page {currentPage} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
            className="border-border text-foreground hover:bg-accent"
          >
            Next
          </Button>
        </div>
      )}
      </div>

      {/* Create/Edit Modal */}
      <Dialog open={showCreateModal} onOpenChange={setShowCreateModal}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editingRunbook ? 'Edit Runbook' : 'Create Runbook'}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-6">
            {/* Title */}
            <div className="space-y-2">
              <Label htmlFor="title">Title *</Label>
              <Input
                id="title"
                type="text"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="e.g., Database Connection Pool Recovery"
              />
            </div>

            {/* Description */}
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Input
                id="description"
                type="text"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Brief description of what this runbook does"
              />
            </div>

            {/* Content */}
            <div className="space-y-2">
              <Label htmlFor="content">Content * (Markdown with optional YAML frontmatter)</Label>
              <Textarea
                id="content"
                value={formData.content}
                onChange={(e) => setFormData({ ...formData, content: e.target.value })}
                rows={12}
                className="font-mono text-sm"
                placeholder={`---
steps:
  - name: Check service status
    command: kubectl get pods -n {{namespace}}
  - name: Restart deployment
    command: kubectl rollout restart deployment/{{service}}
variables:
  namespace: production
  service: api-server
---

# Database Connection Recovery

This runbook handles database connection issues...`}
              />
            </div>

            {/* Tags */}
            <div className="space-y-2">
              <Label>Tags</Label>
              <div className="flex items-center gap-2 mb-2">
                <Input
                  type="text"
                  value={newTag}
                  onChange={(e) => setNewTag(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addTag())}
                  placeholder="Add tag"
                  className="flex-1"
                />
                <Button type="button" variant="secondary" onClick={addTag} className="border border-border text-foreground hover:bg-accent">
                  Add
                </Button>
              </div>
              <div className="flex flex-wrap gap-2">
                {formData.tags.map((tag, i) => (
                  <span key={i} className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-blue-500/10 text-blue-400 border-blue-500/20 flex items-center gap-1">
                    {tag}
                    <button onClick={() => removeTag(tag)} className="hover:text-red-400">
                      <XCircle className="h-4 w-4" />
                    </button>
                  </span>
                ))}
              </div>
            </div>

            {/* Service Names */}
            <div className="space-y-2">
              <Label>Service Names</Label>
              <div className="flex items-center gap-2 mb-2">
                <Input
                  type="text"
                  value={newServiceName}
                  onChange={(e) => setNewServiceName(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addServiceName())}
                  placeholder="Add service name"
                  className="flex-1"
                />
                <Button type="button" variant="secondary" onClick={addServiceName} className="border border-border text-foreground hover:bg-accent">
                  Add
                </Button>
              </div>
              <div className="flex flex-wrap gap-2">
                {formData.service_names.map((name, i) => (
                  <span key={i} className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-emerald-500/10 text-emerald-400 border-emerald-500/20 flex items-center gap-1">
                    {name}
                    <button onClick={() => removeServiceName(name)} className="hover:text-red-400">
                      <XCircle className="h-4 w-4" />
                    </button>
                  </span>
                ))}
              </div>
            </div>

            {/* Alert Patterns */}
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <Label>Alert Patterns (for auto-suggestions)</Label>
                <Button type="button" variant="ghost" size="sm" onClick={addPattern} className="text-muted-foreground hover:text-foreground hover:bg-accent">
                  + Add Pattern
                </Button>
              </div>
              <div className="space-y-2">
                {formData.alert_patterns.map((pattern, i) => (
                  <div key={i} className="flex gap-2 items-center">
                    <Select
                      value={pattern.field}
                      onChange={(e) => updatePattern(i, 'field', e.target.value)}
                    >
                      {PATTERN_FIELDS.map(f => (
                        <option key={f.value} value={f.value}>{f.label}</option>
                      ))}
                    </Select>
                    <Select
                      value={pattern.operator}
                      onChange={(e) => updatePattern(i, 'operator', e.target.value)}
                    >
                      {PATTERN_OPERATORS.map(o => (
                        <option key={o.value} value={o.value}>{o.label}</option>
                      ))}
                    </Select>
                    <Input
                      type="text"
                      value={pattern.value}
                      onChange={(e) => updatePattern(i, 'value', e.target.value)}
                      placeholder="Pattern value"
                      className="flex-1"
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => removePattern(i)}
                      className="text-red-400 hover:text-red-400"
                    >
                      <Trash2 className="h-5 w-5" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>

            {/* Active Toggle */}
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                id="is_active"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                className="h-4 w-4 rounded border-border"
              />
              <Label htmlFor="is_active" className="font-normal text-muted-foreground">
                Runbook is active (available for suggestions and execution)
              </Label>
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-border">
            <Button
              variant="ghost"
              onClick={() => {
                setShowCreateModal(false);
                setEditingRunbook(null);
                resetForm();
              }}
              className="text-muted-foreground hover:text-foreground hover:bg-accent"
            >
              Cancel
            </Button>
            <Button
              onClick={handleSaveRunbook}
              disabled={saving || !formData.title || !formData.content}
              className="bg-primary text-primary-foreground hover:bg-white/90 gap-2"
            >
              {saving && <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-black"></div>}
              {editingRunbook ? 'Update Runbook' : 'Create Runbook'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Modal */}
      <Dialog open={!!showDeleteModal} onOpenChange={() => setShowDeleteModal(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Delete Runbook</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete "{showDeleteModal?.title}"? This action cannot be undone.
          </p>
          <div className="flex items-center justify-end gap-3 pt-4">
            <Button variant="ghost" onClick={() => setShowDeleteModal(null)} className="text-muted-foreground hover:text-foreground hover:bg-accent">
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDeleteRunbook}>
              Delete
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default RunbookManager;
