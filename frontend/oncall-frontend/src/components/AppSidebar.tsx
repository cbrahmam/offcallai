// frontend/oncall-frontend/src/components/AppSidebar.tsx
import * as React from "react"
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bell,
  BookOpen,
  Bug,
  Calendar,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  ChevronsUpDown,
  Container,
  Cpu,
  Database,
  Eye,
  FileText,
  Gauge,
  Globe,
  GripVertical,
  HelpCircle,
  LayoutDashboard,
  LogOut,
  MousePointer,
  Network,
  PanelLeft,
  PanelLeftClose,
  Plus,
  Server,
  Settings,
  Star,
  StarOff,
  Target,
  Wrench,
  Zap
} from 'lucide-react';
import { useTheme } from "../hooks/use-theme"
import { useSidebarPreferences } from "../hooks/useSidebarPreferences"

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarRail,
  useSidebar,
} from "./ui/sidebar"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "./ui/collapsible"

// All available navigation items (flat list for easy reference)
interface NavItem {
  id: string
  label: string
  icon: React.ComponentType<{ className?: string }>
  page: string
}

const ALL_NAV_ITEMS: NavItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, page: 'dashboard' },
  { id: 'incidents', label: 'Incidents', icon: AlertTriangle, page: 'incidents' },
  { id: 'alerts', label: 'Alerts', icon: Bell, page: 'alerts' },
  { id: 'alert-rules', label: 'Alert Rules', icon: Target, page: 'alert-rules' },
  { id: 'on-call-schedules', label: 'On-Call Schedules', icon: Calendar, page: 'on-call-schedules' },
  { id: 'maintenance-windows', label: 'Maintenance', icon: Wrench, page: 'maintenance-windows' },
  { id: 'infrastructure', label: 'Infrastructure', icon: Server, page: 'infrastructure' },
  { id: 'containers', label: 'Containers / K8s', icon: Container, page: 'containers' },
  { id: 'databases', label: 'Databases', icon: Database, page: 'databases' },
  { id: 'logs', label: 'Logs', icon: FileText, page: 'logs' },
  { id: 'apm', label: 'APM & Traces', icon: Activity, page: 'apm' },
  { id: 'profiling', label: 'Profiling', icon: Cpu, page: 'profiling' },
  { id: 'errors', label: 'Error Tracking', icon: Bug, page: 'errors' },
  { id: 'rum', label: 'Browser RUM', icon: MousePointer, page: 'rum' },
  { id: 'runbooks', label: 'Runbooks', icon: BookOpen, page: 'runbooks' },
  { id: 'deployments', label: 'Deployments', icon: Gauge, page: 'deployments' },
  { id: 'analytics', label: 'Analytics', icon: BarChart3, page: 'analytics' },
  { id: 'cost-attribution', label: 'Cost Attribution', icon: BarChart3, page: 'cost-attribution' },
  { id: 'post-mortems', label: 'Post-Mortems', icon: FileText, page: 'post-mortems' },
];

// Create a map for quick lookup
const NAV_ITEMS_MAP = ALL_NAV_ITEMS.reduce((acc, item) => {
  acc[item.id] = item;
  return acc;
}, {} as Record<string, NavItem>);

interface AppSidebarProps {
  currentPage: string
  onNavigate: (page: string) => void
  user: {
    full_name: string
    email: string
    role: string
  } | null
  onLogout: () => void
  unreadCount?: number
  onToggleNotifications?: () => void
}

