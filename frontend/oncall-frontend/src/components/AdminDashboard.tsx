// frontend/oncall-frontend/src/components/AdminDashboard.tsx
import React, { useState, useEffect } from 'react';
import {
  BarChart3,
  Building2,
  Server,
  TrendingDown,
  TrendingUp,
  Users
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';


import { API_URL as API_BASE_URL } from '../config/api';

interface UserMetrics {
  total_users: number;
  new_users_today: number;
  new_users_this_week: number;
  new_users_this_month: number;
  active_users_today: number;
  active_users_this_week: number;
  active_users_this_month: number;
}

interface UsageMetrics {
  total_incidents: number;
  incidents_today: number;
  incidents_this_week: number;
  incidents_this_month: number;
  total_integrations: number;
  active_integrations: number;
  total_organizations: number;
  active_organizations: number;
}

interface Organization {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  user_count: number;
  incident_count: number;
  created_at: string;
}

const AdminDashboard: React.FC = () => {
  const { user } = useAuth();
  const navigate = (path: string) => { window.location.href = path; };

  const [userMetrics, setUserMetrics] = useState<UserMetrics | null>(null);
  const [usageMetrics, setUsageMetrics] = useState<UsageMetrics | null>(null);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Admin access is enforced by the API via SUPER_ADMIN_EMAILS; a 403 sends
  // the user back to the dashboard (see fetchAllMetrics).

  useEffect(() => {
    fetchAllMetrics();
  }, []);

  const fetchAllMetrics = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('access_token');
      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      };

      const [usersRes, usageRes, orgsRes] = await Promise.all([
        fetch(`${API_BASE_URL}/admin/analytics/users`, { headers }),
        fetch(`${API_BASE_URL}/admin/analytics/usage`, { headers }),
        fetch(`${API_BASE_URL}/admin/analytics/organizations?per_page=10`, { headers })
      ]);

      if (usersRes.status === 403 || usageRes.status === 403 || orgsRes.status === 403) {
        navigate('/dashboard');
        return;
      }

      if (!usersRes.ok || !usageRes.ok || !orgsRes.ok) {
        throw new Error('Failed to fetch admin metrics');
      }

      const [users, usage, orgs] = await Promise.all([
        usersRes.json(),
        usageRes.json(),
        orgsRes.json()
      ]);

      setUserMetrics(users);
      setUsageMetrics(usage);
      setOrganizations(orgs.organizations || []);

    } catch (err) {
      console.error('Error fetching admin metrics:', err);
      setError('Failed to load admin metrics');
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-500"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="border border-border rounded-lg bg-transparent p-8 text-center">
          <p className="text-red-400">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border bg-transparent backdrop-blur-xl p-6">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="p-2 rounded-xl bg-secondary">
                <BarChart3 className="w-7 h-7 text-foreground" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-foreground">Admin Dashboard</h1>
                <p className="text-muted-foreground text-sm">Platform analytics and metrics</p>
              </div>
            </div>
            <button
              onClick={fetchAllMetrics}
              className="bg-primary text-primary-foreground hover:bg-white/90 rounded-md px-6 py-2.5 text-sm font-medium"
            >
              Refresh
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Revenue Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <MetricCard
            title="Total Users"
            value={userMetrics?.total_users.toLocaleString() || '0'}
            rawValue={userMetrics?.total_users || 0}
            icon={Users}
            glowColor="blue"
            gradientFrom="from-blue-500"
            gradientTo="to-cyan-600"
            subtitle={`+${userMetrics?.new_users_this_month || 0} this month`}
          />
          <MetricCard
            title="Organizations"
            value={usageMetrics?.total_organizations.toLocaleString() || '0'}
            rawValue={usageMetrics?.total_organizations || 0}
            icon={Building2}
            glowColor="purple"
            gradientFrom="from-purple-500"
            gradientTo="to-violet-600"
            subtitle={`${usageMetrics?.active_organizations || 0} active`}
          />
          <MetricCard
            title="Total Incidents"
            value={usageMetrics?.total_incidents.toLocaleString() || '0'}
            rawValue={usageMetrics?.total_incidents || 0}
            icon={Server}
            glowColor="orange"
            gradientFrom="from-orange-500"
            gradientTo="to-amber-600"
            subtitle={`${usageMetrics?.incidents_this_month || 0} this month`}
          />
        </div>

        {/* User Growth */}
        <div className="border border-border rounded-lg bg-transparent p-6">
          <h3 className="text-base font-medium text-foreground mb-4 flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-secondary">
              <Users className="w-4 h-4 text-foreground" />
            </div>
            User Growth
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatItem
              label="New Today"
              value={userMetrics?.new_users_today || 0}
              trend={userMetrics?.new_users_today || 0 > 0 ? 'up' : 'neutral'}
            />
            <StatItem
              label="New This Week"
              value={userMetrics?.new_users_this_week || 0}
              trend={userMetrics?.new_users_this_week || 0 > 0 ? 'up' : 'neutral'}
            />
            <StatItem
              label="New This Month"
              value={userMetrics?.new_users_this_month || 0}
              trend={userMetrics?.new_users_this_month || 0 > 0 ? 'up' : 'neutral'}
            />
          </div>
          <div className="mt-4 pt-4 border-t border-border">
            <h4 className="text-xs uppercase tracking-wider text-muted-foreground mb-2">Active Users</h4>
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <p className="text-muted-foreground">Today</p>
                <p className="text-foreground font-semibold">{userMetrics?.active_users_today || 0}</p>
              </div>
              <div>
                <p className="text-muted-foreground">This Week</p>
                <p className="text-foreground font-semibold">{userMetrics?.active_users_this_week || 0}</p>
              </div>
              <div>
                <p className="text-muted-foreground">This Month</p>
                <p className="text-foreground font-semibold">{userMetrics?.active_users_this_month || 0}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Recent Organizations */}
        <div className="border border-border rounded-lg bg-transparent p-6">
          <h3 className="text-base font-medium text-foreground mb-4 flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-secondary">
              <Building2 className="w-4 h-4 text-foreground" />
            </div>
            Recent Organizations
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-muted-foreground text-xs uppercase tracking-wider border-b border-border">
                  <th className="pb-3 font-medium">Organization</th>
                  <th className="pb-3 font-medium">Users</th>
                  <th className="pb-3 font-medium">Incidents</th>
                  <th className="pb-3 font-medium">Created</th>
                  <th className="pb-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="text-sm">
                {organizations.map((org) => (
                  <tr key={org.id} className="border-b border-border hover:bg-accent transition-colors">
                    <td className="py-3">
                      <div className="text-foreground font-medium">{org.name}</div>
                      <div className="text-muted-foreground text-xs">{org.slug}</div>
                    </td>
                    <td className="py-3 text-foreground">{org.user_count}</td>
                    <td className="py-3 text-foreground">{org.incident_count}</td>
                    <td className="py-3 text-muted-foreground">{formatDate(org.created_at)}</td>
                    <td className="py-3">
                      <div className="flex items-center gap-2">
                        <span className={`h-2.5 w-2.5 rounded-full ${org.is_active ? 'bg-emerald-500' : 'bg-red-500'} inline-block`} />
                        <span className={org.is_active ? 'text-green-400' : 'text-red-400'}>
                          {org.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

// Helper Components
interface MetricCardProps {
  title: string;
  value: string;
  rawValue: number;
  icon: React.ElementType;
  glowColor: 'green' | 'blue' | 'purple' | 'orange';
  gradientFrom: string;
  gradientTo: string;
  subtitle?: string;
}

const MetricCard: React.FC<MetricCardProps> = ({ title, value, rawValue, icon: Icon, glowColor, gradientFrom, gradientTo, subtitle }) => (
  <div className="border border-border rounded-lg bg-transparent p-6">
    <div className="flex items-center justify-between mb-2">
      <p className="text-muted-foreground text-sm">{title}</p>
      <div className={`p-2 rounded-lg bg-secondary`}>
        <Icon className="w-5 h-5 text-foreground" />
      </div>
    </div>
    <p className="text-2xl font-bold text-foreground mb-1">
      <span>{rawValue}</span>
    </p>
    {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
  </div>
);

interface StatItemProps {
  label: string;
  value: number;
  trend: 'up' | 'down' | 'neutral';
}

const StatItem: React.FC<StatItemProps> = ({ label, value, trend }) => (
  <div className="border border-border rounded-lg bg-transparent p-4">
    <p className="text-muted-foreground text-sm mb-1">{label}</p>
    <div className="flex items-center gap-2">
      <p className="text-2xl font-bold text-foreground">
        <span>{value}</span>
      </p>
      {trend === 'up' && <TrendingUp className="w-5 h-5 text-green-400" />}
      {trend === 'down' && <TrendingDown className="w-5 h-5 text-red-400" />}
    </div>
  </div>
);

export default AdminDashboard;
