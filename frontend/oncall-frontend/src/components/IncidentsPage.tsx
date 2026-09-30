// IncidentsPage.tsx - Dedicated incidents list page
import React, { useState, useEffect, useCallback } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  ChevronLeft,
  ChevronRight,
  Clock,
  Filter,
  Plus,
  RefreshCw,
  Search,
  XCircle
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { Button } from './ui/button';
import { Input } from './ui/input';

import { API_URL as API_BASE_URL } from '../config/api';

interface Incident {
  id: string;
  title: string;
  description: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  status: 'open' | 'acknowledged' | 'resolved';
  created_at: string;
  updated_at: string;
  assigned_to?: string;
  service?: string;
  alert_count?: number;
}

interface IncidentsPageProps {
  onNavigateToIncident: (incidentId: string) => void;
}

const IncidentsPage: React.FC<IncidentsPageProps> = ({ onNavigateToIncident }) => {
  const { logout } = useAuth();
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const itemsPerPage = 10;

  const hasFetchedRef = React.useRef(false);

  const authenticatedFetch = useCallback(async (url: string, options: RequestInit = {}) => {
    const token = localStorage.getItem('access_token');
    if (!token) throw new Error('No access token');

    const response = await fetch(url, {
      ...options,
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (response.status === 401) {
      logout();
      throw new Error('Session expired');
    }

    return response;
  }, [logout]);

  const loadIncidents = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        limit: itemsPerPage.toString(),
        skip: ((currentPage - 1) * itemsPerPage).toString(),
      });

      if (severityFilter !== 'all') params.append('severity', severityFilter);
      if (statusFilter !== 'all') params.append('status', statusFilter);
      if (searchQuery) params.append('search', searchQuery);

      const response = await authenticatedFetch(`${API_BASE_URL}/incidents/?${params}`);

      if (response.ok) {
        const data = await response.json();
        const incidentList = Array.isArray(data) ? data : (data.incidents || data.items || []);
        setIncidents(incidentList);
        setTotalPages(Math.ceil((data.total || incidentList.length) / itemsPerPage));
      } else {
        setIncidents([]);
        setTotalPages(1);
      }
    } catch (error) {
      console.error('Error loading incidents:', error);
      setIncidents([]);
      setTotalPages(1);
    } finally {
      setLoading(false);
    }
  }, [authenticatedFetch, currentPage, severityFilter, statusFilter, searchQuery]);

  useEffect(() => {
    if (hasFetchedRef.current) return;
    hasFetchedRef.current = true;
    loadIncidents();
  }, [loadIncidents]);

  // Reload when filters change
  useEffect(() => {
    if (hasFetchedRef.current) {
      loadIncidents();
    }
  }, [severityFilter, statusFilter, currentPage, loadIncidents]);

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'bg-red-500/10 text-red-400 border-red-500/20';
      case 'high': return 'bg-orange-500/10 text-orange-400 border-orange-500/20';
      case 'medium': return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20';
      case 'low': return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
      default: return 'bg-secondary text-muted-foreground';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'open': return 'bg-red-500/10 text-red-400 border-red-500/20';
      case 'acknowledged': return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20';
      case 'resolved': return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      default: return 'bg-secondary text-muted-foreground';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'open': return <AlertTriangle className="w-3.5 h-3.5" />;
      case 'acknowledged': return <Clock className="w-3.5 h-3.5" />;
      case 'resolved': return <CheckCircle className="w-3.5 h-3.5" />;
      default: return <XCircle className="w-3.5 h-3.5" />;
    }
  };

  const formatTimeAgo = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  // Filter incidents based on search
  const filteredIncidents = incidents.filter(incident => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      incident.title.toLowerCase().includes(query) ||
      incident.description.toLowerCase().includes(query) ||
      incident.service?.toLowerCase().includes(query)
    );
  });

  // Stats
  const stats = {
    total: incidents.length,
    open: incidents.filter(i => i.status === 'open').length,
    acknowledged: incidents.filter(i => i.status === 'acknowledged').length,
    resolved: incidents.filter(i => i.status === 'resolved').length,
    critical: incidents.filter(i => i.severity === 'critical').length,
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-orange-500/10">
                <AlertTriangle className="w-6 h-6 text-orange-400" />
              </div>
              <div>
                <h1 className="text-base font-medium text-foreground">Incidents</h1>
                <p className="text-muted-foreground text-sm">Manage and track all incidents</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <Button
                onClick={loadIncidents}
                variant="outline"
                className="border-border text-foreground hover:bg-accent"
              >
                <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
              <Button onClick={() => {}} className="bg-primary text-primary-foreground hover:bg-white/90">
                <Plus className="w-4 h-4" />
                Create Incident
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* Stats Cards */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-transparent border border-border rounded-xl cursor-pointer hover:bg-accent transition-all">
            <div className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-blue-500/10">
                  <AlertTriangle className="w-4 h-4 text-blue-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-foreground">{stats.total}</p>
                  <p className="text-xs text-muted-foreground">Total</p>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-transparent border border-border rounded-xl cursor-pointer hover:bg-accent transition-all" onClick={() => setStatusFilter('open')}>
            <div className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-red-500/10">
                  <AlertTriangle className="w-4 h-4 text-red-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-red-400">{stats.open}</p>
                  <p className="text-xs text-muted-foreground">Open</p>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-transparent border border-border rounded-xl cursor-pointer hover:bg-accent transition-all" onClick={() => setStatusFilter('acknowledged')}>
            <div className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-yellow-500/10">
                  <Clock className="w-4 h-4 text-yellow-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-yellow-400">{stats.acknowledged}</p>
                  <p className="text-xs text-muted-foreground">Acknowledged</p>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-transparent border border-border rounded-xl cursor-pointer hover:bg-accent transition-all" onClick={() => setStatusFilter('resolved')}>
            <div className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-emerald-500/10">
                  <CheckCircle className="w-4 h-4 text-emerald-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-emerald-400">{stats.resolved}</p>
                  <p className="text-xs text-muted-foreground">Resolved</p>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-transparent border border-border rounded-xl cursor-pointer hover:bg-accent transition-all" onClick={() => setSeverityFilter('critical')}>
            <div className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-red-500/10">
                  <XCircle className="w-4 h-4 text-red-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-red-400">{stats.critical}</p>
                  <p className="text-xs text-muted-foreground">Critical</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-transparent border border-border rounded-xl">
          <div className="p-4">
            <div className="flex flex-col md:flex-row md:items-center gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  placeholder="Search incidents..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 bg-accent border-border focus:border-primary/30 text-foreground"
                />
              </div>

              <div className="flex items-center gap-3">
                <select
                  value={severityFilter}
                  onChange={(e) => setSeverityFilter(e.target.value)}
                  className="bg-accent border border-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
                >
                  <option value="all">All Severities</option>
                  <option value="critical">Critical</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>

                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="bg-accent border border-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
                >
                  <option value="all">All Statuses</option>
                  <option value="open">Open</option>
                  <option value="acknowledged">Acknowledged</option>
                  <option value="resolved">Resolved</option>
                </select>

                {(severityFilter !== 'all' || statusFilter !== 'all' || searchQuery) && (
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setSeverityFilter('all');
                      setStatusFilter('all');
                      setSearchQuery('');
                    }}
                    className="text-muted-foreground hover:text-foreground hover:bg-accent"
                  >
                    Clear
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Incidents List */}
        <div className="bg-transparent border border-border rounded-xl">
          <div className="p-6 border-b border-border">
            <h3 className="font-medium flex items-center gap-2 text-foreground text-base">
              <Filter className="w-5 h-5 text-muted-foreground" />
              Incidents
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-secondary text-muted-foreground border-border">
                {filteredIncidents.length} results
              </span>
            </h3>
          </div>
          <div>
            {loading ? (
              <div className="p-12 text-center">
                <RefreshCw className="w-8 h-8 text-muted-foreground animate-spin mx-auto mb-4" />
                <p className="text-muted-foreground">Loading incidents...</p>
              </div>
            ) : filteredIncidents.length === 0 ? (
              <div className="p-12 text-center">
                <AlertTriangle className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                <h3 className="text-base font-medium text-foreground mb-2">No incidents found</h3>
                <p className="text-muted-foreground text-sm">Try adjusting your filters or search query</p>
              </div>
            ) : (
              <div className="divide-y divide-border">
                {filteredIncidents.map((incident) => (
                  <div
                    key={incident.id}
                    onClick={() => onNavigateToIncident(incident.id)}
                    className="p-4 hover:bg-accent/50 cursor-pointer transition-colors group"
                  >
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${
                            incident.severity === 'critical' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                            incident.severity === 'high' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                            incident.severity === 'medium' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                            'bg-blue-500/10 text-blue-400 border-blue-500/20'
                          }`}>
                            {incident.severity}
                          </span>
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border flex items-center gap-1 ${
                            incident.status === 'open' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                            incident.status === 'acknowledged' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                            'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                          }`}>
                            {getStatusIcon(incident.status)}
                            {incident.status}
                          </span>
                          {incident.service && (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-blue-500/10 text-blue-400 border-blue-500/20">
                              {incident.service}
                            </span>
                          )}
                        </div>
                        <h3 className="font-medium text-foreground group-hover:text-foreground transition-colors truncate text-sm">
                          {incident.title}
                        </h3>
                        <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                          {incident.description}
                        </p>
                      </div>

                      <div className="text-right text-sm shrink-0">
                        <p className="text-muted-foreground">{formatTimeAgo(incident.created_at)}</p>
                        {incident.assigned_to && (
                          <p className="text-muted-foreground mt-1">{incident.assigned_to}</p>
                        )}
                        {incident.alert_count && (
                          <p className="text-muted-foreground mt-1">{incident.alert_count} alerts</p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-border">
                <p className="text-sm text-muted-foreground">
                  Page {currentPage} of {totalPages}
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                    disabled={currentPage === 1}
                    className="border-border text-foreground hover:bg-accent"
                  >
                    <ChevronLeft className="w-4 h-4" />
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                    disabled={currentPage === totalPages}
                    className="border-border text-foreground hover:bg-accent"
                  >
                    Next
                    <ChevronRight className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default IncidentsPage;
