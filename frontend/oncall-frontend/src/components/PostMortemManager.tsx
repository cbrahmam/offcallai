// PostMortemManager.tsx - Refactored with shadcn/ui
import React, { useState, useEffect, useCallback } from 'react';
import {
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Clock,
  Eye,
  FileText,
  MessageSquare,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  Trash2,
  X,
  Zap
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Label } from './ui/label';
import { Select } from './ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';

import { API_URL as API_BASE_URL } from '../config/api';

type PostMortemStatus = 'draft' | 'in_review' | 'published' | 'archived';

interface TimelineEvent {
  time: string;
  description: string;
  actor?: string;
}

interface ActionItem {
  id: string;
  description: string;
  assignee_id?: string;
  assignee_name?: string;
  due_date?: string;
  status: 'open' | 'in_progress' | 'completed';
  priority: 'low' | 'medium' | 'high';
}

interface PostMortem {
  id: string;
  organization_id: string;
  incident_id: string;
  title: string;
  status: PostMortemStatus;
  summary?: string;
  impact?: string;
  root_cause?: string;
  resolution?: string;
  lessons_learned?: string;
  timeline: TimelineEvent[];
  action_items: ActionItem[];
  detection_time_minutes?: number;
  response_time_minutes?: number;
  resolution_time_minutes?: number;
  total_downtime_minutes?: number;
  assessed_severity?: string;
  customer_impact_score?: number;
  tags: string[];
  contributing_factors: string[];
  created_by_id: string;
  created_by_name?: string;
  reviewed_by_id?: string;
  reviewed_by_name?: string;
  reviewed_at?: string;
  published_by_id?: string;
  published_at?: string;
  created_at: string;
  updated_at?: string;
  incident_title?: string;
  incident_severity?: string;
}

interface Comment {
  id: string;
  post_mortem_id: string;
  user_id: string;
  user_name?: string;
  content: string;
  section?: string;
  created_at: string;
}

interface Incident {
  id: string;
  title: string;
  severity: string;
  status: string;
}

interface PostMortemFormData {
  incident_id: string;
  title: string;
  summary: string;
  impact: string;
  root_cause: string;
  resolution: string;
  lessons_learned: string;
  assessed_severity: string;
  customer_impact_score: number | null;
  tags: string;
  contributing_factors: string;
  detection_time_minutes: number | null;
  response_time_minutes: number | null;
  resolution_time_minutes: number | null;
  total_downtime_minutes: number | null;
}

const getStatusVariant = (status: PostMortemStatus): "default" | "success" | "warning" | "error" | "info" => {
  switch (status) {
    case 'draft': return 'default';
    case 'in_review': return 'warning';
    case 'published': return 'success';
    case 'archived': return 'info';
    default: return 'default';
  }
};

const getSeverityVariant = (severity: string): "default" | "success" | "warning" | "error" | "info" => {
  switch (severity) {
    case 'low': return 'info';
    case 'medium': return 'warning';
    case 'high': return 'error';
    case 'critical': return 'error';
    default: return 'default';
  }
};

const statusLabels: Record<PostMortemStatus, string> = {
  draft: 'Draft',
  in_review: 'In Review',
  published: 'Published',
  archived: 'Archived'
};

