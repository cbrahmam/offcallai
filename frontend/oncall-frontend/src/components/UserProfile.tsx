// frontend/src/components/UserProfile.tsx - Truly minimalistic (removes fluff)
import React, { useState, useEffect } from 'react';
import {
  Check,
  Mail,
  Pencil,
  User,
  X
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useNotifications } from '../contexts/NotificationContext';
import { API_URL } from '../config/api';

interface ProfileData {
  full_name: string;
  email: string;
  role: string;
  organization_name: string;
}

const UserProfile: React.FC = () => {
  const { user } = useAuth();
  const { showToast } = useNotifications();
  const [isEditing, setIsEditing] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [profileData, setProfileData] = useState<ProfileData>({
    full_name: '',
    email: '',
    role: '',
    organization_name: ''
  });

  // Load user data on component mount
  useEffect(() => {
    if (user) {
      setProfileData({
        full_name: user.full_name || '',
        email: user.email || '',
        role: user.role || '',
        organization_name: user.organization_name || ''
      });
    }
  }, [user]);

  const handleSave = async () => {
    if (!profileData.full_name.trim()) {
      showToast({
        type: 'error',
        title: 'Error',
        message: 'Name is required'
      });
      return;
    }

    setIsLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_URL}/users/profile`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          full_name: profileData.full_name,
          role: profileData.role
        })
      });

      if (response.ok) {
        showToast({
          type: 'success',
          title: 'Profile Updated',
          message: 'Your profile has been updated successfully'
        });
        setIsEditing(false);
      } else {
        throw new Error('Failed to update profile');
      }
    } catch (error) {
      showToast({
        type: 'error',
        title: 'Error',
        message: 'Failed to update profile. Please try again.'
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = () => {
    if (user) {
      setProfileData({
        full_name: user.full_name || '',
        email: user.email || '',
        role: user.role || '',
        organization_name: user.organization_name || ''
      });
    }
    setIsEditing(false);
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="relative overflow-hidden border-b border-border">
        <div className="relative max-w-2xl mx-auto px-6 py-6">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-2xl bg-secondary">
              <User className="w-7 h-7 text-foreground" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-foreground">Profile</h1>
              <p className="text-muted-foreground text-sm">Manage your account information</p>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-6 py-8">
        {/* Profile Card */}
        <div className="bg-transparent border border-border rounded-xl p-8">

          {/* Profile Picture & Basic Info */}
          <div className="flex items-center space-x-6 mb-8">
            <div className="w-20 h-20 bg-secondary rounded-full flex items-center justify-center">
              <span className="text-foreground text-2xl font-bold">
                {profileData.full_name.charAt(0)?.toUpperCase() || 'U'}
              </span>
            </div>
            <div className="flex-1">
              <h2 className="text-base font-medium text-foreground">{profileData.full_name || 'User'}</h2>
              <p className="text-muted-foreground text-sm">{profileData.organization_name}</p>
            </div>
            <button
              onClick={() => setIsEditing(!isEditing)}
              className="p-2 text-muted-foreground hover:text-foreground transition-colors"
            >
              {isEditing ? (
                <X className="w-5 h-5" />
              ) : (
                <Pencil className="w-5 h-5" />
              )}
            </button>
          </div>

          {/* Profile Information - ESSENTIAL ONLY */}
          <div className="space-y-6">
            
            {/* Name */}
            <div>
              <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-2">Full Name</label>
              {isEditing ? (
                <input
                  type="text"
                  value={profileData.full_name}
                  onChange={(e) => setProfileData(prev => ({ ...prev, full_name: e.target.value }))}
                  className="w-full px-4 py-3 bg-transparent border border-border rounded-lg text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/30"
                  placeholder="Enter your full name"
                />
              ) : (
                <div className="flex items-center space-x-3 px-4 py-3 bg-secondary/50 rounded-lg border border-border">
                  <User className="w-5 h-5 text-muted-foreground" />
                  <span className="text-foreground text-sm">{profileData.full_name || 'Not set'}</span>
                </div>
              )}
            </div>

            {/* Email - Read only */}
            <div>
              <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-2">Email</label>
              <div className="flex items-center space-x-3 px-4 py-3 bg-secondary/50 rounded-lg border border-border">
                <Mail className="w-5 h-5 text-muted-foreground" />
                <span className="text-foreground text-sm">{profileData.email}</span>
                <span className="text-xs text-muted-foreground">(cannot be changed)</span>
              </div>
            </div>

            {/* Role */}
            <div>
              <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-2">Role</label>
              {isEditing ? (
                <select
                  value={profileData.role}
                  onChange={(e) => setProfileData(prev => ({ ...prev, role: e.target.value }))}
                  className="w-full px-4 py-3 bg-transparent border border-border rounded-lg text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/30"
                >
                  <option value="engineer">Engineer</option>
                  <option value="senior_engineer">Senior Engineer</option>
                  <option value="lead">Tech Lead</option>
                  <option value="manager">Manager</option>
                  <option value="admin">Admin</option>
                </select>
              ) : (
                <div className="px-4 py-3 bg-secondary/50 rounded-lg border border-border">
                  <span className="text-foreground text-sm capitalize">{profileData.role || 'Not set'}</span>
                </div>
              )}
            </div>

            {/* Organization - Read only */}
            <div>
              <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-2">Organization</label>
              <div className="px-4 py-3 bg-secondary/50 rounded-lg border border-border">
                <span className="text-foreground text-sm">{profileData.organization_name}</span>
                <span className="text-xs text-muted-foreground ml-2">(managed by admin)</span>
              </div>
            </div>

            {/* Action Buttons */}
            {isEditing && (
              <div className="flex space-x-3 pt-4">
                <button
                  onClick={handleCancel}
                  disabled={isLoading}
                  className="flex-1 px-4 py-3 bg-transparent text-foreground rounded-lg hover:bg-accent border border-border transition-colors font-medium disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={isLoading}
                  className="flex-1 px-4 py-3 bg-primary text-primary-foreground hover:bg-white/90 rounded-lg transition-all font-medium disabled:opacity-50 flex items-center justify-center space-x-2"
                >
                  {isLoading ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                      <span>Saving...</span>
                    </>
                  ) : (
                    <>
                      <Check className="w-4 h-4" />
                      <span>Save Changes</span>
                    </>
                  )}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default UserProfile;