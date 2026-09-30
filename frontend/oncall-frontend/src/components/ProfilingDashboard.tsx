// frontend/oncall-frontend/src/components/ProfilingDashboard.tsx
import React, { useState, useEffect, useCallback } from 'react';
import {
  Clock,
  Cpu,
  Database,
  Filter,
  Flame,
  GitCompare,
  HardDrive,
  Layers,
  RefreshCw
} from 'lucide-react';
import { API_URL } from '../config/api';
import { useNotifications } from '../contexts/NotificationContext';
import { Button } from './ui/button';
import { Select } from './ui/select';

interface Profile {
  id: string;
  service_name: string;
  profile_type: string;
  format: string;
  start_time: string;
  end_time?: string;
  duration_seconds?: number;
  profile_size_bytes?: number;
  sample_count?: number;
  environment?: string;
  runtime?: string;
  trace_id?: string;
  top_functions?: Array<{ name: string; samples: number; percent: number }>;
  created_at: string;
}

interface ServiceInfo {
  service_name: string;
  profile_count: number;
  last_profile_at?: string;
}

interface FlamegraphNode {
  name: string;
  value: number;
  children: FlamegraphNode[];
  file?: string;
  line?: number;
  self_value?: number;
}

interface FlamegraphData {
  profile_id: string;
  profile_type: string;
  service_name: string;
  start_time: string;
  duration_seconds?: number;
  root: FlamegraphNode;
  total_samples: number;
  unit: string;
}

interface ProfilingDashboardProps {
  onNavigateToProfile?: (profileId: string) => void;
}