const PostMortemManager: React.FC = () => {
  const { token } = useAuth();
  const [postMortems, setPostMortems] = useState<PostMortem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingPostMortem, setEditingPostMortem] = useState<PostMortem | null>(null);
  const [viewingPostMortem, setViewingPostMortem] = useState<PostMortem | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [newComment, setNewComment] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [statusFilter, setStatusFilter] = useState<PostMortemStatus | ''>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [expandedTimeline, setExpandedTimeline] = useState(false);
  const [expandedActionItems, setExpandedActionItems] = useState(false);
  const [showAIGenerateModal, setShowAIGenerateModal] = useState(false);
  const [selectedIncidentForAI, setSelectedIncidentForAI] = useState<string>('');
  const [generatingAI, setGeneratingAI] = useState(false);

  const initialFormData: PostMortemFormData = {
    incident_id: '',
    title: '',
    summary: '',
    impact: '',
    root_cause: '',
    resolution: '',
    lessons_learned: '',
    assessed_severity: 'medium',
    customer_impact_score: null,
    tags: '',
    contributing_factors: '',
    detection_time_minutes: null,
    response_time_minutes: null,
    resolution_time_minutes: null,
    total_downtime_minutes: null
  };

  const [formData, setFormData] = useState<PostMortemFormData>(initialFormData);

  const loadPostMortems = useCallback(async () => {
    if (!token) return;

    try {
      setLoading(true);
      const params = new URLSearchParams({
        page: page.toString(),
        per_page: '20'
      });
      if (statusFilter) params.append('status', statusFilter);
      if (searchQuery) params.append('search', searchQuery);

      const response = await fetch(
        `${API_BASE_URL}/post-mortems/?${params}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );

      if (!response.ok) throw new Error('Failed to fetch post-mortems');

      const data = await response.json();
      setPostMortems(data.post_mortems);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token, page, statusFilter, searchQuery]);

  const loadIncidents = useCallback(async () => {
    if (!token) return;

    try {
      const response = await fetch(
        `${API_BASE_URL}/incidents/?status=resolved&per_page=100`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );

      if (response.ok) {
        const data = await response.json();
        setIncidents(data.incidents || []);
      }
    } catch (err) {
      console.error('Failed to load incidents:', err);
    }
  }, [token]);

  const loadComments = useCallback(async (postMortemId: string) => {
    if (!token) return;

    try {
      const response = await fetch(
        `${API_BASE_URL}/post-mortems/${postMortemId}/comments`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );

      if (response.ok) {
        const data = await response.json();
        setComments(data);
      }
    } catch (err) {
      console.error('Failed to load comments:', err);
    }
  }, [token]);

  useEffect(() => {
    loadPostMortems();
  }, [loadPostMortems]);

  useEffect(() => {
    if ((showCreateModal || showAIGenerateModal) && incidents.length === 0) {
      loadIncidents();
    }
  }, [showCreateModal, showAIGenerateModal, incidents.length, loadIncidents]);

  useEffect(() => {
    if (viewingPostMortem) {
      loadComments(viewingPostMortem.id);
    }
  }, [viewingPostMortem, loadComments]);

  const resetForm = () => {
    setFormData(initialFormData);
    setEditingPostMortem(null);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;

    setSubmitting(true);
    try {
      const payload = {
        incident_id: formData.incident_id,
        title: formData.title,
        summary: formData.summary || null,
        impact: formData.impact || null,
        root_cause: formData.root_cause || null,
        resolution: formData.resolution || null,
        lessons_learned: formData.lessons_learned || null,
        assessed_severity: formData.assessed_severity || null,
        customer_impact_score: formData.customer_impact_score,
        tags: formData.tags.split(',').map(t => t.trim()).filter(Boolean),
        contributing_factors: formData.contributing_factors.split(',').map(f => f.trim()).filter(Boolean),
        detection_time_minutes: formData.detection_time_minutes,
        response_time_minutes: formData.response_time_minutes,
        resolution_time_minutes: formData.resolution_time_minutes,
        total_downtime_minutes: formData.total_downtime_minutes,
        timeline: [],
        action_items: []
      };

      const url = editingPostMortem
        ? `${API_BASE_URL}/post-mortems/${editingPostMortem.id}`
        : `${API_BASE_URL}/post-mortems/`;

      const response = await fetch(url, {
        method: editingPostMortem ? 'PATCH' : 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Failed to save post-mortem');
      }

      setShowCreateModal(false);
      resetForm();
      loadPostMortems();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!token || !window.confirm('Are you sure you want to delete this post-mortem?')) return;

    try {
      const response = await fetch(`${API_BASE_URL}/post-mortems/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) throw new Error('Failed to delete post-mortem');

      loadPostMortems();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleWorkflowAction = async (id: string, action: 'submit-for-review' | 'publish' | 'archive') => {
    if (!token) return;

    try {
      const response = await fetch(`${API_BASE_URL}/post-mortems/${id}/${action}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) throw new Error(`Failed to ${action.replace('-', ' ')}`);

      loadPostMortems();
      if (viewingPostMortem?.id === id) {
        const updatedData = await response.json();
        setViewingPostMortem(updatedData);
      }
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleAddComment = async () => {
    if (!token || !viewingPostMortem || !newComment.trim()) return;

    try {
      const response = await fetch(
        `${API_BASE_URL}/post-mortems/${viewingPostMortem.id}/comments`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ content: newComment })
        }
      );

      if (!response.ok) throw new Error('Failed to add comment');

      setNewComment('');
      loadComments(viewingPostMortem.id);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleActionItemStatus = async (postMortemId: string, actionItemId: string, status: string) => {
    if (!token) return;

    try {
      const response = await fetch(
        `${API_BASE_URL}/post-mortems/${postMortemId}/action-items/${actionItemId}?status=${status}`,
        {
          method: 'PATCH',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );

      if (!response.ok) throw new Error('Failed to update action item');

      const updatedData = await response.json();
      if (viewingPostMortem?.id === postMortemId) {
        setViewingPostMortem(updatedData);
      }
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleGenerateWithAI = async () => {
    if (!token || !selectedIncidentForAI) return;

    setGeneratingAI(true);
    setError(null);

    try {
      const response = await fetch(
        `${API_BASE_URL}/post-mortems/generate/${selectedIncidentForAI}`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Failed to generate post-mortem with AI');
      }

      const generatedPostMortem = await response.json();

      setShowAIGenerateModal(false);
      setSelectedIncidentForAI('');
      loadPostMortems();
      setViewingPostMortem(generatedPostMortem);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setGeneratingAI(false);
    }
  };

  const openEdit = (pm: PostMortem) => {
    setFormData({
      incident_id: pm.incident_id,
      title: pm.title,
      summary: pm.summary || '',
      impact: pm.impact || '',
      root_cause: pm.root_cause || '',
      resolution: pm.resolution || '',
      lessons_learned: pm.lessons_learned || '',
      assessed_severity: pm.assessed_severity || 'medium',
      customer_impact_score: pm.customer_impact_score ?? null,
      tags: pm.tags.join(', '),
      contributing_factors: pm.contributing_factors.join(', '),
      detection_time_minutes: pm.detection_time_minutes ?? null,
      response_time_minutes: pm.response_time_minutes ?? null,
      resolution_time_minutes: pm.resolution_time_minutes ?? null,
      total_downtime_minutes: pm.total_downtime_minutes ?? null
    });
    setEditingPostMortem(pm);
    setShowCreateModal(true);
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  const formatMinutes = (minutes?: number) => {
    if (!minutes) return '-';
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
  };

  // Detail View Modal
  const renderDetailView = () => {
    if (!viewingPostMortem) return null;

    return (
      <Dialog open={!!viewingPostMortem} onOpenChange={() => setViewingPostMortem(null)}>
        <DialogContent className="max-w-5xl max-h-[90vh] overflow-hidden flex flex-col" onClose={() => setViewingPostMortem(null)}>
          {/* Header */}
          <DialogHeader>
            <div className="flex items-center justify-between">
              <div>
                <DialogTitle>{viewingPostMortem.title}</DialogTitle>
                <div className="flex items-center gap-2 mt-2">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${
                    getStatusVariant(viewingPostMortem.status) === 'success' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
                    getStatusVariant(viewingPostMortem.status) === 'warning' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                    getStatusVariant(viewingPostMortem.status) === 'error' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                    getStatusVariant(viewingPostMortem.status) === 'info' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' :
                    'bg-secondary text-muted-foreground border-border'
                  }`}>
                    {statusLabels[viewingPostMortem.status]}
                  </span>
                  {viewingPostMortem.incident_severity && (
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${
                      getSeverityVariant(viewingPostMortem.incident_severity) === 'error' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                      getSeverityVariant(viewingPostMortem.incident_severity) === 'warning' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                      getSeverityVariant(viewingPostMortem.incident_severity) === 'info' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' :
                      'bg-secondary text-muted-foreground border-border'
                    }`}>
                      {viewingPostMortem.incident_severity}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {viewingPostMortem.status === 'draft' && (
                  <Button
                    size="sm"
                    onClick={() => handleWorkflowAction(viewingPostMortem.id, 'submit-for-review')}
                    className="bg-yellow-600 hover:bg-yellow-700"
                  >
                    Submit for Review
                  </Button>
                )}
                {viewingPostMortem.status === 'in_review' && (
                  <Button
                    size="sm"
                    onClick={() => handleWorkflowAction(viewingPostMortem.id, 'publish')}
                    className="bg-green-600 hover:bg-green-700"
                  >
                    Publish
                  </Button>
                )}
                {viewingPostMortem.status === 'published' && (
                  <Button
                    size="sm"
                    onClick={() => handleWorkflowAction(viewingPostMortem.id, 'archive')}
                  >
                    Archive
                  </Button>
                )}
              </div>
            </div>
          </DialogHeader>

          {/* Content */}
          <div className="flex-1 overflow-y-auto space-y-6 mt-4">
            {/* Metrics Row */}
            <div className="grid grid-cols-4 gap-4">
              {[
                { label: 'Detection Time', value: formatMinutes(viewingPostMortem.detection_time_minutes) },
                { label: 'Response Time', value: formatMinutes(viewingPostMortem.response_time_minutes) },
                { label: 'Resolution Time', value: formatMinutes(viewingPostMortem.resolution_time_minutes) },
                { label: 'Total Downtime', value: formatMinutes(viewingPostMortem.total_downtime_minutes) }
              ].map((metric, idx) => (
                <div key={idx} className="bg-secondary rounded-lg p-4">
                  <div className="text-xs text-muted-foreground uppercase tracking-wide">{metric.label}</div>
                  <div className="text-base font-medium text-foreground mt-1">{metric.value}</div>
                </div>
              ))}
            </div>

            {/* Summary */}
            {viewingPostMortem.summary && (
              <div>
                <h3 className="text-sm font-medium text-foreground mb-2">Summary</h3>
                <p className="text-muted-foreground whitespace-pre-wrap">{viewingPostMortem.summary}</p>
              </div>
            )}

            {/* Impact */}
            {viewingPostMortem.impact && (
              <div>
                <h3 className="text-sm font-medium text-foreground mb-2">Impact</h3>
                <p className="text-muted-foreground whitespace-pre-wrap">{viewingPostMortem.impact}</p>
              </div>
            )}

            {/* Root Cause */}
            {viewingPostMortem.root_cause && (
              <div>
                <h3 className="text-sm font-medium text-foreground mb-2">Root Cause</h3>
                <p className="text-muted-foreground whitespace-pre-wrap">{viewingPostMortem.root_cause}</p>
              </div>
            )}

            {/* Resolution */}
            {viewingPostMortem.resolution && (
              <div>
                <h3 className="text-sm font-medium text-foreground mb-2">Resolution</h3>
                <p className="text-muted-foreground whitespace-pre-wrap">{viewingPostMortem.resolution}</p>
              </div>
            )}

            {/* Lessons Learned */}
            {viewingPostMortem.lessons_learned && (
              <div>
                <h3 className="text-sm font-medium text-foreground mb-2">Lessons Learned</h3>
                <p className="text-muted-foreground whitespace-pre-wrap">{viewingPostMortem.lessons_learned}</p>
              </div>
            )}

            {/* Timeline */}
            {viewingPostMortem.timeline.length > 0 && (
              <div>
                <button
                  onClick={() => setExpandedTimeline(!expandedTimeline)}
                  className="flex items-center gap-2 text-sm font-medium text-foreground mb-2"
                >
                  Timeline ({viewingPostMortem.timeline.length} events)
                  {expandedTimeline ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </button>
                {expandedTimeline && (
                  <div className="space-y-2 border-l-2 border-border pl-4 ml-2">
                    {viewingPostMortem.timeline.map((event, idx) => (
                      <div key={idx} className="relative">
                        <div className="absolute -left-[21px] w-2 h-2 bg-secondary-foreground rounded-full" />
                        <div className="text-xs text-muted-foreground">{formatDate(event.time)}</div>
                        <div className="text-sm text-foreground">{event.description}</div>
                        {event.actor && <div className="text-xs text-muted-foreground">by {event.actor}</div>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Action Items */}
            {viewingPostMortem.action_items.length > 0 && (
              <div>
                <button
                  onClick={() => setExpandedActionItems(!expandedActionItems)}
                  className="flex items-center gap-2 text-sm font-medium text-foreground mb-2"
                >
                  Action Items ({viewingPostMortem.action_items.length})
                  {expandedActionItems ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </button>
                {expandedActionItems && (
                  <div className="space-y-2">
                    {viewingPostMortem.action_items.map((item) => (
                      <div key={item.id} className="flex items-center gap-3 p-3 bg-secondary rounded-lg">
                        <select
                          value={item.status}
                          onChange={(e) => handleActionItemStatus(viewingPostMortem.id, item.id, e.target.value)}
                          className="text-xs border border-border rounded px-2 py-1 bg-background text-foreground"
                        >
                          <option value="open">Open</option>
                          <option value="in_progress">In Progress</option>
                          <option value="completed">Completed</option>
                        </select>
                        <div className="flex-1">
                          <div className={`text-sm ${item.status === 'completed' ? 'line-through text-muted-foreground' : 'text-foreground'}`}>
                            {item.description}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {item.assignee_name && `Assigned to: ${item.assignee_name}`}
                            {item.due_date && ` | Due: ${new Date(item.due_date).toLocaleDateString()}`}
                          </div>
                        </div>
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${
                          item.priority === 'high' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                          item.priority === 'medium' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                          'bg-blue-500/10 text-blue-400 border-blue-500/20'
                        }`}>
                          {item.priority}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Contributing Factors */}
            {viewingPostMortem.contributing_factors.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-foreground mb-2">Contributing Factors</h3>
                <div className="flex flex-wrap items-center gap-2">
                  {viewingPostMortem.contributing_factors.map((factor, idx) => (
                    <span key={idx} className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-yellow-500/10 text-yellow-400 border-yellow-500/20">{factor}</span>
                  ))}
                </div>
              </div>
            )}

            {/* Tags */}
            {viewingPostMortem.tags.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-foreground mb-2">Tags</h3>
                <div className="flex flex-wrap items-center gap-2">
                  {viewingPostMortem.tags.map((tag, idx) => (
                    <span key={idx} className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-secondary text-muted-foreground border-border">{tag}</span>
                  ))}
                </div>
              </div>
            )}

            {/* Comments Section */}
            <div className="border-t border-border pt-4">
              <h3 className="text-sm font-medium text-foreground mb-3 flex items-center gap-2">
                <MessageSquare className="h-4 w-4" />
                Comments ({comments.length})
              </h3>

              <div className="space-y-3 mb-4">
                {comments.map((comment) => (
                  <div key={comment.id} className="bg-secondary rounded-lg p-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium text-foreground">{comment.user_name || 'Unknown'}</span>
                      <span className="text-xs text-muted-foreground">{formatDate(comment.created_at)}</span>
                    </div>
                    <p className="text-sm text-muted-foreground">{comment.content}</p>
                  </div>
                ))}
              </div>

              <div className="flex items-center gap-2">
                <Input
                  type="text"
                  value={newComment}
                  onChange={(e) => setNewComment(e.target.value)}
                  placeholder="Add a comment..."
                  className="flex-1"
                  onKeyPress={(e) => e.key === 'Enter' && handleAddComment()}
                />
                <Button onClick={handleAddComment} disabled={!newComment.trim()}>
                  Add
                </Button>
              </div>
            </div>

            {/* Metadata */}
            <div className="border-t border-border pt-4 text-xs text-muted-foreground">
              <div>Created by: {viewingPostMortem.created_by_name || 'Unknown'} on {formatDate(viewingPostMortem.created_at)}</div>
              {viewingPostMortem.published_at && (
                <div>Published on: {formatDate(viewingPostMortem.published_at)}</div>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>
    );
  };

  // Create/Edit Modal
  const renderCreateModal = () => (
    <Dialog open={showCreateModal} onOpenChange={(open) => { if (!open) { setShowCreateModal(false); resetForm(); } }}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-hidden flex flex-col" onClose={() => { setShowCreateModal(false); resetForm(); }}>
        <DialogHeader>
          <DialogTitle>
            {editingPostMortem ? 'Edit Post-Mortem' : 'Create Post-Mortem'}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleCreate} className="flex-1 overflow-y-auto space-y-4 mt-4">
          {/* Incident Selection */}
          {!editingPostMortem && (
            <div className="space-y-2">
              <Label>Incident *</Label>
              <Select
                value={formData.incident_id}
                onChange={(e) => setFormData({ ...formData, incident_id: e.target.value })}
                required
              >
                <option value="">Select an incident...</option>
                {incidents.map((inc) => (
                  <option key={inc.id} value={inc.id}>
                    {inc.title} ({inc.severity})
                  </option>
                ))}
              </Select>
            </div>
          )}

          {/* Title */}
          <div className="space-y-2">
            <Label>Title *</Label>
            <Input
              type="text"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              required
              placeholder="Post-Mortem: Database Outage on Jan 9"
            />
          </div>

          {/* Summary */}
          <div className="space-y-2">
            <Label>Executive Summary</Label>
            <Textarea
              value={formData.summary}
              onChange={(e) => setFormData({ ...formData, summary: e.target.value })}
              rows={3}
              placeholder="Brief overview of what happened..."
            />
          </div>

          {/* Impact */}
          <div className="space-y-2">
            <Label>Impact</Label>
            <Textarea
              value={formData.impact}
              onChange={(e) => setFormData({ ...formData, impact: e.target.value })}
              rows={2}
              placeholder="Business and user impact..."
            />
          </div>

          {/* Root Cause */}
          <div className="space-y-2">
            <Label>Root Cause</Label>
            <Textarea
              value={formData.root_cause}
              onChange={(e) => setFormData({ ...formData, root_cause: e.target.value })}
              rows={2}
              placeholder="What was the root cause..."
            />
          </div>

          {/* Resolution */}
          <div className="space-y-2">
            <Label>Resolution</Label>
            <Textarea
              value={formData.resolution}
              onChange={(e) => setFormData({ ...formData, resolution: e.target.value })}
              rows={2}
              placeholder="How was the incident resolved..."
            />
          </div>

          {/* Lessons Learned */}
          <div className="space-y-2">
            <Label>Lessons Learned</Label>
            <Textarea
              value={formData.lessons_learned}
              onChange={(e) => setFormData({ ...formData, lessons_learned: e.target.value })}
              rows={2}
              placeholder="Key takeaways and improvements..."
            />
          </div>

          {/* Metrics Row */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Detection Time (minutes)</Label>
              <Input
                type="number"
                value={formData.detection_time_minutes ?? ''}
                onChange={(e) => setFormData({ ...formData, detection_time_minutes: e.target.value ? parseInt(e.target.value) : null })}
              />
            </div>
            <div className="space-y-2">
              <Label>Response Time (minutes)</Label>
              <Input
                type="number"
                value={formData.response_time_minutes ?? ''}
                onChange={(e) => setFormData({ ...formData, response_time_minutes: e.target.value ? parseInt(e.target.value) : null })}
              />
            </div>
            <div className="space-y-2">
              <Label>Resolution Time (minutes)</Label>
              <Input
                type="number"
                value={formData.resolution_time_minutes ?? ''}
                onChange={(e) => setFormData({ ...formData, resolution_time_minutes: e.target.value ? parseInt(e.target.value) : null })}
              />
            </div>
            <div className="space-y-2">
              <Label>Total Downtime (minutes)</Label>
              <Input
                type="number"
                value={formData.total_downtime_minutes ?? ''}
                onChange={(e) => setFormData({ ...formData, total_downtime_minutes: e.target.value ? parseInt(e.target.value) : null })}
              />
            </div>
          </div>

          {/* Severity and Impact Score */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Assessed Severity</Label>
              <Select
                value={formData.assessed_severity}
                onChange={(e) => setFormData({ ...formData, assessed_severity: e.target.value })}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Customer Impact Score (1-10)</Label>
              <Input
                type="number"
                min="1"
                max="10"
                value={formData.customer_impact_score ?? ''}
                onChange={(e) => setFormData({ ...formData, customer_impact_score: e.target.value ? parseInt(e.target.value) : null })}
              />
            </div>
          </div>

          {/* Tags and Contributing Factors */}
          <div className="space-y-2">
            <Label>Tags (comma-separated)</Label>
            <Input
              type="text"
              value={formData.tags}
              onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
              placeholder="database, outage, production"
            />
          </div>

          <div className="space-y-2">
            <Label>Contributing Factors (comma-separated)</Label>
            <Input
              type="text"
              value={formData.contributing_factors}
              onChange={(e) => setFormData({ ...formData, contributing_factors: e.target.value })}
              placeholder="missing monitoring, lack of runbook"
            />
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
              {submitting ? 'Saving...' : editingPostMortem ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-slate-500/10">
                <FileText className="w-6 h-6 text-slate-400" />
              </div>
              <div>
                <h1 className="text-base font-medium text-foreground">Post-Mortems</h1>
                <p className="text-muted-foreground text-sm">Document and learn from incidents</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Button
                onClick={() => setShowAIGenerateModal(true)}
                variant="outline"
                className="border-border text-foreground hover:bg-accent"
              >
                <Sparkles className="h-5 w-5 mr-2" />
                Generate with AI
              </Button>
              <Button onClick={() => setShowCreateModal(true)} className="bg-primary text-primary-foreground hover:bg-white/90">
                <Plus className="h-5 w-5 mr-2" />
                New Post-Mortem
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* Error Display */}
      {error && (
        <div className="mb-4 border border-red-500/20 bg-red-500/10 rounded-lg">
          <div className="p-4 flex items-center gap-2 text-red-400">
            <AlertTriangle className="h-5 w-5" />
            {error}
            <button onClick={() => setError(null)} className="ml-auto">
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="mb-4 flex items-center gap-4">
        <div className="flex-1 relative">
          <Search className="h-5 w-5 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search post-mortems..."
            className="pl-10"
          />
        </div>
        <Select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as PostMortemStatus | '')}
        >
          <option value="">All Statuses</option>
          <option value="draft">Draft</option>
          <option value="in_review">In Review</option>
          <option value="published">Published</option>
          <option value="archived">Archived</option>
        </Select>
        <Button variant="ghost" onClick={loadPostMortems} size="sm">
          <RefreshCw className={`h-5 w-5 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {/* List */}
      {loading ? (
        <div className="text-center py-12 text-muted-foreground">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white mx-auto mb-4"></div>
          Loading...
        </div>
      ) : postMortems.length === 0 ? (
        <div className="border border-border rounded-lg bg-transparent">
          <div className="p-6 text-center py-12">
            <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
            <p className="text-foreground">No post-mortems found</p>
            <p className="text-muted-foreground text-sm mt-1">Create your first post-mortem to document incident learnings</p>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {postMortems.map((pm) => (
            <div key={pm.id} className="border border-border rounded-lg bg-transparent hover:bg-accent/50 transition-colors">
              <div className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-medium text-foreground truncate">{pm.title}</h3>
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${
                        getStatusVariant(pm.status) === 'success' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
                        getStatusVariant(pm.status) === 'warning' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                        getStatusVariant(pm.status) === 'error' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                        getStatusVariant(pm.status) === 'info' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' :
                        'bg-secondary text-muted-foreground border-border'
                      }`}>
                        {statusLabels[pm.status]}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                      <span>Incident: {pm.incident_title || 'Unknown'}</span>
                      {pm.incident_severity && (
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${
                          getSeverityVariant(pm.incident_severity) === 'error' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                          getSeverityVariant(pm.incident_severity) === 'warning' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                          getSeverityVariant(pm.incident_severity) === 'info' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' :
                          'bg-secondary text-muted-foreground border-border'
                        }`}>
                          {pm.incident_severity}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-4 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Clock className="h-3.5 w-3.5" />
                        {formatDate(pm.created_at)}
                      </span>
                      {pm.created_by_name && <span>by {pm.created_by_name}</span>}
                      {pm.action_items.length > 0 && (
                        <span>{pm.action_items.filter(a => a.status === 'completed').length}/{pm.action_items.length} actions completed</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 ml-4">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setViewingPostMortem(pm)}
                    >
                      <Eye className="h-5 w-5" />
                    </Button>
                    {pm.status === 'draft' && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openEdit(pm)}
                      >
                        <Pencil className="h-5 w-5" />
                      </Button>
                    )}
                    {pm.status === 'draft' && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(pm.id)}
                        className="text-red-400 hover:text-red-400"
                      >
                        <Trash2 className="h-5 w-5" />
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {total > 20 && (
        <div className="mt-4 flex items-center justify-center gap-4">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {Math.ceil(total / 20)}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(p => p + 1)}
            disabled={page * 20 >= total}
          >
            Next
          </Button>
        </div>
      )}

      {/* Modals */}
      {showCreateModal && renderCreateModal()}
      {viewingPostMortem && renderDetailView()}

      {/* AI Generate Modal */}
      <Dialog open={showAIGenerateModal} onOpenChange={(open) => { if (!open) { setShowAIGenerateModal(false); setSelectedIncidentForAI(''); } }}>
        <DialogContent onClose={() => { setShowAIGenerateModal(false); setSelectedIncidentForAI(''); }}>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Sparkles className="h-6 w-6 text-purple-600" />
              Generate Post-Mortem with AI
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 mt-4">
            <p className="text-sm text-muted-foreground">
              Select an incident to automatically generate a comprehensive post-mortem report using AI.
              The AI will analyze the incident data, alerts, and timeline to create a draft you can review and edit.
            </p>

            <div className="space-y-2">
              <Label>Select Incident</Label>
              <Select
                value={selectedIncidentForAI}
                onChange={(e) => setSelectedIncidentForAI(e.target.value)}
                disabled={generatingAI}
              >
                <option value="">Choose an incident...</option>
                {incidents.map((inc) => (
                  <option key={inc.id} value={inc.id}>
                    {inc.title} ({inc.severity}) - {inc.status}
                  </option>
                ))}
              </Select>
            </div>

            {generatingAI && (
              <div className="p-4 bg-purple-500/10 rounded-lg border border-purple-500/20">
                <div className="flex items-center gap-3">
                  <div className="animate-spin rounded-full h-5 w-5 border-2 border-purple-600 border-t-transparent"></div>
                  <div>
                    <p className="text-sm font-medium text-purple-400">Generating post-mortem...</p>
                    <p className="text-xs text-purple-300">AI is analyzing incident data and creating your report</p>
                  </div>
                </div>
              </div>
            )}

            <div className="border border-border rounded-lg bg-transparent">
              <div className="p-4">
                <h4 className="text-sm font-medium text-foreground mb-2 flex items-center gap-2">
                  <Zap className="h-4 w-4 text-yellow-500" />
                  What AI will generate:
                </h4>
                <ul className="text-xs text-muted-foreground space-y-1">
                  <li>• Executive summary of the incident</li>
                  <li>• Impact analysis and root cause</li>
                  <li>• Resolution steps and timeline</li>
                  <li>• Lessons learned and action items</li>
                  <li>• Contributing factors</li>
                </ul>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => { setShowAIGenerateModal(false); setSelectedIncidentForAI(''); }}
              disabled={generatingAI}
            >
              Cancel
            </Button>
            <Button
              onClick={handleGenerateWithAI}
              disabled={!selectedIncidentForAI || generatingAI}
              className="bg-primary text-primary-foreground hover:bg-white/90"
            >
              {generatingAI ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent mr-2"></div>
                  Generating...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4 mr-2" />
                  Generate
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      </div>
    </div>
  );
};

export default PostMortemManager;
