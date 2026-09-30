// Service Dependency Map - Interactive visualization of service relationships
import React, { useCallback, useEffect, useState, useMemo } from 'react';
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  Position,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { useAuth } from '../contexts/AuthContext';
import { API_URL } from '../config/api';

// Types from backend
interface ServiceNode {
  service_name: string;
  request_count: number;
  error_rate: number;
  latency_avg: number;
  latency_p95: number | null;
  health_status: 'healthy' | 'degraded' | 'critical' | null;
}

interface ServiceEdge {
  source: string;
  target: string;
  request_count: number;
  error_rate: number;
  latency_avg: number;
}

interface ServiceMapData {
  nodes: ServiceNode[];
  edges: ServiceEdge[];
  time_range_hours: number;
}

// Health status colors
const healthColors = {
  healthy: { bg: '#10B981', border: '#059669', text: '#ECFDF5' },   // Green
  degraded: { bg: '#F59E0B', border: '#D97706', text: '#FFFBEB' },  // Yellow
  critical: { bg: '#EF4444', border: '#DC2626', text: '#FEF2F2' },  // Red
  unknown: { bg: '#6B7280', border: '#4B5563', text: '#F3F4F6' },   // Gray
};

// Custom node component for services
const ServiceNodeComponent = ({ data }: { data: ServiceNode & { selected?: boolean } }) => {
  const health = data.health_status || 'unknown';
  const colors = healthColors[health] || healthColors.unknown;

  return (
    <div
      className={`px-4 py-3 rounded-lg border-2 min-w-[180px] transition-transform ${
        data.selected ? 'ring-2 ring-blue-500 ring-offset-2' : ''
      }`}
      style={{
        backgroundColor: colors.bg,
        borderColor: colors.border,
      }}
    >
      <div className="text-center">
        <div className="font-bold text-foreground text-sm truncate max-w-[160px]">
          {data.service_name}
        </div>
        <div className="text-xs text-foreground/80 mt-1">
          {data.request_count.toLocaleString()} requests
        </div>
        <div className="flex justify-center gap-3 mt-2 text-xs">
          <div className="text-foreground/90">
            <span className="font-medium">{data.error_rate.toFixed(1)}%</span>
            <span className="text-foreground/60 ml-1">err</span>
          </div>
          <div className="text-foreground/90">
            <span className="font-medium">{data.latency_avg.toFixed(0)}</span>
            <span className="text-foreground/60 ml-1">ms</span>
          </div>
        </div>
        {data.latency_p95 && (
          <div className="text-xs text-foreground/70 mt-1">
            p95: {data.latency_p95.toFixed(0)}ms
          </div>
        )}
      </div>
    </div>
  );
};

// Node types for React Flow
const nodeTypes = {
  serviceNode: ServiceNodeComponent,
};

interface ServiceDependencyMapProps {
  onServiceClick?: (serviceName: string) => void;
}

