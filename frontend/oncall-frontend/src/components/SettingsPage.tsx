// frontend/src/components/SettingsPage.tsx
import React, { useState, useEffect } from 'react';
import {
  ArrowUpDown,
  Building2,
  Key,
  Link,
  Plus,
  Settings2,
  ShieldCheck,
  User
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useNotifications } from '../contexts/NotificationContext';
import APIKeyManagement from './APIKeyManagement';
import IntegrationsTab from './IntegrationsTab';
// Magic UI removed for Vercel-style

import { API_URL as API_BASE_URL } from '../config/api';

interface Organization {
  id: string;
  name: string;
  slug?: string;
  max_users: number;
}

interface TeamMember {
  id: string;
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
}

interface EscalationPolicy {
  id: string;
  name: string;
  description: string;
  steps: number;
  is_default: boolean;
}

type TabId = 'profile' | 'api_keys' | 'integrations' | 'organization' | 'escalations' | 'security';

const SettingsPage: React.FC = () => {
  const { user } = useAuth();
  const { showToast } = useNotifications();

  // Invite member modal state
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('member');
  const [isInviting, setIsInviting] = useState(false);

  // Initialize activeTab from URL search params to preserve state across re-renders
  const getInitialTab = (): TabId => {
    const params = new URLSearchParams(window.location.search);
    const tabFromUrl = params.get('tab') as TabId | null;
    const validTabs: TabId[] = ['profile', 'api_keys', 'integrations', 'organization', 'escalations', 'security'];
    if (tabFromUrl && validTabs.includes(tabFromUrl)) {
      return tabFromUrl;
    }
    return 'profile';
  };

  const [activeTab, setActiveTab] = useState<TabId>(getInitialTab);
  const [isLoading, setIsLoading] = useState(true);

  // Update URL when tab changes
  const handleTabChange = (newTab: TabId) => {
    setActiveTab(newTab);
    const url = new URL(window.location.href);
    url.searchParams.set('tab', newTab);
    window.history.replaceState(null, '', url.toString());
  };

  // Real data states
  const [organization, setOrganization] = useState<Organization | null>(null);
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [escalationPolicies, setEscalationPolicies] = useState<EscalationPolicy[]>([
    { id: '1', name: 'Default Policy', description: 'Standard escalation for all incidents', steps: 3, is_default: true },
    { id: '2', name: 'Critical Incidents', description: 'Fast escalation for P1 incidents', steps: 2, is_default: false },
  ]);

  const tabs = [
    { id: 'profile' as TabId, name: 'Profile', icon: User },
    { id: 'api_keys' as TabId, name: 'API Keys', icon: Key },
    { id: 'integrations' as TabId, name: 'Integrations', icon: Link },
    { id: 'organization' as TabId, name: 'Organization', icon: Building2 },
    { id: 'escalations' as TabId, name: 'Escalations', icon: ArrowUpDown },
    { id: 'security' as TabId, name: 'Security', icon: ShieldCheck },
  ];

  // Fetch real data from APIs
  useEffect(() => {
    const fetchData = async () => {
      try {
        const token = localStorage.getItem('access_token');
        const headers = {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        };

        // Fetch organization details
        const orgResponse = await fetch(`${API_BASE_URL}/organizations/me`, { headers });
        if (orgResponse.ok) {
          const orgData = await orgResponse.json();
          setOrganization(orgData);
        }

        // Fetch team members
        const teamResponse = await fetch(`${API_BASE_URL}/organizations/me/members`, { headers });
        if (teamResponse.ok) {
          const teamData = await teamResponse.json();
          setTeamMembers(teamData.members || []);
        }

      } catch (error) {
        console.error('Error fetching settings data:', error);
        showToast({
          type: 'error',
          title: 'Failed to load settings',
          message: 'Could not fetch your settings data. Please refresh the page.',
          autoClose: true,
          duration: 5000
        });
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Only run once on mount


  // Invite member handler
  const handleInviteMember = async () => {
    if (!inviteEmail || !inviteEmail.includes('@')) {
      showToast({
        type: 'error',
        title: 'Invalid Email',
        message: 'Please enter a valid email address',
        autoClose: true,
      });
      return;
    }

    setIsInviting(true);
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/organizations/me/invite`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: inviteEmail,
          role: inviteRole,
        }),
      });

      const data = await response.json();

      if (response.ok) {
        if (data.email_sent === false && data.invite_link) {
          // Email failed, show the link for manual sharing
          showToast({
            type: 'warning',
            title: 'Invitation Created',
            message: 'Email could not be sent. Copy the invite link to share manually.',
            autoClose: false,
          });
          // Copy invite link to clipboard
          navigator.clipboard.writeText(data.invite_link).then(() => {
            showToast({
              type: 'info',
              title: 'Link Copied',
              message: 'Invite link has been copied to your clipboard',
              autoClose: true,
            });
          });
        } else {
          showToast({
            type: 'success',
            title: 'Invitation Sent',
            message: `Invitation sent to ${inviteEmail}`,
            autoClose: true,
          });
        }
        setShowInviteModal(false);
        setInviteEmail('');
        setInviteRole('member');
      } else {
        throw new Error(data.detail || 'Failed to send invitation');
      }
    } catch (error: any) {
      showToast({
        type: 'error',
        title: 'Invitation Failed',
        message: error.message || 'Failed to send invitation',
        autoClose: true,
      });
    } finally {
      setIsInviting(false);
    }
  };

  const ProfileTab = () => (
    <div className="space-y-6">
      <div className="bg-transparent border border-border rounded-xl p-6">
        <h3 className="text-base font-medium text-foreground mb-4">Personal Information</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-2">Full Name</label>
            <input
              type="text"
              defaultValue={user?.full_name || ''}
              className="w-full px-4 py-3 bg-accent border border-border rounded-xl text-foreground placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-2">Email Address</label>
            <input
              type="email"
              defaultValue={user?.email || ''}
              className="w-full px-4 py-3 bg-accent border border-border rounded-xl text-foreground placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-2">Phone Number</label>
            <input
              type="tel"
              placeholder="+1 (555) 123-4567"
              className="w-full px-4 py-3 bg-accent border border-border rounded-xl text-foreground placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-2">Timezone</label>
            <select className="w-full px-4 py-3 bg-accent border border-border rounded-xl text-foreground focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20">
              <option value="UTC">UTC (Coordinated Universal Time)</option>
              <option value="EST">EST (Eastern Standard Time)</option>
              <option value="PST">PST (Pacific Standard Time)</option>
              <option value="CST">CST (Central Standard Time)</option>
            </select>
          </div>
        </div>
        <div className="mt-6">
          <button className="bg-primary text-primary-foreground hover:bg-white/90 px-6 py-2.5 rounded-lg transition-colors font-medium">
            Save Changes
          </button>
        </div>
      </div>
    </div>
  );

  const OrganizationTab = () => (
    <div className="space-y-6">
      <div className="bg-transparent border border-border rounded-xl p-6">
        <h3 className="text-base font-medium text-foreground mb-4">Organization Settings</h3>
        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-2">Organization Name</label>
            <input
              type="text"
              defaultValue={organization?.name || ''}
              className="w-full px-4 py-3 bg-accent border border-border rounded-xl text-foreground placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-2">Organization Slug</label>
            <div className="flex items-center space-x-3">
              <span className="text-muted-foreground">/status/</span>
              <input
                type="text"
                defaultValue={organization?.slug || ''}
                className="flex-1 px-4 py-3 bg-accent border border-border rounded-xl text-foreground placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
              />
            </div>
          </div>

        </div>

        <div className="mt-6">
          <button className="bg-primary text-primary-foreground hover:bg-white/90 px-6 py-2.5 rounded-lg transition-colors font-medium">
            Save Changes
          </button>
        </div>
      </div>

      <div className="bg-transparent border border-border rounded-xl p-6">
        <h3 className="text-base font-medium text-foreground mb-4">Team Members</h3>
        {isLoading ? (
          <div className="animate-pulse space-y-3">
            {[...Array(2)].map((_, i) => (
              <div key={i} className="h-16 bg-accent rounded-lg"></div>
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            {teamMembers.map((member) => (
              <div key={member.id} className="flex items-center justify-between p-4 bg-secondary/30 rounded-lg">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 bg-secondary rounded-full flex items-center justify-center">
                    <span className="text-foreground font-medium">
                      {member.full_name.split(' ').map(n => n[0]).join('').toUpperCase()}
                    </span>
                  </div>
                  <div>
                    <h4 className="text-foreground font-medium">{member.full_name}</h4>
                    <p className="text-muted-foreground text-sm">{member.email} • {member.role}</p>
                  </div>
                </div>
                <span className="px-2 py-1 rounded-full text-xs font-medium bg-green-500/20 text-green-500">
                  {member.role}
                </span>
              </div>
            ))}
          </div>
        )}

        <button
          onClick={() => setShowInviteModal(true)}
          className="w-full mt-4 bg-accent hover:bg-secondary text-foreground px-4 py-3 rounded-xl transition-colors font-medium flex items-center justify-center space-x-2 border border-border"
        >
          <Plus className="w-5 h-5" />
          <span>Invite Team Member</span>
        </button>
      </div>
    </div>
  );

  const EscalationsTab = () => (
    <div className="space-y-6">
      <div className="bg-transparent border border-border rounded-xl p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-base font-medium text-foreground">Escalation Policies</h3>
            <p className="text-muted-foreground text-sm mt-1">Define how incidents are escalated to your team</p>
          </div>
          <button className="bg-primary text-primary-foreground hover:bg-white/90 px-4 py-2 rounded-lg transition-colors font-medium flex items-center space-x-2">
            <Plus className="w-5 h-5" />
            <span>New Policy</span>
          </button>
        </div>

        <div className="space-y-4">
          {escalationPolicies.map((policy) => (
            <div key={policy.id} className="flex items-center justify-between p-4 bg-secondary/30 rounded-lg border border-border hover:border-white/20 transition-colors">
              <div className="flex items-center space-x-4">
                <div className="w-10 h-10 bg-secondary rounded-lg flex items-center justify-center">
                  <ArrowUpDown className="w-5 h-5 text-foreground" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="text-foreground font-medium">{policy.name}</h4>
                    {policy.is_default && (
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-secondary text-foreground">
                        Default
                      </span>
                    )}
                  </div>
                  <p className="text-muted-foreground text-sm">{policy.description}</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-muted-foreground text-sm">{policy.steps} steps</span>
                <button className="text-muted-foreground hover:text-foreground transition-colors">
                  Edit
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-transparent border border-border rounded-xl p-6">
        <h3 className="text-base font-medium text-foreground mb-4">Escalation Settings</h3>
        <div className="space-y-4">
          <div className="flex items-center justify-between p-4 bg-secondary/30 rounded-lg">
            <div>
              <h4 className="text-foreground font-medium">Auto-escalate unacknowledged incidents</h4>
              <p className="text-muted-foreground text-sm">Automatically escalate if no response within timeout</p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" defaultChecked className="sr-only peer" />
              <div className="w-11 h-6 bg-secondary peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-white"></div>
            </label>
          </div>

          <div className="flex items-center justify-between p-4 bg-secondary/30 rounded-lg">
            <div>
              <h4 className="text-foreground font-medium">Default acknowledgment timeout</h4>
              <p className="text-muted-foreground text-sm">Time before escalating to next level</p>
            </div>
            <select className="px-3 py-2 bg-accent border border-border rounded-lg text-foreground focus:outline-none focus:ring-1 focus:ring-white/10">
              <option value="5">5 minutes</option>
              <option value="10">10 minutes</option>
              <option value="15" selected>15 minutes</option>
              <option value="30">30 minutes</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  );

  const SecurityTab = () => (
    <div className="space-y-6">
      <div className="bg-transparent border border-border rounded-xl p-6">
        <h3 className="text-base font-medium text-foreground mb-4">Password & Authentication</h3>
        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-2">Current Password</label>
            <input
              type="password"
              className="w-full px-4 py-3 bg-accent border border-border rounded-xl text-foreground placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
              placeholder="Enter current password"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-2">New Password</label>
            <input
              type="password"
              className="w-full px-4 py-3 bg-accent border border-border rounded-xl text-foreground placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
              placeholder="Enter new password"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-2">Confirm New Password</label>
            <input
              type="password"
              className="w-full px-4 py-3 bg-accent border border-border rounded-xl text-foreground placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
              placeholder="Confirm new password"
            />
          </div>
        </div>

        <div className="mt-6">
          <button className="bg-primary text-primary-foreground hover:bg-white/90 px-6 py-2.5 rounded-lg transition-colors font-medium">
            Update Password
          </button>
        </div>
      </div>

      <div className="bg-transparent border border-border rounded-xl p-6">
        <h3 className="text-base font-medium text-foreground mb-4">Two-Factor Authentication</h3>
        <div className="flex items-center justify-between p-4 bg-secondary/30 rounded-lg">
          <div>
            <h4 className="text-foreground font-medium">2FA via Authentication App</h4>
            <p className="text-muted-foreground text-sm">Add an extra layer of security to your account</p>
          </div>
          <button className="bg-green-500/20 text-green-500 hover:bg-green-500/30 px-4 py-2 rounded-lg transition-colors font-medium">
            Enable 2FA
          </button>
        </div>
      </div>
    </div>
  );

  const renderTabContent = () => {
    switch (activeTab) {
      case 'profile':
        return <ProfileTab />;
      case 'api_keys':
        return <APIKeyManagement />;
      case 'integrations':
        return <IntegrationsTab />;
      case 'organization':
        return <OrganizationTab />;
      case 'escalations':
        return <EscalationsTab />;
      case 'security':
        return <SecurityTab />;
      default:
        return <ProfileTab />;
    }
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex items-center gap-4">
            <div className="p-2.5 rounded-lg bg-secondary">
              <Settings2 className="w-5 h-5 text-muted-foreground" />
            </div>
            <div>
              <h1 className="text-base font-medium text-foreground">Settings</h1>
              <p className="text-muted-foreground text-sm">Manage your account, team, and integrations</p>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-6">
        <div className="flex flex-col lg:flex-row gap-6">
          <div className="lg:w-64 flex-shrink-0">
            <div className="sticky top-4 border border-border rounded-lg p-3">
              <nav className="space-y-0.5">
                {tabs.map((tab) => {
                  return (
                    <button
                      key={tab.id}
                      onClick={() => handleTabChange(tab.id)}
                      className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg transition-colors text-left ${
                        activeTab === tab.id
                          ? 'bg-secondary text-foreground'
                          : 'text-muted-foreground hover:text-foreground hover:bg-accent'
                      }`}
                    >
                      <tab.icon className={`w-4 h-4 ${activeTab === tab.id ? 'text-foreground' : 'text-muted-foreground'}`} />
                      <span className="text-sm font-medium">{tab.name}</span>
                    </button>
                  )
                })}
              </nav>
            </div>
          </div>

          <div className="flex-1 min-w-0">
            {renderTabContent()}
          </div>
        </div>
      </div>

      {/* Invite Member Modal */}
      {showInviteModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-background border border-border rounded-lg p-6 w-full max-w-md mx-4">
            <h3 className="text-base font-medium text-foreground mb-4">Invite Team Member</h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-muted-foreground mb-2">
                  Email Address
                </label>
                <input
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="colleague@company.com"
                  className="w-full px-4 py-3 bg-accent border border-border rounded-xl text-foreground placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
                  disabled={isInviting}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-muted-foreground mb-2">
                  Role
                </label>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value)}
                  className="w-full px-4 py-3 bg-accent border border-border rounded-xl text-foreground focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
                  disabled={isInviting}
                >
                  <option value="member">Member</option>
                  <option value="admin">Admin</option>
                </select>
                <p className="text-xs text-muted-foreground mt-1">
                  Admins can manage team members and organization settings.
                </p>
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => {
                  setShowInviteModal(false);
                  setInviteEmail('');
                  setInviteRole('member');
                }}
                className="px-4 py-2 text-muted-foreground hover:text-foreground transition-colors"
                disabled={isInviting}
              >
                Cancel
              </button>
              <button
                onClick={handleInviteMember}
                disabled={isInviting || !inviteEmail}
                className="bg-primary text-primary-foreground hover:bg-white/90 px-6 py-2 rounded-lg transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isInviting ? (
                  <>
                    <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <span>Sending...</span>
                  </>
                ) : (
                  <span>Send Invitation</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SettingsPage;
