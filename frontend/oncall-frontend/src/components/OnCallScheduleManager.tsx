// OnCallScheduleManager.tsx - Refactored with shadcn/ui
import React, { useState, useEffect, useCallback } from 'react';
import {
  CalendarDays,
  ChevronDown,
  ChevronUp,
  Clock,
  Globe,
  Pencil,
  Plus,
  Search,
  Trash2,
  User,
  Users
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useNotifications } from '../contexts/NotificationContext';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Label } from './ui/label';
import { Select } from './ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from './ui/dialog';

import { API_URL as API_BASE_URL } from '../config/api';

const DAYS_OF_WEEK = [
  { value: 0, label: 'Monday', short: 'Mon' },
  { value: 1, label: 'Tuesday', short: 'Tue' },
  { value: 2, label: 'Wednesday', short: 'Wed' },
  { value: 3, label: 'Thursday', short: 'Thu' },
  { value: 4, label: 'Friday', short: 'Fri' },
  { value: 5, label: 'Saturday', short: 'Sat' },
  { value: 6, label: 'Sunday', short: 'Sun' }
];

const TIMEZONES = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'Asia/Tokyo',
  'Asia/Shanghai',
  'Asia/Kolkata',
  'Australia/Sydney'
];

const NOTIFY_CHANNELS = [
  { value: 'email', label: 'Email' },
  { value: 'sms', label: 'SMS' },
  { value: 'slack', label: 'Slack' },
  { value: 'push', label: 'Push' }
];

interface UserSummary {
  id: string;
  email: string;
  full_name: string | null;
}

interface TeamSummary {
  id: string;
  name: string;
}

interface OnCallShift {
  id: string;
  schedule_id: string;
  user_id: string;
  user: UserSummary | null;
  shift_type: string;
  day_of_week: number | null;
  start_time: string | null;
  end_time: string | null;
  start_datetime: string | null;
  end_datetime: string | null;
  notify_channels: string[];
  created_at: string;
}

interface OnCallSchedule {
  id: string;
  organization_id: string;
  team_id: string | null;
  team: TeamSummary | null;
  name: string;
  description: string | null;
  timezone: string;
  is_active: boolean;
  escalation_policy_id: string | null;
  shifts: OnCallShift[];
  created_at: string;
  updated_at: string | null;
  created_by: UserSummary | null;
}

interface ScheduleListResponse {
  schedules: OnCallSchedule[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

interface TeamMember {
  id: string;
  full_name: string;
  email: string;
}

interface ShiftFormData {
  user_id: string;
  shift_type: string;
  day_of_week: number;
  start_time: string;
  end_time: string;
  notify_channels: string[];
}

const OnCallScheduleManager: React.FC = () => {
  const { token } = useAuth();
  const { showToast } = useNotifications();

  const [schedules, setSchedules] = useState<OnCallSchedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [totalPages, setTotalPages] = useState(1);
  const [currentPage, setCurrentPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterActive, setFilterActive] = useState<boolean | null>(null);
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState<OnCallSchedule | null>(null);
  const [editingSchedule, setEditingSchedule] = useState<OnCallSchedule | null>(null);
  const [expandedSchedule, setExpandedSchedule] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    timezone: 'UTC',
    team_id: '',
    escalation_policy_id: '',
    is_active: true,
    shifts: [] as ShiftFormData[]
  });
  const [saving, setSaving] = useState(false);

