// frontend/oncall-frontend/src/hooks/useSidebarPreferences.ts
// Hook for managing sidebar favorites and UI preferences with localStorage + backend sync

import { useState, useEffect, useCallback, useRef } from 'react';

import { API_URL as API_BASE_URL } from '../config/api';

const STORAGE_KEY = 'offcall_sidebar_preferences';
const SYNC_DEBOUNCE_MS = 2000; // 2 seconds

export interface SidebarPreferences {
  sidebar_favorites: string[];
  sidebar_favorites_order: string[];
  sidebar_collapsed: boolean;
  all_features_expanded: boolean;
}

const DEFAULT_PREFERENCES: SidebarPreferences = {
  sidebar_favorites: ['dashboard', 'incidents', 'alerts', 'logs'],
  sidebar_favorites_order: ['dashboard', 'incidents', 'alerts', 'logs'],
  sidebar_collapsed: false,
  all_features_expanded: true,
};

export function useSidebarPreferences() {
  const [preferences, setPreferences] = useState<SidebarPreferences>(DEFAULT_PREFERENCES);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const syncTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Load preferences from localStorage on mount
  useEffect(() => {
    const loadPreferences = async () => {
      try {
        // First load from localStorage for instant UI
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
          const parsed = JSON.parse(stored);
          setPreferences({ ...DEFAULT_PREFERENCES, ...parsed });
        }

        // Then fetch from backend to sync across devices
        const token = localStorage.getItem('access_token');
        if (token) {
          const response = await fetch(`${API_BASE_URL}/users/ui-preferences`, {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
          });

          if (response.ok) {
            const backendPrefs = await response.json();
            // Safely merge preferences, ensuring we have valid data
            const mergedPrefs = {
              sidebar_favorites: backendPrefs?.sidebar_favorites || DEFAULT_PREFERENCES.sidebar_favorites,
              sidebar_favorites_order: backendPrefs?.sidebar_favorites_order || DEFAULT_PREFERENCES.sidebar_favorites_order,
              sidebar_collapsed: backendPrefs?.sidebar_collapsed ?? DEFAULT_PREFERENCES.sidebar_collapsed,
              all_features_expanded: backendPrefs?.all_features_expanded ?? DEFAULT_PREFERENCES.all_features_expanded,
            };
            setPreferences(mergedPrefs);
            localStorage.setItem(STORAGE_KEY, JSON.stringify(mergedPrefs));
          }
        }
      } catch (error) {
        console.error('Failed to load sidebar preferences:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadPreferences();
  }, []);

  // Sync preferences to backend (debounced)
  const syncToBackend = useCallback(async (prefs: SidebarPreferences) => {
    try {
      setIsSyncing(true);
      const token = localStorage.getItem('access_token');
      if (!token) return;

      await fetch(`${API_BASE_URL}/users/ui-preferences`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(prefs),
      });
    } catch (error) {
      console.error('Failed to sync sidebar preferences:', error);
    } finally {
      setIsSyncing(false);
    }
  }, []);

  // Update preferences with debounced backend sync
  const updatePreferences = useCallback((updates: Partial<SidebarPreferences>) => {
    setPreferences((prev) => {
      const newPrefs = { ...prev, ...updates };

      // Save to localStorage immediately
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newPrefs));

      // Debounce backend sync
      if (syncTimeoutRef.current) {
        clearTimeout(syncTimeoutRef.current);
      }
      syncTimeoutRef.current = setTimeout(() => {
        syncToBackend(newPrefs);
      }, SYNC_DEBOUNCE_MS);

      return newPrefs;
    });
  }, [syncToBackend]);

  // Add item to favorites
  const addToFavorites = useCallback((itemId: string) => {
    setPreferences((prev) => {
      if (prev.sidebar_favorites.includes(itemId)) {
        return prev; // Already in favorites
      }

      const newFavorites = [...prev.sidebar_favorites, itemId];
      const newOrder = [...prev.sidebar_favorites_order, itemId];
      const newPrefs = {
        ...prev,
        sidebar_favorites: newFavorites,
        sidebar_favorites_order: newOrder,
      };

      localStorage.setItem(STORAGE_KEY, JSON.stringify(newPrefs));

      if (syncTimeoutRef.current) {
        clearTimeout(syncTimeoutRef.current);
      }
      syncTimeoutRef.current = setTimeout(() => {
        syncToBackend(newPrefs);
      }, SYNC_DEBOUNCE_MS);

      return newPrefs;
    });
  }, [syncToBackend]);

  // Remove item from favorites
  const removeFromFavorites = useCallback((itemId: string) => {
    setPreferences((prev) => {
      const newFavorites = prev.sidebar_favorites.filter((id) => id !== itemId);
      const newOrder = prev.sidebar_favorites_order.filter((id) => id !== itemId);
      const newPrefs = {
        ...prev,
        sidebar_favorites: newFavorites,
        sidebar_favorites_order: newOrder,
      };

      localStorage.setItem(STORAGE_KEY, JSON.stringify(newPrefs));

      if (syncTimeoutRef.current) {
        clearTimeout(syncTimeoutRef.current);
      }
      syncTimeoutRef.current = setTimeout(() => {
        syncToBackend(newPrefs);
      }, SYNC_DEBOUNCE_MS);

      return newPrefs;
    });
  }, [syncToBackend]);

  // Reorder favorites (for drag and drop)
  const reorderFavorites = useCallback((newOrder: string[]) => {
    setPreferences((prev) => {
      const newPrefs = {
        ...prev,
        sidebar_favorites: newOrder,
        sidebar_favorites_order: newOrder,
      };

      localStorage.setItem(STORAGE_KEY, JSON.stringify(newPrefs));

      if (syncTimeoutRef.current) {
        clearTimeout(syncTimeoutRef.current);
      }
      syncTimeoutRef.current = setTimeout(() => {
        syncToBackend(newPrefs);
      }, SYNC_DEBOUNCE_MS);

      return newPrefs;
    });
  }, [syncToBackend]);

  // Move item up in favorites
  const moveFavoriteUp = useCallback((itemId: string) => {
    setPreferences((prev) => {
      const index = prev.sidebar_favorites_order.indexOf(itemId);
      if (index <= 0) return prev; // Already at top or not found

      const newOrder = [...prev.sidebar_favorites_order];
      [newOrder[index - 1], newOrder[index]] = [newOrder[index], newOrder[index - 1]];

      const newPrefs = {
        ...prev,
        sidebar_favorites: newOrder,
        sidebar_favorites_order: newOrder,
      };

      localStorage.setItem(STORAGE_KEY, JSON.stringify(newPrefs));

      if (syncTimeoutRef.current) {
        clearTimeout(syncTimeoutRef.current);
      }
      syncTimeoutRef.current = setTimeout(() => {
        syncToBackend(newPrefs);
      }, SYNC_DEBOUNCE_MS);

      return newPrefs;
    });
  }, [syncToBackend]);

  // Move item down in favorites
  const moveFavoriteDown = useCallback((itemId: string) => {
    setPreferences((prev) => {
      const index = prev.sidebar_favorites_order.indexOf(itemId);
      if (index === -1 || index >= prev.sidebar_favorites_order.length - 1) {
        return prev; // Not found or already at bottom
      }

      const newOrder = [...prev.sidebar_favorites_order];
      [newOrder[index], newOrder[index + 1]] = [newOrder[index + 1], newOrder[index]];

      const newPrefs = {
        ...prev,
        sidebar_favorites: newOrder,
        sidebar_favorites_order: newOrder,
      };

      localStorage.setItem(STORAGE_KEY, JSON.stringify(newPrefs));

      if (syncTimeoutRef.current) {
        clearTimeout(syncTimeoutRef.current);
      }
      syncTimeoutRef.current = setTimeout(() => {
        syncToBackend(newPrefs);
      }, SYNC_DEBOUNCE_MS);

      return newPrefs;
    });
  }, [syncToBackend]);

  // Toggle sidebar collapsed state
  const toggleCollapsed = useCallback(() => {
    updatePreferences({ sidebar_collapsed: !preferences.sidebar_collapsed });
  }, [preferences.sidebar_collapsed, updatePreferences]);

  // Toggle all features expanded state
  const toggleAllFeaturesExpanded = useCallback(() => {
    updatePreferences({ all_features_expanded: !preferences.all_features_expanded });
  }, [preferences.all_features_expanded, updatePreferences]);

  // Check if item is in favorites
  const isFavorite = useCallback((itemId: string) => {
    return preferences.sidebar_favorites.includes(itemId);
  }, [preferences.sidebar_favorites]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (syncTimeoutRef.current) {
        clearTimeout(syncTimeoutRef.current);
      }
    };
  }, []);

  return {
    preferences,
    isLoading,
    isSyncing,
    addToFavorites,
    removeFromFavorites,
    reorderFavorites,
    moveFavoriteUp,
    moveFavoriteDown,
    toggleCollapsed,
    toggleAllFeaturesExpanded,
    isFavorite,
    updatePreferences,
  };
}

export default useSidebarPreferences;