const ServiceDependencyMap: React.FC<ServiceDependencyMapProps> = ({ onServiceClick }) => {
  const { token } = useAuth();
  const [serviceMapData, setServiceMapData] = useState<ServiceMapData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState(24);
  const [selectedService, setSelectedService] = useState<string | null>(null);

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  // Fetch service map data
  const fetchServiceMap = useCallback(async () => {
    if (!token) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${API_URL}/traces/services/map?hours=${timeRange}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch service map: ${response.status}`);
      }

      const data: ServiceMapData = await response.json();
      setServiceMapData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load service map');
    } finally {
      setLoading(false);
    }
  }, [token, timeRange]);

  useEffect(() => {
    fetchServiceMap();
  }, [fetchServiceMap]);

  // Convert service map data to React Flow nodes and edges
  useEffect(() => {
    if (!serviceMapData) return;

    // Calculate node positions using a simple grid layout
    // In production, you might want to use a proper graph layout algorithm
    const nodeCount = serviceMapData.nodes.length;
    const cols = Math.ceil(Math.sqrt(nodeCount));
    const spacing = 250;

    const flowNodes: Node[] = serviceMapData.nodes.map((node, index) => {
      const row = Math.floor(index / cols);
      const col = index % cols;

      return {
        id: node.service_name,
        type: 'serviceNode',
        position: { x: col * spacing + 100, y: row * spacing + 100 },
        data: {
          ...node,
          selected: node.service_name === selectedService,
        },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      };
    });

    const flowEdges: Edge[] = serviceMapData.edges.map((edge, index) => ({
      id: `${edge.source}-${edge.target}-${index}`,
      source: edge.source,
      target: edge.target,
      type: 'smoothstep',
      animated: edge.error_rate > 1,  // Animate edges with errors
      style: {
        stroke: edge.error_rate > 5 ? '#EF4444' : edge.error_rate > 1 ? '#F59E0B' : '#71717A',
        strokeWidth: Math.min(Math.max(edge.request_count / 1000, 1), 4),
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: edge.error_rate > 5 ? '#EF4444' : edge.error_rate > 1 ? '#F59E0B' : '#71717A',
      },
      label: `${edge.request_count.toLocaleString()} req`,
      labelStyle: { fill: '#A1A1AA', fontSize: 10 },
      labelBgStyle: { fill: '#18181B', fillOpacity: 0.8 },
      labelBgPadding: [4, 2] as [number, number],
      labelBgBorderRadius: 4,
    }));

    setNodes(flowNodes);
    setEdges(flowEdges);
  }, [serviceMapData, selectedService, setNodes, setEdges]);

  // Handle node click
  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      setSelectedService(node.id);
      if (onServiceClick) {
        onServiceClick(node.id);
      }
    },
    [onServiceClick]
  );

  // Stats summary
  const stats = useMemo(() => {
    if (!serviceMapData) return null;

    const totalRequests = serviceMapData.nodes.reduce((sum, n) => sum + n.request_count, 0);
    const healthyCount = serviceMapData.nodes.filter((n) => n.health_status === 'healthy').length;
    const degradedCount = serviceMapData.nodes.filter((n) => n.health_status === 'degraded').length;
    const criticalCount = serviceMapData.nodes.filter((n) => n.health_status === 'critical').length;

    return { totalRequests, healthyCount, degradedCount, criticalCount };
  }, [serviceMapData]);

  // Page header component for consistent layout
  const PageHeader = () => (
    <div className="relative overflow-hidden border-b border-border">
      <div className="relative max-w-7xl mx-auto px-6 py-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl bg-rose-500/10">
              <svg className="w-6 h-6 text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
              </svg>
            </div>
            <div>
              <h1 className="text-base font-medium text-foreground">Service Map</h1>
              <p className="text-muted-foreground text-sm">Visualize service dependencies and health status</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(Number(e.target.value))}
              className="bg-muted text-foreground px-3 py-2 rounded-lg border border-border text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value={1}>Last 1 hour</option>
              <option value={6}>Last 6 hours</option>
              <option value={24}>Last 24 hours</option>
              <option value={72}>Last 3 days</option>
              <option value={168}>Last 7 days</option>
            </select>
            <button
              onClick={fetchServiceMap}
              className="p-2 text-muted-foreground hover:text-foreground transition-colors bg-muted rounded-lg border border-border"
              title="Refresh"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  if (loading) {
    return (
      <div className="min-h-screen bg-background">
        <PageHeader />
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="bg-muted rounded-lg border border-border p-8 flex items-center justify-center h-[500px]">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
              <p className="text-muted-foreground mt-4">Loading service map...</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-background">
        <PageHeader />
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="bg-muted rounded-lg border border-border p-8 h-[500px]">
            <div className="text-center text-red-400">
              <svg className="h-12 w-12 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <p>{error}</p>
              <button
                onClick={fetchServiceMap}
                className="mt-4 px-4 py-2 bg-blue-600 text-foreground rounded-lg hover:bg-blue-700 transition-colors"
              >
                Retry
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!serviceMapData || serviceMapData.nodes.length === 0) {
    return (
      <div className="min-h-screen bg-background">
        <PageHeader />
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="bg-muted rounded-lg border border-border p-8 h-[500px]">
            <div className="text-center text-muted-foreground pt-20">
              <svg className="h-16 w-16 mx-auto mb-4 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
              </svg>
              <h3 className="text-lg font-medium text-foreground">No Service Data</h3>
              <p className="mt-2">
                No trace data available for the selected time range.
                <br />
                Make sure your services are instrumented with OpenTelemetry.
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <PageHeader />

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-muted rounded-lg p-4 border border-border">
            <div className="text-2xl font-bold text-foreground">{serviceMapData.nodes.length}</div>
            <div className="text-muted-foreground text-sm">Services</div>
          </div>
          <div className="bg-muted rounded-lg p-4 border border-border">
            <div className="text-2xl font-bold text-green-400">{stats.healthyCount}</div>
            <div className="text-muted-foreground text-sm">Healthy</div>
          </div>
          <div className="bg-muted rounded-lg p-4 border border-border">
            <div className="text-2xl font-bold text-yellow-400">{stats.degradedCount}</div>
            <div className="text-muted-foreground text-sm">Degraded</div>
          </div>
          <div className="bg-muted rounded-lg p-4 border border-border">
            <div className="text-2xl font-bold text-red-400">{stats.criticalCount}</div>
            <div className="text-muted-foreground text-sm">Critical</div>
          </div>
        </div>
      )}

      {/* Map Container */}
      <div className="bg-muted rounded-lg border border-border overflow-hidden">

      {/* React Flow canvas */}
      <div className="h-[600px]">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.1}
          maxZoom={2}
          defaultEdgeOptions={{
            type: 'smoothstep',
          }}
        >
          <Background color="rgba(255,255,255,0.06)" gap={20} />
          <Controls
            className="bg-muted border border-border rounded-lg"
            showInteractive={false}
          />
          <MiniMap
            className="bg-muted border border-border rounded-lg"
            nodeColor={(node) => {
              const health = node.data?.health_status || 'unknown';
              return healthColors[health as keyof typeof healthColors]?.bg || healthColors.unknown.bg;
            }}
            maskColor="rgba(0, 0, 0, 0.8)"
          />
        </ReactFlow>
      </div>

      {/* Selected service details */}
      {selectedService && serviceMapData && (
        <div className="p-4 border-t border-border bg-muted/50">
          {(() => {
            const service = serviceMapData.nodes.find((n) => n.service_name === selectedService);
            if (!service) return null;

            const incomingEdges = serviceMapData.edges.filter((e) => e.target === selectedService);
            const outgoingEdges = serviceMapData.edges.filter((e) => e.source === selectedService);

            return (
              <div className="grid grid-cols-3 gap-6">
                <div>
                  <h4 className="text-sm font-medium text-muted-foreground mb-2">Service Details</h4>
                  <div className="text-foreground font-bold">{service.service_name}</div>
                  <div className="text-sm text-muted-foreground mt-1">
                    Status:{' '}
                    <span
                      className={
                        service.health_status === 'healthy'
                          ? 'text-green-400'
                          : service.health_status === 'degraded'
                          ? 'text-yellow-400'
                          : 'text-red-400'
                      }
                    >
                      {service.health_status || 'Unknown'}
                    </span>
                  </div>
                </div>
                <div>
                  <h4 className="text-sm font-medium text-muted-foreground mb-2">Metrics</h4>
                  <div className="text-sm text-foreground">
                    <div>Requests: {service.request_count.toLocaleString()}</div>
                    <div>Error Rate: {service.error_rate.toFixed(2)}%</div>
                    <div>Avg Latency: {service.latency_avg.toFixed(0)}ms</div>
                    {service.latency_p95 && <div>p95 Latency: {service.latency_p95.toFixed(0)}ms</div>}
                  </div>
                </div>
                <div>
                  <h4 className="text-sm font-medium text-muted-foreground mb-2">Dependencies</h4>
                  <div className="text-sm text-foreground">
                    <div>
                      Upstream: {incomingEdges.map((e) => e.source).join(', ') || 'None'}
                    </div>
                    <div>
                      Downstream: {outgoingEdges.map((e) => e.target).join(', ') || 'None'}
                    </div>
                  </div>
                </div>
              </div>
            );
          })()}
        </div>
      )}
      </div>
      </div>
    </div>
  );
};

export default ServiceDependencyMap;