const ProfilingDashboard: React.FC<ProfilingDashboardProps> = ({ onNavigateToProfile }) => {
  const { showToast } = useNotifications();
  const [services, setServices] = useState<ServiceInfo[]>([]);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [selectedService, setSelectedService] = useState<string>('');
  const [selectedType, setSelectedType] = useState<string>('');
  const [selectedProfile, setSelectedProfile] = useState<Profile | null>(null);
  const [flamegraphData, setFlamegraphData] = useState<FlamegraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingFlamegraph, setLoadingFlamegraph] = useState(false);
  const [compareMode, setCompareMode] = useState(false);
  const [baseProfileId, setBaseProfileId] = useState<string | null>(null);

  // Profile type icons
  const profileTypeIcons: Record<string, React.ReactNode> = {
    cpu: <Cpu className="w-4 h-4" />,
    heap: <HardDrive className="w-4 h-4" />,
    goroutine: <Layers className="w-4 h-4" />,
    block: <Clock className="w-4 h-4" />,
    mutex: <Database className="w-4 h-4" />,
  };

  // Fetch services
  const fetchServices = useCallback(async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_URL}/profiles/services`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (response.ok) {
        const data = await response.json();
        const fetchedServices = data.services || [];
        setServices(fetchedServices);
        if (fetchedServices.length > 0 && !selectedService) {
          setSelectedService(fetchedServices[0].service_name);
        }
      } else {
        setServices([]);
      }
    } catch (error) {
      console.error('Failed to fetch services:', error);
      setServices([]);
    }
  }, [selectedService]);

  // Fetch profiles
  const fetchProfiles = useCallback(async () => {
    if (!selectedService) return;

    setLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      const params = new URLSearchParams({
        service_name: selectedService,
        limit: '50',
      });
      if (selectedType) {
        params.append('profile_type', selectedType);
      }

      const response = await fetch(`${API_URL}/profiles?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (response.ok) {
        const data = await response.json();
        const fetchedProfiles = data.profiles || [];
        setProfiles(fetchedProfiles);
      } else {
        setProfiles([]);
      }
    } catch (error) {
      console.error('Failed to fetch profiles:', error);
      setProfiles([]);
    } finally {
      setLoading(false);
    }
  }, [selectedService, selectedType]);

  // Fetch flamegraph data
  const fetchFlamegraph = useCallback(async (profileId: string) => {
    setLoadingFlamegraph(true);
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_URL}/profiles/${profileId}/flamegraph`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (response.ok) {
        const data = await response.json();
        if (data && data.root) {
          setFlamegraphData(data);
        } else {
          setFlamegraphData(null);
        }
      } else {
        setFlamegraphData(null);
      }
    } catch (error) {
      console.error('Failed to fetch flamegraph:', error);
      setFlamegraphData(null);
    } finally {
      setLoadingFlamegraph(false);
    }
  }, []);

  useEffect(() => {
    fetchServices();
  }, [fetchServices]);

  useEffect(() => {
    if (selectedService) {
      fetchProfiles();
    }
  }, [selectedService, selectedType, fetchProfiles]);

  // Handle profile selection
  const handleProfileSelect = (profile: Profile) => {
    if (compareMode && baseProfileId) {
      // Compare two profiles
      handleCompareProfiles(baseProfileId, profile.id);
    } else if (compareMode) {
      setBaseProfileId(profile.id);
      showToast({ message: 'Base profile selected. Now select a profile to compare.', type: 'info' });
    } else {
      setSelectedProfile(profile);
      fetchFlamegraph(profile.id);
    }
  };

  // Compare profiles
  const handleCompareProfiles = async (baseId: string, compareId: string) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_URL}/profiles/compare`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          base_profile_id: baseId,
          compare_profile_id: compareId,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        showToast({ message: `Comparison complete. Total diff: ${data.total_diff_percent.toFixed(1)}%`, type: 'success' });
      }
    } catch (error) {
      showToast({ message: 'Failed to compare profiles', type: 'error' });
    } finally {
      setCompareMode(false);
      setBaseProfileId(null);
    }
  };

  // Format bytes
  const formatBytes = (bytes?: number) => {
    if (!bytes) return '-';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // Format time ago
  const formatTimeAgo = (dateStr?: string) => {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
    return `${Math.floor(diffMins / 1440)}d ago`;
  };

  // Flamegraph component (simplified visualization)
  const FlamegraphViewer: React.FC<{ data: FlamegraphData }> = ({ data }) => {
    const [hoveredNode, setHoveredNode] = useState<FlamegraphNode | null>(null);

    const renderNode = (node: FlamegraphNode, depth: number, startPercent: number, widthPercent: number): React.ReactNode => {
      if (widthPercent < 0.1 || depth > 20) return null;

      const hue = (depth * 30) % 360;
      const bgColor = `hsl(${hue}, 70%, ${60 - depth * 2}%)`;

      return (
        <div key={`${node.name}-${depth}-${startPercent}`} className="relative">
          <div
            className="h-6 border border-border cursor-pointer transition-opacity hover:opacity-80 overflow-hidden whitespace-nowrap text-ellipsis"
            style={{
              width: `${widthPercent}%`,
              marginLeft: `${startPercent}%`,
              backgroundColor: bgColor,
            }}
            onMouseEnter={() => setHoveredNode(node)}
            onMouseLeave={() => setHoveredNode(null)}
          >
            <span className="text-xs text-foreground px-1 truncate">
              {node.name.split('.').pop() || node.name}
            </span>
          </div>
          {node.children.length > 0 && (
            <div className="relative">
              {(() => {
                let childStart = startPercent;
                return node.children.map((child, i) => {
                  const childWidth = (child.value / data.total_samples) * 100;
                  const rendered = renderNode(child, depth + 1, childStart, childWidth);
                  childStart += childWidth;
                  return rendered;
                });
              })()}
            </div>
          )}
        </div>
      );
    };

    return (
      <div className="bg-muted rounded-lg p-4">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h3 className="text-lg font-semibold text-foreground">Flamegraph</h3>
            <p className="text-sm text-muted-foreground">
              {data.service_name} - {data.profile_type} - {data.total_samples.toLocaleString()} {data.unit}
            </p>
          </div>
          {hoveredNode && (
            <div className="text-right">
              <p className="text-sm text-foreground font-mono">{hoveredNode.name}</p>
              <p className="text-xs text-muted-foreground">
                {hoveredNode.value.toLocaleString()} {data.unit} ({((hoveredNode.value / data.total_samples) * 100).toFixed(1)}%)
              </p>
            </div>
          )}
        </div>
        <div className="overflow-x-auto">
          <div className="min-w-[800px]">
            {renderNode(data.root, 0, 0, 100)}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="relative overflow-hidden border-b border-border">
        <div className="relative max-w-7xl mx-auto px-6 py-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-orange-500/10">
                <Flame className="w-6 h-6 text-orange-400" />
              </div>
              <div>
                <h1 className="text-base font-medium text-foreground">Continuous Profiling</h1>
                <p className="text-muted-foreground text-sm">Analyze CPU and memory profiles to identify performance bottlenecks</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant={compareMode ? 'default' : 'outline'}
                onClick={() => {
                  setCompareMode(!compareMode);
                  setBaseProfileId(null);
                }}
              >
                <GitCompare className="w-4 h-4 mr-2" />
                {compareMode ? 'Cancel Compare' : 'Compare'}
              </Button>
              <Button variant="outline" onClick={() => fetchProfiles()}>
                <RefreshCw className="w-4 h-4 mr-2" />
                Refresh
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
      {/* Filters */}
      <div className="border border-border rounded-lg bg-transparent bg-muted/50 border-border">
        <div className="p-4 pb-4">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Filters:</span>
            </div>
            <Select
              value={selectedService}
              onChange={(e) => setSelectedService(e.target.value)}
              className="w-48 bg-muted border-border"
            >
              <option value="">Select service</option>
              {services.map((svc) => (
                <option key={svc.service_name} value={svc.service_name}>
                  {svc.service_name}
                </option>
              ))}
            </Select>
            <Select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="w-40 bg-muted border-border"
            >
              <option value="">All types</option>
              <option value="cpu">CPU</option>
              <option value="heap">Heap</option>
              <option value="goroutine">Goroutine</option>
              <option value="block">Block</option>
              <option value="mutex">Mutex</option>
            </Select>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Profile list */}
        <div className="lg:col-span-1">
          <div className="border border-border rounded-lg bg-transparent bg-muted/50 border-border">
            <div className="p-6">
              <h3 className="font-semibold text-lg">Recent Profiles</h3>
              <p className="text-sm text-muted-foreground">
                {profiles.length} profile{profiles.length !== 1 ? 's' : ''} found
              </p>
            </div>
            <div className="p-0">
              <div className="max-h-[600px] overflow-y-auto">
                {loading ? (
                  <div className="p-4 text-center text-muted-foreground">Loading...</div>
                ) : profiles.length === 0 ? (
                  <div className="p-4 text-center text-muted-foreground">
                    No profiles found. Configure your agent to collect profiles.
                  </div>
                ) : (
                  profiles.map((profile) => (
                    <div
                      key={profile.id}
                      className={`p-4 border-b border-border cursor-pointer hover:bg-muted/50 transition-colors ${
                        selectedProfile?.id === profile.id ? 'bg-muted/70' : ''
                      } ${baseProfileId === profile.id ? 'ring-2 ring-blue-500' : ''}`}
                      onClick={() => handleProfileSelect(profile)}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          {profileTypeIcons[profile.profile_type] || <Flame className="w-4 h-4" />}
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-secondary text-muted-foreground border-border text-xs">
                            {profile.profile_type}
                          </span>
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {formatTimeAgo(profile.start_time)}
                        </span>
                      </div>
                      <div className="text-sm text-foreground">{profile.service_name}</div>
                      <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                        <span>{formatBytes(profile.profile_size_bytes)}</span>
                        {profile.sample_count && (
                          <span>{profile.sample_count.toLocaleString()} samples</span>
                        )}
                        {profile.duration_seconds && (
                          <span>{profile.duration_seconds}s</span>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Flamegraph viewer */}
        <div className="lg:col-span-2">
          {loadingFlamegraph ? (
            <div className="border border-border rounded-lg bg-transparent bg-muted/50 border-border h-[600px] flex items-center justify-center">
              <div className="text-center">
                <RefreshCw className="w-8 h-8 text-muted-foreground animate-spin mx-auto mb-2" />
                <p className="text-muted-foreground">Loading flamegraph...</p>
              </div>
            </div>
          ) : flamegraphData ? (
            <FlamegraphViewer data={flamegraphData} />
          ) : (
            <div className="border border-border rounded-lg bg-transparent bg-muted/50 border-border h-[600px] flex items-center justify-center">
              <div className="text-center">
                <Flame className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
                <h3 className="text-lg font-medium text-muted-foreground mb-2">
                  Select a profile to view
                </h3>
                <p className="text-sm text-muted-foreground max-w-md">
                  Click on a profile from the list to visualize its flamegraph.
                  Flamegraphs help identify hot code paths and memory allocation patterns.
                </p>
              </div>
            </div>
          )}

          {/* Profile details */}
          {selectedProfile && (
            <div className="border border-border rounded-lg bg-transparent bg-muted/50 border-border mt-4">
              <div className="p-6">
                <h3 className="font-semibold text-lg">Profile Details</h3>
              </div>
              <div className="p-6 pt-0">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <p className="text-xs text-muted-foreground">Service</p>
                    <p className="text-sm text-foreground">{selectedProfile.service_name}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Type</p>
                    <p className="text-sm text-foreground">{selectedProfile.profile_type}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Runtime</p>
                    <p className="text-sm text-foreground">{selectedProfile.runtime || '-'}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Environment</p>
                    <p className="text-sm text-foreground">{selectedProfile.environment || '-'}</p>
                  </div>
                </div>

                {selectedProfile.top_functions && selectedProfile.top_functions.length > 0 && (
                  <div className="mt-4">
                    <p className="text-xs text-muted-foreground mb-2">Top Functions</p>
                    <div className="space-y-2">
                      {selectedProfile.top_functions.slice(0, 5).map((func, idx) => (
                        <div key={idx} className="flex items-center justify-between">
                          <span className="text-sm text-foreground font-mono truncate max-w-[300px]">
                            {func.name}
                          </span>
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-muted-foreground">
                              {func.samples.toLocaleString()} samples
                            </span>
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-secondary text-muted-foreground border-border text-xs">
                              {func.percent.toFixed(1)}%
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
      </div>
    </div>
  );
};

export default ProfilingDashboard;