  const loadSchedules = useCallback(async () => {
    if (!token) return;

    try {
      setLoading(true);
      const params = new URLSearchParams({
        page: currentPage.toString(),
        per_page: '10'
      });

      if (searchQuery) params.append('search', searchQuery);
      if (filterActive !== null) params.append('is_active', filterActive.toString());

      const response = await fetch(`${API_BASE_URL}/on-call-schedules/?${params}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) throw new Error('Failed to fetch schedules');

      const data: ScheduleListResponse = await response.json();
      setSchedules(data.schedules);
      setTotalPages(data.total_pages);
    } catch (error) {
      console.error('Error loading schedules:', error);
      showToast({ message: 'Failed to load schedules', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [token, currentPage, searchQuery, filterActive, showToast]);

  const loadTeamMembers = useCallback(async () => {
    if (!token) return;

    try {
      const response = await fetch(`${API_BASE_URL}/users/`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setTeamMembers(data.users || data || []);
      }
    } catch (error) {
      console.error('Error loading team members:', error);
    }
  }, [token]);

  useEffect(() => {
    loadSchedules();
    loadTeamMembers();
  }, [loadSchedules, loadTeamMembers]);

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      timezone: 'UTC',
      team_id: '',
      escalation_policy_id: '',
      is_active: true,
      shifts: []
    });
  };

  const openEditModal = (schedule: OnCallSchedule) => {
    setEditingSchedule(schedule);
    setFormData({
      name: schedule.name,
      description: schedule.description || '',
      timezone: schedule.timezone,
      team_id: schedule.team_id || '',
      escalation_policy_id: schedule.escalation_policy_id || '',
      is_active: schedule.is_active,
      shifts: schedule.shifts.map(s => ({
        user_id: s.user_id,
        shift_type: s.shift_type,
        day_of_week: s.day_of_week || 0,
        start_time: s.start_time || '09:00',
        end_time: s.end_time || '17:00',
        notify_channels: s.notify_channels || []
      }))
    });
    setShowCreateModal(true);
  };

  const closeModal = () => {
    setShowCreateModal(false);
    setEditingSchedule(null);
    resetForm();
  };

  const addShift = () => {
    setFormData({
      ...formData,
      shifts: [
        ...formData.shifts,
        {
          user_id: '',
          shift_type: 'recurring',
          day_of_week: 0,
          start_time: '09:00',
          end_time: '17:00',
          notify_channels: ['email']
        }
      ]
    });
  };

  const removeShift = (index: number) => {
    setFormData({
      ...formData,
      shifts: formData.shifts.filter((_, i) => i !== index)
    });
  };

  const updateShift = (index: number, field: keyof ShiftFormData, value: any) => {
    const newShifts = [...formData.shifts];
    newShifts[index] = { ...newShifts[index], [field]: value };
    setFormData({ ...formData, shifts: newShifts });
  };

  const toggleNotifyChannel = (index: number, channel: string) => {
    const shift = formData.shifts[index];
    const channels = shift.notify_channels.includes(channel)
      ? shift.notify_channels.filter(c => c !== channel)
      : [...shift.notify_channels, channel];
    updateShift(index, 'notify_channels', channels);
  };

  const handleSave = async () => {
    if (!token || !formData.name) {
      showToast({ message: 'Schedule name is required', type: 'error' });
      return;
    }

    try {
      setSaving(true);

      const payload = {
        name: formData.name,
        description: formData.description || null,
        timezone: formData.timezone,
        team_id: formData.team_id || null,
        escalation_policy_id: formData.escalation_policy_id || null,
        is_active: formData.is_active,
        shifts: formData.shifts.filter(s => s.user_id).map(s => ({
          user_id: s.user_id,
          shift_type: s.shift_type,
          day_of_week: s.day_of_week,
          start_time: s.start_time,
          end_time: s.end_time,
          notify_channels: s.notify_channels
        }))
      };

      const url = editingSchedule
        ? `${API_BASE_URL}/on-call-schedules/${editingSchedule.id}`
        : `${API_BASE_URL}/on-call-schedules/`;

      const response = await fetch(url, {
        method: editingSchedule ? 'PATCH' : 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to save schedule');
      }

      showToast({
        message: editingSchedule ? 'Schedule updated successfully' : 'Schedule created successfully',
        type: 'success'
      });

      closeModal();
      loadSchedules();
    } catch (error: any) {
      showToast({ message: error.message || 'Failed to save schedule', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!token || !showDeleteModal) return;

    try {
      const response = await fetch(`${API_BASE_URL}/on-call-schedules/${showDeleteModal.id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) throw new Error('Failed to delete schedule');

      showToast({ message: 'Schedule deleted successfully', type: 'success' });
      setShowDeleteModal(null);
      loadSchedules();
    } catch (error) {
      showToast({ message: 'Failed to delete schedule', type: 'error' });
    }
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-green-500/10">
                <CalendarDays className="w-6 h-6 text-green-400" />
              </div>
              <div>
                <h1 className="text-base font-medium text-foreground">On-Call Schedules</h1>
                <p className="text-muted-foreground text-sm">Manage on-call rotations and shift assignments</p>
              </div>
            </div>

            <Button onClick={() => setShowCreateModal(true)} className="bg-primary text-primary-foreground hover:bg-white/90">
              <Plus className="h-5 w-5 mr-2" />
              Create Schedule
            </Button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6">

      {/* Search and Filter */}
      <div className="flex items-center gap-4 mb-6">
        <div className="flex-1 relative">
          <Search className="h-5 w-5 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search schedules..."
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

      {/* Schedules List */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white"></div>
        </div>
      ) : schedules.length === 0 ? (
        <div className="border border-border rounded-lg bg-transparent">
          <div className="p-6 text-center py-12">
            <CalendarDays className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-base font-medium text-foreground">No schedules found</h3>
            <p className="text-muted-foreground mt-1">Create your first on-call schedule to get started</p>
            <Button onClick={() => setShowCreateModal(true)} className="mt-4 bg-primary text-primary-foreground hover:bg-white/90">
              Create Schedule
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {schedules.map((schedule) => (
            <div key={schedule.id} className="border border-border rounded-lg bg-transparent overflow-hidden">
              <div className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="text-base font-medium text-foreground">{schedule.name}</h3>
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${
                        schedule.is_active ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-secondary text-muted-foreground border-border'
                      }`}>
                        {schedule.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                    {schedule.description && (
                      <p className="text-muted-foreground text-sm mt-1">{schedule.description}</p>
                    )}
                    <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Globe className="h-4 w-4" />
                        {schedule.timezone}
                      </span>
                      <span className="flex items-center gap-1">
                        <Users className="h-4 w-4" />
                        {schedule.shifts.length} shift{schedule.shifts.length !== 1 ? 's' : ''}
                      </span>
                      {schedule.team && (
                        <span className="flex items-center gap-1">
                          <Users className="h-4 w-4" />
                          {schedule.team.name}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setExpandedSchedule(expandedSchedule === schedule.id ? null : schedule.id)}
                    >
                      {expandedSchedule === schedule.id ? (
                        <ChevronUp className="h-5 w-5" />
                      ) : (
                        <ChevronDown className="h-5 w-5" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openEditModal(schedule)}
                    >
                      <Pencil className="h-5 w-5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowDeleteModal(schedule)}
                      className="text-destructive hover:text-destructive"
                    >
                      <Trash2 className="h-5 w-5" />
                    </Button>
                  </div>
                </div>
              </div>

              {/* Expanded Shifts View */}
              {expandedSchedule === schedule.id && (
                <div className="border-t border-border p-4 bg-secondary/50">
                  <h4 className="text-sm font-medium text-foreground mb-3">Shifts</h4>
                  {schedule.shifts.length === 0 ? (
                    <p className="text-muted-foreground text-sm">No shifts configured</p>
                  ) : (
                    <div className="space-y-2">
                      {schedule.shifts.map((shift) => (
                        <div
                          key={shift.id}
                          className="flex items-center justify-between p-3 bg-transparent rounded-lg border border-border"
                        >
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center">
                              <User className="h-4 w-4 text-muted-foreground" />
                            </div>
                            <div>
                              <p className="text-foreground font-medium">
                                {shift.user?.full_name || shift.user?.email || 'Unknown User'}
                              </p>
                              <p className="text-muted-foreground text-sm">
                                {shift.shift_type === 'recurring' ? (
                                  <>
                                    {DAYS_OF_WEEK.find(d => d.value === shift.day_of_week)?.label || 'Unknown'} • {shift.start_time} - {shift.end_time}
                                  </>
                                ) : (
                                  'One-time shift'
                                )}
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {shift.notify_channels.map(channel => (
                              <span key={channel} className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-secondary text-muted-foreground border-border text-xs">
                                {channel}
                              </span>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-6">
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
            <Button
              key={page}
              variant={page === currentPage ? 'default' : 'outline'}
              size="sm"
              onClick={() => setCurrentPage(page)}
            >
              {page}
            </Button>
          ))}
        </div>
      )}
      </div>

      {/* Create/Edit Modal */}
      <Dialog open={showCreateModal} onOpenChange={(open) => { if (!open) closeModal(); }}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" onClose={closeModal}>
          <DialogHeader>
            <DialogTitle>
              {editingSchedule ? 'Edit Schedule' : 'Create On-Call Schedule'}
            </DialogTitle>
            <DialogDescription>
              Configure on-call rotation with shift assignments
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6 mt-4">
            {/* Basic Info */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Schedule Name *</Label>
                <Input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g., Primary On-Call"
                />
              </div>
              <div className="space-y-2">
                <Label>Timezone</Label>
                <Select
                  value={formData.timezone}
                  onChange={(e) => setFormData({ ...formData, timezone: e.target.value })}
                >
                  {TIMEZONES.map(tz => (
                    <option key={tz} value={tz}>{tz}</option>
                  ))}
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label>Description</Label>
              <Textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Optional description for this schedule"
                rows={2}
              />
            </div>

            {/* Active Toggle */}
            <div className="flex items-center justify-between p-4 bg-accent rounded-lg">
              <div>
                <h4 className="text-foreground font-medium">Active</h4>
                <p className="text-muted-foreground text-sm">Enable this schedule for on-call rotation</p>
              </div>
              <button
                onClick={() => setFormData({ ...formData, is_active: !formData.is_active })}
                className={`relative w-12 h-6 rounded-full transition-colors ${
                  formData.is_active ? 'bg-white' : 'bg-muted'
                }`}
              >
                <span
                  className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                    formData.is_active ? 'left-7' : 'left-1'
                  }`}
                />
              </button>
            </div>

            {/* Shifts Section */}
            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-base font-medium text-foreground">Shifts</h3>
                <Button variant="outline" size="sm" onClick={addShift}>
                  <Plus className="h-4 w-4 mr-1" />
                  Add Shift
                </Button>
              </div>

              {formData.shifts.length === 0 ? (
                <div className="border border-dashed border-border rounded-lg bg-transparent">
                  <div className="p-6 text-center py-8">
                    <Clock className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                    <p className="text-muted-foreground">No shifts configured</p>
                    <button
                      onClick={addShift}
                      className="mt-2 text-foreground hover:text-foreground hover:underline"
                    >
                      Add your first shift
                    </button>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  {formData.shifts.map((shift, index) => (
                    <div key={index} className="border border-border rounded-lg bg-transparent">
                      <div className="p-4 space-y-4">
                        <div className="flex items-center justify-between">
                          <h4 className="text-sm font-medium text-foreground">Shift {index + 1}</h4>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => removeShift(index)}
                            className="text-destructive hover:text-destructive"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label>Team Member</Label>
                            <Select
                              value={shift.user_id}
                              onChange={(e) => updateShift(index, 'user_id', e.target.value)}
                            >
                              <option value="">Select member...</option>
                              {teamMembers.map(member => (
                                <option key={member.id} value={member.id}>
                                  {member.full_name || member.email}
                                </option>
                              ))}
                            </Select>
                          </div>
                          <div className="space-y-2">
                            <Label>Day</Label>
                            <Select
                              value={shift.day_of_week.toString()}
                              onChange={(e) => updateShift(index, 'day_of_week', parseInt(e.target.value))}
                            >
                              {DAYS_OF_WEEK.map(day => (
                                <option key={day.value} value={day.value}>{day.label}</option>
                              ))}
                            </Select>
                          </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label>Start Time</Label>
                            <Input
                              type="time"
                              value={shift.start_time}
                              onChange={(e) => updateShift(index, 'start_time', e.target.value)}
                            />
                          </div>
                          <div className="space-y-2">
                            <Label>End Time</Label>
                            <Input
                              type="time"
                              value={shift.end_time}
                              onChange={(e) => updateShift(index, 'end_time', e.target.value)}
                            />
                          </div>
                        </div>

                        <div className="space-y-2">
                          <Label>Notify via</Label>
                          <div className="flex flex-wrap items-center gap-2">
                            {NOTIFY_CHANNELS.map(channel => (
                              <Button
                                key={channel.value}
                                type="button"
                                variant={shift.notify_channels.includes(channel.value) ? 'default' : 'outline'}
                                size="sm"
                                onClick={() => toggleNotifyChannel(index, channel.value)}
                              >
                                {channel.label}
                              </Button>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={closeModal}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={saving || !formData.name}>
              {saving && (
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
              )}
              {editingSchedule ? 'Update Schedule' : 'Create Schedule'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Modal */}
      <Dialog open={!!showDeleteModal} onOpenChange={() => setShowDeleteModal(null)}>
        <DialogContent onClose={() => setShowDeleteModal(null)}>
          <DialogHeader>
            <DialogTitle>Delete Schedule</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete "{showDeleteModal?.name}"? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteModal(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default OnCallScheduleManager;
