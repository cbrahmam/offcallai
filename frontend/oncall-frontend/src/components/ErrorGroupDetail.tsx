// frontend/oncall-frontend/src/components/ErrorGroupDetail.tsx
import React, { useState, useEffect, useCallback } from 'react';
import {
  AlertTriangle,
  ArrowLeft,
  Bug,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Clock,
  Code,
  EyeOff,
  FileText,
  Globe,
  Link,
  Monitor,
  RefreshCw,
  Server,
  Tag,
  User
} from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { Button } from './ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from './ui/tabs';
import { useNotifications } from '../contexts/NotificationContext';

import { API_URL as API_BASE_URL } from '../config/api';

interface StackFrame {
  filename?: string;
  function?: string;
  lineno?: number;
  colno?: number;
  abs_path?: string;
  context_line?: string;
  pre_context?: string[];
  post_context?: string[];
  in_app?: boolean;
  module?: string;
  vars?: Record<string, any>;
}

interface ErrorGroupDetail {
  id: string;
  title: string;
  error_type?: string;
  message?: string;
  service_name?: string;
  filename?: string;
  function_name?: string;
  line_number?: number;
  column_number?: number;
  status: string;
  is_regression?: boolean;
  assigned_to_id?: string;
  assigned_to_name?: string;
  event_count: number;
  user_count: number;
  first_seen_at: string;
  last_seen_at: string;
  resolved_at?: string;
  first_release?: string;
  last_release?: string;
  environments?: string[];
  tags?: Record<string, any>;
  fingerprint: string;
  created_at: string;
  updated_at: string;
}

interface ErrorEvent {
  id: string;
  timestamp: string;
  error_type?: string;
  message?: string;
  stack_trace?: string;
  stack_frames?: StackFrame[];
  service_name?: string;
  environment?: string;
  release?: string;
  user_id?: string;
  user_email?: string;
  user_ip?: string;
  request_url?: string;
  request_method?: string;
  runtime?: string;
  runtime_version?: string;
  os?: string;
  os_version?: string;
  browser?: string;
  browser_version?: string;
  device?: string;
  trace_id?: string;
  tags?: Record<string, any>;
  extra_data?: Record<string, any>;
  breadcrumbs?: any[];
}

interface FrequencyBucket {
  timestamp: string;
  count: number;
}

interface FrequencyData {
  buckets: FrequencyBucket[];
  period: string;
  total_events: number;
}

type FrequencyPeriod = '24h' | '7d' | '14d' | '30d';

interface ErrorGroupDetailProps {
  groupId: string;
  onBack: () => void;
}

const FREQUENCY_PERIODS: { value: FrequencyPeriod; label: string }[] = [
  { value: '24h', label: '24h' },
  { value: '7d', label: '7d' },
  { value: '14d', label: '14d' },
  { value: '30d', label: '30d' },
];