export function AppSidebar({
  currentPage,
  onNavigate,
  user,
  onLogout,
  unreadCount = 0,
  onToggleNotifications,
}: AppSidebarProps) {
  const { state, toggleSidebar } = useSidebar()
  const isCollapsed = state === "collapsed"
  const { theme, setTheme } = useTheme()
  const [userMenuOpen, setUserMenuOpen] = React.useState(false)
  const userMenuRef = React.useRef<HTMLDivElement>(null)
  const [hoveredItem, setHoveredItem] = React.useState<string | null>(null)

  // Use the sidebar preferences hook
  const {
    preferences,
    isLoading: prefsLoading,
    addToFavorites,
    removeFromFavorites,
    moveFavoriteUp,
    moveFavoriteDown,
    isFavorite,
    toggleAllFeaturesExpanded,
  } = useSidebarPreferences()

  // Close user menu when clicking outside
  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false)
      }
    }
    if (userMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [userMenuOpen])

  // Handle navigation click
  const handleNavClick = (page: string) => {
    onNavigate(page)
  }

  // Check if a page is active
  const isPageActive = (page: string) => {
    return currentPage === page ||
      (page === 'dashboard' && currentPage === 'incident-detail') ||
      (page === 'infrastructure' && currentPage === 'host-detail') ||
      (page === 'errors' && currentPage === 'error-detail') ||
      (page === 'alerts' && currentPage === 'alert-detail')
  }

  // Get favorites items sorted by order
  const favoriteItems = React.useMemo(() => {
    return preferences.sidebar_favorites_order
      .map(id => NAV_ITEMS_MAP[id])
      .filter(Boolean);
  }, [preferences.sidebar_favorites_order]);

  // Get non-favorite items
  const nonFavoriteItems = React.useMemo(() => {
    return ALL_NAV_ITEMS.filter(item => !isFavorite(item.id));
  }, [preferences.sidebar_favorites, isFavorite]);

  // Render a favorite nav item with star and reorder controls
  const renderFavoriteItem = (item: NavItem, index: number) => {
    const Icon = item.icon
    const isActive = isPageActive(item.page)
    const isHovered = hoveredItem === `fav-${item.id}`
    const isFirst = index === 0
    const isLast = index === favoriteItems.length - 1

    return (
      <SidebarMenuItem key={`fav-${item.id}`}>
        <div
          className="relative flex items-center"
          onMouseEnter={() => setHoveredItem(`fav-${item.id}`)}
          onMouseLeave={() => setHoveredItem(null)}
        >
          <SidebarMenuButton
            tooltip={item.label}
            isActive={isActive}
            onClick={() => handleNavClick(item.page)}
            className={`flex-1 text-sm transition-colors ${isActive ? "text-sidebar-foreground bg-sidebar-accent border-l-2 border-l-white" : "text-muted-foreground hover:text-sidebar-foreground hover:bg-sidebar-accent"}`}
          >
            <Icon className={`size-4 ${isActive ? 'text-foreground' : 'text-muted-foreground'}`} />
            <span className="flex-1">{item.label}</span>
          </SidebarMenuButton>

          {/* Hover controls: remove from favorites + reorder */}
          {isHovered && !isCollapsed && (
            <div className="absolute right-1 flex items-center gap-0.5 bg-sidebar-accent rounded px-1">
              {!isFirst && (
                <button
                  onClick={(e) => { e.stopPropagation(); moveFavoriteUp(item.id); }}
                  className="p-0.5 text-muted-foreground hover:text-foreground"
                  title="Move up"
                >
                  <ChevronUp className="size-3" />
                </button>
              )}
              {!isLast && (
                <button
                  onClick={(e) => { e.stopPropagation(); moveFavoriteDown(item.id); }}
                  className="p-0.5 text-muted-foreground hover:text-foreground"
                  title="Move down"
                >
                  <ChevronDown className="size-3" />
                </button>
              )}
              <button
                onClick={(e) => { e.stopPropagation(); removeFromFavorites(item.id); }}
                className="p-0.5 text-yellow-500 hover:text-yellow-400"
                title="Remove from favorites"
              >
                <Star className="size-3 fill-current" />
              </button>
            </div>
          )}
        </div>
      </SidebarMenuItem>
    )
  }

  // Render a non-favorite nav item with add-to-favorites star on hover
  const renderNonFavoriteItem = (item: NavItem) => {
    const Icon = item.icon
    const isActive = isPageActive(item.page)
    const isHovered = hoveredItem === `all-${item.id}`

    return (
      <SidebarMenuItem key={`all-${item.id}`}>
        <div
          className="relative flex items-center"
          onMouseEnter={() => setHoveredItem(`all-${item.id}`)}
          onMouseLeave={() => setHoveredItem(null)}
        >
          <SidebarMenuButton
            tooltip={item.label}
            isActive={isActive}
            onClick={() => handleNavClick(item.page)}
            className={`flex-1 text-sm transition-colors ${isActive ? "text-sidebar-foreground bg-sidebar-accent border-l-2 border-l-white" : "text-muted-foreground hover:text-sidebar-foreground hover:bg-sidebar-accent"}`}
          >
            <Icon className={`size-4 ${isActive ? 'text-foreground' : 'text-muted-foreground'}`} />
            <span className="flex-1">{item.label}</span>
          </SidebarMenuButton>

          {/* Hover control: add to favorites */}
          {isHovered && !isCollapsed && (
            <button
              onClick={(e) => { e.stopPropagation(); addToFavorites(item.id); }}
              className="absolute right-1 p-0.5 text-muted-foreground hover:text-yellow-500"
              title="Add to favorites"
            >
              <StarOff className="size-3" />
            </button>
          )}
        </div>
      </SidebarMenuItem>
    )
  }

  // Settings items
  const settingsItems: NavItem[] = [
    { id: 'settings', label: 'Settings', icon: Settings, page: 'settings' },
  ]

  return (
    <Sidebar collapsible="icon" className="border-r border-sidebar-border bg-sidebar">
      {/* Header with Logo */}
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              size="lg"
              className="hover:bg-sidebar-accent"
              onClick={() => onNavigate('dashboard')}
            >
              <img
                src="/logo-small.png?v=4"
                alt="OffCall AI"
                className="size-10 rounded-lg"
                onError={(e) => {
                  e.currentTarget.style.display = 'none'
                }}
              />
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate text-base font-medium text-foreground">OffCall AI</span>
                <span className="truncate text-xs text-muted-foreground">
                  Incident Response
                </span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
          {/* Collapse Toggle */}
          <SidebarMenuItem>
            <SidebarMenuButton
              tooltip={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              onClick={toggleSidebar}
              className="hidden md:flex text-muted-foreground hover:text-sidebar-foreground hover:bg-sidebar-accent"
            >
              {isCollapsed ? (
                <PanelLeft className="size-4" />
              ) : (
                <PanelLeftClose className="size-4" />
              )}
              <span>{isCollapsed ? "Expand" : "Collapse"}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      {/* Navigation Content */}
      <SidebarContent>
        {/* MY FAVORITES Section */}
        <SidebarGroup>
          <SidebarGroupLabel className="text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-2">
            <Star className="size-3 text-yellow-500" />
            My Favorites
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {favoriteItems.length > 0 ? (
                favoriteItems.map((item, index) => renderFavoriteItem(item, index))
              ) : (
                <SidebarMenuItem>
                  <div className="px-3 py-2 text-xs text-muted-foreground italic">
                    Hover over items below and click the star to add favorites
                  </div>
                </SidebarMenuItem>
              )}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {/* ALL FEATURES Section (Collapsible) */}
        <SidebarGroup>
          <Collapsible
            open={preferences.all_features_expanded}
            onOpenChange={toggleAllFeaturesExpanded}
            className="group/collapsible"
          >
            <CollapsibleTrigger asChild>
              <SidebarGroupLabel className="text-xs uppercase tracking-wider text-muted-foreground cursor-pointer hover:text-foreground flex items-center justify-between pr-2">
                <span>All Features</span>
                <ChevronRight className="size-3 transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
              </SidebarGroupLabel>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <SidebarGroupContent>
                <SidebarMenu>
                  {nonFavoriteItems.map(renderNonFavoriteItem)}
                </SidebarMenu>
              </SidebarGroupContent>
            </CollapsibleContent>
          </Collapsible>
        </SidebarGroup>

        {/* Settings */}
        <SidebarGroup>
          <SidebarGroupLabel className="text-xs uppercase tracking-wider text-muted-foreground">Settings</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {settingsItems.map((item) => {
                const Icon = item.icon
                const isActive = isPageActive(item.page)
                return (
                  <SidebarMenuItem key={item.id}>
                    <SidebarMenuButton
                      tooltip={item.label}
                      isActive={isActive}
                      onClick={() => handleNavClick(item.page)}
                      className={`text-sm transition-colors ${isActive ? "text-sidebar-foreground bg-sidebar-accent border-l-2 border-l-white" : "text-muted-foreground hover:text-sidebar-foreground hover:bg-sidebar-accent"}`}
                    >
                      <Icon className={`size-4 ${isActive ? 'text-foreground' : 'text-muted-foreground'}`} />
                      <span>{item.label}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                )
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      {/* Footer with User Menu */}
      <SidebarFooter>
        <SidebarMenu>
          {/* Notifications */}
          <SidebarMenuItem>
            <SidebarMenuButton
              tooltip="Notifications"
              onClick={() => onToggleNotifications ? onToggleNotifications() : onNavigate('notifications')}
              className="text-sm text-muted-foreground hover:text-sidebar-foreground hover:bg-sidebar-accent"
            >
              <div className="relative">
                <Bell className="size-4" />
                {unreadCount > 0 && (
                  <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-red-500" />
                )}
              </div>
              <span>Notifications</span>
              {unreadCount > 0 && (
                <span className="ml-auto inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500/10 px-1.5 text-xs font-medium text-red-400">
                  {unreadCount > 9 ? '9+' : unreadCount}
                </span>
              )}
            </SidebarMenuButton>
          </SidebarMenuItem>

          {/* User Menu */}
          <SidebarMenuItem>
            <div ref={userMenuRef} className="relative">
              <SidebarMenuButton
                size="lg"
                onClick={() => setUserMenuOpen(!userMenuOpen)}
                className="hover:bg-sidebar-accent"
              >
                <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-secondary text-foreground">
                  <span className="text-sm font-medium">
                    {user?.full_name?.charAt(0)?.toUpperCase() || 'U'}
                  </span>
                </div>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate text-sm font-medium text-foreground">{user?.full_name || 'User'}</span>
                  <span className="truncate text-xs text-muted-foreground">
                    {user?.email || ''}
                  </span>
                </div>
                <ChevronsUpDown className="ml-auto size-4 text-muted-foreground" />
              </SidebarMenuButton>

              {/* Simple popover user menu */}
              {userMenuOpen && (
                <div className="absolute bottom-full left-0 mb-1 w-full min-w-[200px] rounded-lg border border-border bg-popover shadow-elevation-2 p-1 z-50">
                  <div className="px-2 py-1.5">
                    <p className="text-sm font-medium text-foreground">{user?.full_name || 'User'}</p>
                    <p className="text-xs text-muted-foreground">{user?.email || ''}</p>
                  </div>
                  <div className="my-1 h-px bg-border" />
                  <button
                    onClick={() => { setUserMenuOpen(false); onNavigate('profile'); }}
                    className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-sidebar-accent transition-colors"
                  >
                    <Settings className="size-4" />
                    Profile Settings
                  </button>
                  <div className="my-1 h-px bg-border" />
                  <button
                    onClick={() => { setUserMenuOpen(false); onLogout(); }}
                    className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-red-400 hover:text-red-300 hover:bg-sidebar-accent transition-colors"
                  >
                    <LogOut className="size-4" />
                    Log out
                  </button>
                </div>
              )}
            </div>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>

      <SidebarRail />
    </Sidebar>
  )
}

export default AppSidebar
