// frontend/oncall-frontend/src/App.tsx

import React, { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { NotificationProvider, useNotifications } from './contexts/NotificationContext';
import AuthPages from './components/AuthPages';
import Dashboard from './components/Dashboard';
import SettingsPage from './components/SettingsPage';
import UserProfile from './components/UserProfile';
import NotificationCenter from './components/NotificationCenter';
import NotificationSettings from './components/NotificationSettings';
import IncidentDetail from './components/IncidentDetail';
import AdminDashboard from './components/AdminDashboard';
import SlackCallBack from './components/SlackCallBack';
import AIAnalysisDisplay from './components/AIAnalysisDisplay';
import AIDeploymentInterface from './components/AIDeploymentInterface';
import AlertDetail from './components/AlertDetail';
import RunbookManager from './components/RunbookManager';
import OnCallScheduleManager from './components/OnCallScheduleManager';
import MaintenanceWindowManager from './components/MaintenanceWindowManager';
import PostMortemManager from './components/PostMortemManager';
import StatusPageManager from './components/StatusPageManager';
import PublicStatusPage from './components/PublicStatusPage';
import AnalyticsDashboard from './components/AnalyticsDashboard';
import Infrastructure from './components/Infrastructure';
import HostDetail from './components/HostDetail';
import AlertRulesManager from './components/AlertRulesManager';
import AlertsPage from './components/AlertsPage';
import IncidentsPage from './components/IncidentsPage';
import LogViewer from './components/LogViewer';
import APMViewer from './components/APMViewer';
import AnomalyDetection from './components/AnomalyDetection';
import ContainerMonitoring from './components/ContainerMonitoring';
import DatabaseMonitoring from './components/DatabaseMonitoring';
import SyntheticMonitoring from './components/SyntheticMonitoring';
import NetworkMonitoring from './components/NetworkMonitoring';
import BrowserRUM from './components/BrowserRUM';
import { SidebarProvider, SidebarInset, SidebarTrigger } from './components/ui/sidebar';
import AppSidebar from './components/AppSidebar';
import { ThemeProvider } from './hooks/use-theme';
import ErrorBoundary from './components/ErrorBoundary';
import ServiceDependencyMap from './components/ServiceDependencyMap';
import DeploymentTimeline from './components/DeploymentTimeline';
import CostAttributionDashboard from './components/CostAttributionDashboard';
import ErrorTrackingDashboard from './components/ErrorTrackingDashboard';
import ErrorGroupDetail from './components/ErrorGroupDetail';
import ProfilingDashboard from './components/ProfilingDashboard';
import ForgotPassword from './components/ForgotPassword';
import ResetPassword from './components/ResetPassword';

type Page =
  | 'auth' | 'forgot-password' | 'reset-password'
  | 'dashboard' | 'settings' | 'profile' | 'notifications' | 'admin'
  | 'incidents' | 'incident-detail' | 'alerts' | 'alert-detail' | 'alert-rules'
  | 'ai-analysis' | 'ai-deployment'
  | 'runbooks' | 'on-call-schedules' | 'maintenance-windows' | 'post-mortems'
  | 'status-page' | 'public-status' | 'analytics'
  | 'infrastructure' | 'host-detail' | 'logs' | 'apm' | 'service-map'
  | 'deployments' | 'cost-attribution' | 'anomaly-detection'
  | 'containers' | 'databases' | 'synthetic' | 'network' | 'rum'
  | 'errors' | 'error-detail' | 'profiling'
  | 'slack-callback';

/** Pages reachable without being logged in. */
const PUBLIC_PAGES: Page[] = ['auth', 'forgot-password', 'reset-password', 'public-status'];

/** Path prefix for each page, used for both parsing and pushState. */
const PAGE_PATHS: Partial<Record<Page, string>> = {
  auth: '/login',
  'forgot-password': '/forgot-password',
  'reset-password': '/reset-password',
  dashboard: '/dashboard',
  settings: '/settings',
  profile: '/profile',
  notifications: '/notifications',
  admin: '/admin',
  incidents: '/incidents',
  alerts: '/alerts',
  'alert-rules': '/alert-rules',
  'ai-analysis': '/ai-analysis',
  'ai-deployment': '/ai-deployment',
  runbooks: '/runbooks',
  'on-call-schedules': '/on-call-schedules',
  'maintenance-windows': '/maintenance-windows',
  'post-mortems': '/post-mortems',
  'status-page': '/status-page',
  analytics: '/analytics',
  infrastructure: '/infrastructure',
  logs: '/logs',
  apm: '/apm',
  'service-map': '/service-map',
  deployments: '/deployments',
  'cost-attribution': '/cost-attribution',
  'anomaly-detection': '/anomaly-detection',
  containers: '/containers',
  databases: '/databases',
  synthetic: '/synthetic',
  network: '/network',
  rum: '/rum',
  errors: '/errors',
  profiling: '/profiling',
  'slack-callback': '/settings/integrations/slack/callback',
};

/** Routes carrying a resource id in the path. */
const ID_ROUTES: { page: Page; pattern: RegExp }[] = [
  { page: 'incident-detail', pattern: /^\/incidents\/([a-zA-Z0-9-]+)/ },
  { page: 'alert-detail', pattern: /^\/alerts\/([a-zA-Z0-9-]+)/ },
  { page: 'host-detail', pattern: /^\/hosts\/([a-zA-Z0-9-]+)/ },
  { page: 'error-detail', pattern: /^\/errors\/([a-zA-Z0-9-]+)/ },
  { page: 'public-status', pattern: /^\/status\/([a-zA-Z0-9-]+)/ },
];

type Resolved = { page: Page; id?: string };

/**
 * Map a browser path to a page (plus a resource id where the route carries one).
 * Longest-prefix wins so that e.g. /alert-rules is not swallowed by /alerts.
 */
const resolvePath = (path: string): Resolved => {
  for (const { page, pattern } of ID_ROUTES) {
    const match = path.match(pattern);
    if (match) return { page, id: match[1] };
  }

  const entries = Object.entries(PAGE_PATHS) as [Page, string][];
  const hit = entries
    .filter(([, prefix]) => path === prefix || path.startsWith(`${prefix}/`) || path.startsWith(`${prefix}?`))
    .sort((a, b) => b[1].length - a[1].length)[0];
  if (hit) return { page: hit[0] };

  // Legacy aliases
  if (path.startsWith('/app')) return { page: 'dashboard' };
  if (path.startsWith('/auth') || path.startsWith('/register')) return { page: 'auth' };

  return { page: 'dashboard' };
};

const AppContent: React.FC = () => {
  const { isAuthenticated, isLoading, user, logout } = useAuth();
  const { unreadCount } = useNotifications();
  const [currentPage, setCurrentPage] = useState<Page>('dashboard');
  const [currentIncidentId, setCurrentIncidentId] = useState<string | null>(null);
  const [showNotificationCenter, setShowNotificationCenter] = useState(false);
  const [currentAlertId, setCurrentAlertId] = useState<string | null>(null);
  const [currentStatusSlug, setCurrentStatusSlug] = useState<string | null>(null);
  const [currentHostId, setCurrentHostId] = useState<string | null>(null);
  const [currentErrorGroupId, setCurrentErrorGroupId] = useState<string | null>(null);
  const [pendingRedirect, setPendingRedirect] = useState<string | null>(null);

  const [aiAnalysisData, setAiAnalysisData] = useState<{
    incidentId: string;
    provider?: 'claude' | 'gemini';
    solution?: any;
  } | null>(null);

  // Validate redirect URL to prevent open redirect attacks
  const isValidRedirectUrl = (url: string): boolean => {
    if (!url) return false;
    if (!url.startsWith('/')) return false;
    if (url.startsWith('//')) return false;

    const lowerUrl = url.toLowerCase();
    // eslint-disable-next-line no-script-url
    const DENIED_SCHEMES = ['javascript:', 'data:'];
    if (DENIED_SCHEMES.some((scheme) => lowerUrl.includes(scheme))) return false;

    if (url.includes('%')) {
      try {
        const decoded = decodeURIComponent(url);
        const lowerDecoded = decoded.toLowerCase();
        if (decoded.startsWith('//') || DENIED_SCHEMES.some((scheme) => lowerDecoded.includes(scheme))) {
          return false;
        }
      } catch {
        return false;
      }
    }

    return true;
  };

  // Apply a resolved route to component state
  const applyResolved = ({ page, id }: Resolved) => {
    setCurrentIncidentId(page === 'incident-detail' ? id ?? null : null);
    setCurrentAlertId(page === 'alert-detail' ? id ?? null : null);
    setCurrentHostId(page === 'host-detail' ? id ?? null : null);
    setCurrentErrorGroupId(page === 'error-detail' ? id ?? null : null);
    if (page === 'public-status') setCurrentStatusSlug(id ?? null);
    setCurrentPage(page);
  };

  // Check for pending redirect URL on mount
  useEffect(() => {
    const storedRedirect = sessionStorage.getItem('auth_redirect_url');
    if (storedRedirect && isValidRedirectUrl(storedRedirect)) {
      setPendingRedirect(storedRedirect);
    } else if (storedRedirect) {
      sessionStorage.removeItem('auth_redirect_url');
    }
  }, []);

  // Handle redirect after authentication
  useEffect(() => {
    if (isAuthenticated && user && pendingRedirect) {
      sessionStorage.removeItem('auth_redirect_url');
      const redirectUrl = pendingRedirect;
      setPendingRedirect(null);
      window.history.replaceState(null, '', redirectUrl);
      applyResolved(resolvePath(redirectUrl));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, user, pendingRedirect]);

  // Resolve the initial route, then follow browser back/forward
  const hasInitializedRouting = React.useRef(false);
  useEffect(() => {
    if (hasInitializedRouting.current) return;
    hasInitializedRouting.current = true;

    applyResolved(resolvePath(window.location.pathname));

    const handlePopState = () => applyResolved(resolvePath(window.location.pathname));
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const navigate = (page: Page, id?: string) => {
    applyResolved({ page, id });

    let url: string;
    if (page === 'incident-detail' && id) url = `/incidents/${id}`;
    else if (page === 'alert-detail' && id) url = `/alerts/${id}`;
    else if (page === 'host-detail' && id) url = `/hosts/${id}`;
    else if (page === 'error-detail' && id) url = `/errors/${id}`;
    else if (page === 'public-status' && id) url = `/status/${id}`;
    else url = PAGE_PATHS[page] ?? `/${page}`;

    window.history.pushState(null, '', url);
  };

  const handleShowAIAnalysis = (incidentId: string) => {
    setAiAnalysisData({ incidentId });
    setCurrentPage('ai-analysis');
  };

  const handleAIDeploymentSelect = (provider: 'claude' | 'gemini', solution: any) => {
    if (aiAnalysisData) {
      setAiAnalysisData({ ...aiAnalysisData, provider, solution });
      setCurrentPage('ai-deployment');
    }
  };

  const handleDeploymentComplete = (success: boolean, deploymentId?: string) => {
    if (aiAnalysisData?.incidentId) {
      navigate('incident-detail', aiAnalysisData.incidentId);
    } else {
      navigate('dashboard');
    }
  };

  const handleAICancel = () => {
    if (aiAnalysisData?.incidentId) {
      navigate('incident-detail', aiAnalysisData.incidentId);
    } else {
      navigate('dashboard');
    }
    setAiAnalysisData(null);
  };

  // Page content rendered inside the sidebar layout
  const renderSidebarPageContent = () => {
    switch (currentPage) {
      case 'dashboard':
        return <Dashboard onShowAIAnalysis={handleShowAIAnalysis} onNavigateToIncident={(incidentId: string) => navigate('incident-detail', incidentId)} />;
      case 'settings':
        return <SettingsPage />;
      case 'runbooks':
        return <RunbookManager />;
      case 'on-call-schedules':
        return <OnCallScheduleManager />;
      case 'maintenance-windows':
        return <MaintenanceWindowManager />;
      case 'post-mortems':
        return <PostMortemManager />;
      case 'status-page':
        return <StatusPageManager />;
      case 'analytics':
        return <AnalyticsDashboard />;
      case 'infrastructure':
        return <Infrastructure onNavigateToHost={(hostId: string) => navigate('host-detail', hostId)} />;
      case 'host-detail':
        return currentHostId ? <HostDetail hostId={currentHostId} onBack={() => navigate('infrastructure')} /> : null;
      case 'alerts':
        return <AlertsPage onNavigateToAlert={(alertId) => navigate('alert-detail', alertId)} onNavigateToIncident={(incidentId) => navigate('incident-detail', incidentId)} />;
      case 'incidents':
        return <IncidentsPage onNavigateToIncident={(incidentId) => navigate('incident-detail', incidentId)} />;
      case 'alert-rules':
        return <AlertRulesManager />;
      case 'logs':
        return <LogViewer />;
      case 'apm':
        return <APMViewer />;
      case 'service-map':
        return <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8"><ServiceDependencyMap onServiceClick={(serviceName) => console.log('Service clicked:', serviceName)} /></div>;
      case 'deployments':
        return <DeploymentTimeline />;
      case 'cost-attribution':
        return <CostAttributionDashboard />;
      case 'anomaly-detection':
        return <AnomalyDetection />;
      case 'containers':
        return <ContainerMonitoring />;
      case 'databases':
        return <DatabaseMonitoring />;
      case 'synthetic':
        return <SyntheticMonitoring />;
      case 'network':
        return <NetworkMonitoring />;
      case 'rum':
        return <BrowserRUM />;
      case 'errors':
        return <ErrorTrackingDashboard onNavigateToGroup={(groupId: string) => navigate('error-detail', groupId)} />;
      case 'error-detail':
        return currentErrorGroupId ? <ErrorGroupDetail groupId={currentErrorGroupId} onBack={() => navigate('errors')} /> : null;
      case 'profiling':
        return <ProfilingDashboard />;
      case 'profile':
        return <UserProfile />;
      case 'notifications':
        return <NotificationSettings />;
      case 'admin':
        return <AdminDashboard />;
      case 'incident-detail':
        return currentIncidentId ? <IncidentDetail incidentId={currentIncidentId} onShowAIAnalysis={handleShowAIAnalysis} onBack={() => navigate('dashboard')} /> : null;
      case 'alert-detail':
        return currentAlertId ? <AlertDetail alertId={currentAlertId} onBack={() => navigate('dashboard')} /> : null;
      case 'ai-analysis':
        return aiAnalysisData ? <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8"><AIAnalysisDisplay incidentId={aiAnalysisData.incidentId} onDeploymentSelect={handleAIDeploymentSelect} /></div> : null;
      case 'ai-deployment':
        return aiAnalysisData?.provider && aiAnalysisData?.solution ? <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8"><AIDeploymentInterface incidentId={aiAnalysisData.incidentId} provider={aiAnalysisData.provider} solution={aiAnalysisData.solution} onDeploymentComplete={handleDeploymentComplete} onCancel={handleAICancel} /></div> : null;
      default:
        return <Dashboard onShowAIAnalysis={handleShowAIAnalysis} onNavigateToIncident={(incidentId: string) => navigate('incident-detail', incidentId)} />;
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex flex-col items-center space-y-4">
          <div className="w-12 h-12 bg-primary rounded-xl flex items-center justify-center animate-pulse">
            <svg className="w-8 h-8 text-primary-foreground" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
            </svg>
          </div>
          <p className="text-muted-foreground">Loading OffCall AI...</p>
        </div>
      </div>
    );
  }

  const renderCurrentPage = () => {
    // Public pages, no authentication required
    if (currentPage === 'public-status' && currentStatusSlug) {
      return <PublicStatusPage slug={currentStatusSlug} />;
    }

    if (currentPage === 'forgot-password') {
      return <ForgotPassword onNavigateToLogin={() => navigate('auth')} />;
    }

    if (currentPage === 'reset-password') {
      return <ResetPassword onNavigateToLogin={() => navigate('auth')} />;
    }

    if (currentPage === 'slack-callback') {
      return <SlackCallBack />;
    }

    // Everything else requires a session
    if (!isAuthenticated) {
      const currentPath = window.location.pathname;
      const isAuthPath = PUBLIC_PAGES.some((p) => currentPath.startsWith(PAGE_PATHS[p] ?? ''));
      if (currentPath && currentPath !== '/' && !isAuthPath && isValidRedirectUrl(currentPath)) {
        sessionStorage.setItem('auth_redirect_url', currentPath);
      }
      return (
        <AuthPages
          key="auth"
          onLoginSuccess={() => navigate('dashboard')}
          defaultMode="login"
        />
      );
    }

    if (currentPage === 'auth') {
      // Already signed in — send them to the dashboard instead of the login form
      return (
        <SidebarProvider>
          <AppSidebar
            currentPage="dashboard"
            onNavigate={(page) => navigate(page as Page)}
            user={user}
            onLogout={logout}
            unreadCount={unreadCount}
            onToggleNotifications={() => setShowNotificationCenter(!showNotificationCenter)}
          />
          <SidebarInset>
            <main className="flex-1 overflow-auto bg-background">
              <Dashboard onShowAIAnalysis={handleShowAIAnalysis} onNavigateToIncident={(incidentId: string) => navigate('incident-detail', incidentId)} />
            </main>
          </SidebarInset>
        </SidebarProvider>
      );
    }

    // All authenticated pages share a single stable SidebarProvider
    return (
      <SidebarProvider>
        <AppSidebar
          currentPage={currentPage}
          onNavigate={(page) => navigate(page as Page)}
          user={user}
          onLogout={logout}
          unreadCount={unreadCount}
          onToggleNotifications={() => setShowNotificationCenter(!showNotificationCenter)}
        />
        <SidebarInset>
          <header className="flex h-14 items-center gap-2 border-b border-border px-4 md:hidden">
            <SidebarTrigger className="-ml-1 text-muted-foreground hover:text-foreground" />
            <span className="text-[15px] font-medium text-foreground">OffCall AI</span>
          </header>
          <main className="flex-1 overflow-auto bg-background">
            {renderSidebarPageContent()}
          </main>
        </SidebarInset>
        {showNotificationCenter && (
          <NotificationCenter
            isOpen={showNotificationCenter}
            onClose={() => setShowNotificationCenter(false)}
          />
        )}
      </SidebarProvider>
    );
  };

  return <div className="App">{renderCurrentPage()}</div>;
};

const App: React.FC = () => {
  return (
    <ThemeProvider defaultTheme="dark" storageKey="offcall-ui-theme">
      <ErrorBoundary>
        <AuthProvider>
          <NotificationProvider>
            <AppContent />
          </NotificationProvider>
        </AuthProvider>
      </ErrorBoundary>
    </ThemeProvider>
  );
};

export default App;