const ErrorGroupDetailComponent: React.FC<ErrorGroupDetailProps> = ({
  groupId,
  onBack,
}) => {
  const { showToast } = useNotifications();
  const [group, setGroup] = useState<ErrorGroupDetail | null>(null);
  const [events, setEvents] = useState<ErrorEvent[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<ErrorEvent | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('stacktrace');
  const [expandedFrames, setExpandedFrames] = useState<Set<number>>(new Set());

  // Frequency chart
  const [frequencyData, setFrequencyData] = useState<FrequencyData | null>(null);
  const [frequencyPeriod, setFrequencyPeriod] = useState<FrequencyPeriod>('24h');

  const fetchGroup = useCallback(async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/errors/groups/${groupId}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        setGroup(data);
      }
    } catch (error) {
      console.error('Error fetching group:', error);
    }
  }, [groupId]);

  const fetchEvents = useCallback(async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/errors/groups/${groupId}/events?limit=50`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        setEvents(data.events);
        if (data.events.length > 0) {
          fetchEventDetail(data.events[0].id);
        }
      }
    } catch (error) {
      console.error('Error fetching events:', error);
    } finally {
      setIsLoading(false);
    }
  }, [groupId]);

  const fetchFrequency = useCallback(async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(
        `${API_BASE_URL}/errors/groups/${groupId}/frequency?period=${frequencyPeriod}`,
        { headers: { 'Authorization': `Bearer ${token}` } }
      );
      if (response.ok) {
        setFrequencyData(await response.json());
      }
    } catch {
      // ignore
    }
  }, [groupId, frequencyPeriod]);

  const fetchEventDetail = async (eventId: string) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/errors/events/${eventId}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        setSelectedEvent(data);
      }
    } catch (error) {
      console.error('Error fetching event detail:', error);
    }
  };

  useEffect(() => {
    fetchGroup();
    fetchEvents();
  }, [fetchGroup, fetchEvents]);

  useEffect(() => {
    fetchFrequency();
  }, [fetchFrequency]);

  const updateStatus = async (newStatus: string) => {
    try {
      const token = localStorage.getItem('access_token');
      const endpoint = newStatus === 'resolved' ? 'resolve' :
                       newStatus === 'ignored' ? 'ignore' : 'reopen';

      const response = await fetch(`${API_BASE_URL}/errors/groups/${groupId}/${endpoint}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        showToast({
          type: 'success',
          title: 'Status Updated',
          message: `Error ${newStatus}`,
          autoClose: true,
        });
        fetchGroup();
      }
    } catch (error) {
      console.error('Error updating status:', error);
    }
  };

  const toggleFrame = (index: number) => {
    const newExpanded = new Set(expandedFrames);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedFrames(newExpanded);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const formatRelative = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'unresolved':
        return 'bg-red-500/20 text-red-400 border-red-500/30';
      case 'resolved':
        return 'bg-green-500/20 text-green-400 border-green-500/30';
      case 'ignored':
        return 'bg-secondary text-muted-foreground border-border';
      default:
        return 'bg-secondary text-muted-foreground';
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (!group) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <Bug className="w-16 h-16 text-muted-foreground/50 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-foreground mb-2">Error Not Found</h2>
          <Button onClick={onBack}>Go Back</Button>
        </div>
      </div>
    );
  }

  // Prepare frequency chart data
  const chartData = frequencyData?.buckets.map((b) => {
    const d = new Date(b.timestamp);
    return {
      time: frequencyPeriod === '24h'
        ? d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        : d.toLocaleDateString([], { month: 'short', day: 'numeric' }),
      count: b.count,
    };
  }) || [];

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <button
            onClick={onBack}
            className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
            Back to Errors
          </button>

          <div className="flex items-center gap-2">
            {group.status === 'unresolved' && (
              <>
                <Button
                  onClick={() => updateStatus('resolved')}
                  className="bg-green-600 hover:bg-green-700"
                >
                  <CheckCircle className="w-4 h-4 mr-2" />
                  Resolve
                </Button>
                <Button
                  variant="outline"
                  onClick={() => updateStatus('ignored')}
                >
                  <EyeOff className="w-4 h-4 mr-2" />
                  Ignore
                </Button>
              </>
            )}
            {(group.status === 'resolved' || group.status === 'ignored') && (
              <Button
                onClick={() => updateStatus('unresolved')}
                className="bg-yellow-600 hover:bg-yellow-700"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Reopen
              </Button>
            )}
          </div>
        </div>

        {/* Error Title Card */}
        <div className="border border-border rounded-lg bg-transparent mb-6 border-red-500/30">
          <div className="p-6">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 bg-red-500/20 rounded-lg flex items-center justify-center flex-shrink-0">
                <Bug className="w-6 h-6 text-red-500" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-2">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${getStatusColor(group.status)}`}>
                    {group.status}
                  </span>
                  {group.is_regression && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-orange-500/20 text-orange-400 border-orange-500/30">
                      Regression
                    </span>
                  )}
                  {group.error_type && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-secondary text-muted-foreground border-border">{group.error_type}</span>
                  )}
                  {group.service_name && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-secondary text-muted-foreground border-border flex items-center gap-1">
                      <Server className="w-3 h-3" />
                      {group.service_name}
                    </span>
                  )}
                </div>
                <h1 className="text-xl font-bold text-foreground mb-2 break-words">
                  {group.title}
                </h1>
                {group.message && group.message !== group.title && (
                  <p className="text-muted-foreground text-sm font-mono break-words">
                    {group.message}
                  </p>
                )}
                {group.filename && (
                  <p className="text-sm text-muted-foreground mt-2 font-mono">
                    {group.filename}
                    {group.line_number && `:${group.line_number}`}
                    {group.column_number && `:${group.column_number}`}
                    {group.function_name && ` in ${group.function_name}()`}
                  </p>
                )}
              </div>
            </div>

            {/* Frequency Chart */}
            <div className="mt-4 pt-4 border-t border-border">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-muted-foreground font-medium">Event Frequency</span>
                <div className="flex items-center border border-border rounded-md overflow-hidden">
                  {FREQUENCY_PERIODS.map((p) => (
                    <button
                      key={p.value}
                      onClick={() => setFrequencyPeriod(p.value)}
                      className={`px-2 py-1 text-[10px] font-medium transition-colors ${
                        frequencyPeriod === p.value
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted hover:bg-muted/80 text-muted-foreground'
                      }`}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="h-[120px]">
                {chartData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                      <defs>
                        <linearGradient id="freqFill" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#ef4444" stopOpacity={0.3} />
                          <stop offset="100%" stopColor="#ef4444" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <XAxis dataKey="time" tick={{ fontSize: 10 }} stroke="#888" interval="preserveStartEnd" />
                      <YAxis tick={{ fontSize: 10 }} stroke="#888" width={30} allowDecimals={false} />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #333', borderRadius: 8, fontSize: 12 }}
                        labelStyle={{ color: '#aaa' }}
                      />
                      <Area
                        type="monotone"
                        dataKey="count"
                        stroke="#ef4444"
                        strokeWidth={2}
                        fill="url(#freqFill)"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-xs text-muted-foreground">
                    No events in this period
                  </div>
                )}
              </div>
            </div>

            {/* Stats Row */}
            <div className="flex flex-wrap items-center gap-6 mt-4 pt-4 border-t border-border">
              <div className="flex items-center gap-2">
                <span className="text-2xl font-bold text-foreground">{group.event_count.toLocaleString()}</span>
                <span className="text-sm text-muted-foreground">events</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-2xl font-bold text-foreground">{group.user_count.toLocaleString()}</span>
                <span className="text-sm text-muted-foreground">users affected</span>
              </div>
              <div
                className="flex items-center gap-2 text-sm text-muted-foreground"
                title={formatDate(group.first_seen_at)}
              >
                <Clock className="w-4 h-4" />
                First seen: {formatRelative(group.first_seen_at)}
              </div>
              <div
                className="flex items-center gap-2 text-sm text-muted-foreground"
                title={formatDate(group.last_seen_at)}
              >
                <Clock className="w-4 h-4" />
                Last seen: {formatRelative(group.last_seen_at)}
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-3">
            {selectedEvent && (
              <div className="border border-border rounded-lg bg-transparent">
                <Tabs value={activeTab} onValueChange={setActiveTab}>
                  <div className="p-6 pb-0">
                    <TabsList className="w-full justify-start bg-muted/50">
                      <TabsTrigger value="stacktrace" className="flex items-center gap-2">
                        <Code className="w-4 h-4" />
                        Stack Trace
                      </TabsTrigger>
                      <TabsTrigger value="context" className="flex items-center gap-2">
                        <FileText className="w-4 h-4" />
                        Context
                      </TabsTrigger>
                      <TabsTrigger value="breadcrumbs" className="flex items-center gap-2">
                        <Tag className="w-4 h-4" />
                        Breadcrumbs
                      </TabsTrigger>
                      <TabsTrigger value="events" className="flex items-center gap-2">
                        <Clock className="w-4 h-4" />
                        Events ({events.length})
                      </TabsTrigger>
                    </TabsList>
                  </div>

                  <div className="p-6">
                    {/* Stack Trace Tab */}
                    <TabsContent value="stacktrace">
                      {selectedEvent.stack_frames && selectedEvent.stack_frames.length > 0 ? (
                        <div className="space-y-2">
                          {selectedEvent.stack_frames.map((frame, index) => (
                            <div
                              key={index}
                              className={`border rounded-lg overflow-hidden ${
                                frame.in_app !== false ? 'border-red-500/30 bg-red-500/5' : 'border-border'
                              }`}
                            >
                              <button
                                onClick={() => toggleFrame(index)}
                                className="w-full p-3 flex items-center justify-between hover:bg-muted/30 transition-colors"
                              >
                                <div className="flex items-center gap-3 font-mono text-sm">
                                  <span className="text-muted-foreground">{index + 1}</span>
                                  <span className={frame.in_app !== false ? 'text-red-400' : 'text-muted-foreground'}>
                                    {frame.function || '<anonymous>'}
                                  </span>
                                  <span className="text-muted-foreground">
                                    in {frame.filename || frame.abs_path || 'unknown'}
                                    {frame.lineno && `:${frame.lineno}`}
                                  </span>
                                </div>
                                {expandedFrames.has(index) ? (
                                  <ChevronUp className="w-4 h-4 text-muted-foreground" />
                                ) : (
                                  <ChevronDown className="w-4 h-4 text-muted-foreground" />
                                )}
                              </button>

                              {expandedFrames.has(index) && (
                                <div className="border-t border-border bg-muted/30 p-4">
                                  {/* Context lines */}
                                  {(frame.pre_context || frame.context_line || frame.post_context) && (
                                    <div className="font-mono text-xs mb-4 rounded overflow-hidden bg-background">
                                      {frame.pre_context?.map((line, i) => (
                                        <div key={`pre-${i}`} className="flex">
                                          <span className="w-12 text-right pr-3 text-muted-foreground bg-muted/50 select-none">
                                            {(frame.lineno || 0) - (frame.pre_context?.length || 0) + i}
                                          </span>
                                          <span className="px-3 text-muted-foreground">{line}</span>
                                        </div>
                                      ))}
                                      {frame.context_line && (
                                        <div className="flex bg-red-500/10">
                                          <span className="w-12 text-right pr-3 text-red-400 bg-red-500/20 select-none">
                                            {frame.lineno}
                                          </span>
                                          <span className="px-3 text-foreground font-medium">{frame.context_line}</span>
                                        </div>
                                      )}
                                      {frame.post_context?.map((line, i) => (
                                        <div key={`post-${i}`} className="flex">
                                          <span className="w-12 text-right pr-3 text-muted-foreground bg-muted/50 select-none">
                                            {(frame.lineno || 0) + i + 1}
                                          </span>
                                          <span className="px-3 text-muted-foreground">{line}</span>
                                        </div>
                                      ))}
                                    </div>
                                  )}

                                  {/* Local variables */}
                                  {frame.vars && Object.keys(frame.vars).length > 0 && (
                                    <div>
                                      <p className="text-xs font-medium text-muted-foreground mb-2">Local Variables</p>
                                      <div className="font-mono text-xs space-y-1">
                                        {Object.entries(frame.vars).map(([key, value]) => (
                                          <div key={key} className="flex">
                                            <span className="text-blue-400 mr-2">{key}:</span>
                                            <span className="text-foreground break-all">
                                              {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                                            </span>
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      ) : selectedEvent.stack_trace ? (
                        <pre className="font-mono text-sm bg-muted/30 p-4 rounded-lg overflow-x-auto whitespace-pre-wrap">
                          {selectedEvent.stack_trace}
                        </pre>
                      ) : (
                        <p className="text-muted-foreground text-center py-8">
                          No stack trace available
                        </p>
                      )}
                    </TabsContent>

                    {/* Context Tab */}
                    <TabsContent value="context">
                      <div className="space-y-6">
                        {/* Request Info */}
                        {(selectedEvent.request_url || selectedEvent.request_method) && (
                          <div>
                            <h4 className="text-sm font-medium text-muted-foreground mb-2 flex items-center gap-2">
                              <Globe className="w-4 h-4" />
                              Request
                            </h4>
                            <div className="bg-muted/30 rounded-lg p-4 font-mono text-sm">
                              {selectedEvent.request_method && selectedEvent.request_url && (
                                <p>
                                  <span className="text-blue-400">{selectedEvent.request_method}</span>{' '}
                                  {selectedEvent.request_url}
                                </p>
                              )}
                            </div>
                          </div>
                        )}

                        {/* User Info */}
                        {(selectedEvent.user_id || selectedEvent.user_email) && (
                          <div>
                            <h4 className="text-sm font-medium text-muted-foreground mb-2 flex items-center gap-2">
                              <User className="w-4 h-4" />
                              User
                            </h4>
                            <div className="bg-muted/30 rounded-lg p-4 space-y-1 text-sm">
                              {selectedEvent.user_id && (
                                <p><span className="text-muted-foreground">ID:</span> {selectedEvent.user_id}</p>
                              )}
                              {selectedEvent.user_email && (
                                <p><span className="text-muted-foreground">Email:</span> {selectedEvent.user_email}</p>
                              )}
                              {selectedEvent.user_ip && (
                                <p><span className="text-muted-foreground">IP:</span> {selectedEvent.user_ip}</p>
                              )}
                            </div>
                          </div>
                        )}

                        {/* Device Info */}
                        {(selectedEvent.browser || selectedEvent.os || selectedEvent.device) && (
                          <div>
                            <h4 className="text-sm font-medium text-muted-foreground mb-2 flex items-center gap-2">
                              <Monitor className="w-4 h-4" />
                              Device
                            </h4>
                            <div className="bg-muted/30 rounded-lg p-4 space-y-1 text-sm">
                              {selectedEvent.browser && (
                                <p>
                                  <span className="text-muted-foreground">Browser:</span>{' '}
                                  {selectedEvent.browser} {selectedEvent.browser_version}
                                </p>
                              )}
                              {selectedEvent.os && (
                                <p>
                                  <span className="text-muted-foreground">OS:</span>{' '}
                                  {selectedEvent.os} {selectedEvent.os_version}
                                </p>
                              )}
                              {selectedEvent.device && (
                                <p><span className="text-muted-foreground">Device:</span> {selectedEvent.device}</p>
                              )}
                            </div>
                          </div>
                        )}

                        {/* Runtime Info */}
                        {selectedEvent.runtime && (
                          <div>
                            <h4 className="text-sm font-medium text-muted-foreground mb-2 flex items-center gap-2">
                              <Server className="w-4 h-4" />
                              Runtime
                            </h4>
                            <div className="bg-muted/30 rounded-lg p-4 text-sm">
                              <p>{selectedEvent.runtime} {selectedEvent.runtime_version}</p>
                            </div>
                          </div>
                        )}

                        {/* Tags */}
                        {selectedEvent.tags && Object.keys(selectedEvent.tags).length > 0 && (
                          <div>
                            <h4 className="text-sm font-medium text-muted-foreground mb-2 flex items-center gap-2">
                              <Tag className="w-4 h-4" />
                              Tags
                            </h4>
                            <div className="flex flex-wrap gap-2">
                              {Object.entries(selectedEvent.tags).map(([key, value]) => (
                                <span key={key} className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-secondary text-muted-foreground border-border">
                                  {key}: {String(value)}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Extra Data */}
                        {selectedEvent.extra_data && Object.keys(selectedEvent.extra_data).length > 0 && (
                          <div>
                            <h4 className="text-sm font-medium text-muted-foreground mb-2">Extra Data</h4>
                            <pre className="bg-muted/30 rounded-lg p-4 font-mono text-xs overflow-x-auto">
                              {JSON.stringify(selectedEvent.extra_data, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    </TabsContent>

                    {/* Breadcrumbs Tab */}
                    <TabsContent value="breadcrumbs">
                      {selectedEvent.breadcrumbs && selectedEvent.breadcrumbs.length > 0 ? (
                        <div className="space-y-2">
                          {selectedEvent.breadcrumbs.map((crumb, index) => (
                            <div
                              key={index}
                              className="flex items-start gap-3 p-3 bg-muted/30 rounded-lg"
                            >
                              <div className="w-2 h-2 rounded-full bg-blue-500 mt-2 flex-shrink-0" />
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-1">
                                  {crumb.category && (
                                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-secondary text-muted-foreground border-border">
                                      {crumb.category}
                                    </span>
                                  )}
                                  <span className="text-xs text-muted-foreground">
                                    {crumb.timestamp && formatDate(crumb.timestamp)}
                                  </span>
                                </div>
                                <p className="text-sm text-foreground">{crumb.message}</p>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-muted-foreground text-center py-8">
                          No breadcrumbs recorded
                        </p>
                      )}
                    </TabsContent>

                    {/* Events Tab */}
                    <TabsContent value="events">
                      <div className="space-y-2">
                        {events.map((event) => (
                          <button
                            key={event.id}
                            onClick={() => fetchEventDetail(event.id)}
                            className={`w-full text-left p-3 rounded-lg transition-colors ${
                              selectedEvent?.id === event.id
                                ? 'bg-primary/10 border border-primary'
                                : 'bg-muted/30 hover:bg-muted/50 border border-transparent'
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-3">
                                <Clock className="w-4 h-4 text-muted-foreground" />
                                <span className="text-sm">{formatDate(event.timestamp)}</span>
                                {event.environment && (
                                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-secondary text-muted-foreground border-border">
                                    {event.environment}
                                  </span>
                                )}
                                {event.release && (
                                  <span className="text-xs text-muted-foreground">
                                    v{event.release}
                                  </span>
                                )}
                              </div>
                              {event.user_id && (
                                <span className="text-xs text-muted-foreground flex items-center gap-1">
                                  <User className="w-3 h-3" />
                                  {event.user_id}
                                </span>
                              )}
                            </div>
                          </button>
                        ))}
                      </div>
                    </TabsContent>
                  </div>
                </Tabs>
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Releases */}
            <div className="border border-border rounded-lg bg-transparent">
              <div className="p-6 pb-3">
                <h3 className="font-semibold text-sm">Releases</h3>
              </div>
              <div className="p-6 pt-0 space-y-2 text-sm">
                {group.first_release && (
                  <div>
                    <p className="text-muted-foreground">First seen in</p>
                    <p className="font-mono">{group.first_release}</p>
                  </div>
                )}
                {group.last_release && (
                  <div>
                    <p className="text-muted-foreground">Last seen in</p>
                    <p className="font-mono">{group.last_release}</p>
                  </div>
                )}
                {group.environments && group.environments.length > 0 && (
                  <div>
                    <p className="text-muted-foreground">Environments</p>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {group.environments.map((env) => (
                        <span key={env} className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-secondary text-muted-foreground border-border">
                          {env}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Trace Correlation */}
            {selectedEvent?.trace_id && (
              <div className="border border-border rounded-lg bg-transparent">
                <div className="p-6 pb-3">
                  <h3 className="font-semibold text-sm flex items-center gap-2">
                    <Link className="w-4 h-4" />
                    Trace
                  </h3>
                </div>
                <div className="p-6 pt-0">
                  <p className="font-mono text-xs break-all text-muted-foreground">
                    {selectedEvent.trace_id}
                  </p>
                </div>
              </div>
            )}

            {/* Fingerprint */}
            <div className="border border-border rounded-lg bg-transparent">
              <div className="p-6 pb-3">
                <h3 className="font-semibold text-sm">Fingerprint</h3>
              </div>
              <div className="p-6 pt-0">
                <p className="font-mono text-xs break-all text-muted-foreground">
                  {group.fingerprint}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ErrorGroupDetailComponent;
