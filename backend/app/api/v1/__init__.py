# backend/app/api/v1/__init__.py
from fastapi import APIRouter

# Import only guaranteed modules
from app.api.v1.endpoints import auth
from app.api.v1.endpoints import admin

api_router = APIRouter()

# Always register these
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])

# Conditionally import and register others
try:
    from app.api.v1.endpoints import incidents
    api_router.include_router(incidents.router, prefix="/incidents", tags=["incidents"])
    print("✅ Incidents router registered: /api/v1/incidents/")
except ImportError:
    pass

try:
    from app.api.v1.endpoints import webhooks
    api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
except ImportError:
    pass

try:
    from app.api.v1.endpoints import ai_chat
    api_router.include_router(ai_chat.router, prefix="/incidents", tags=["ai-chat"])
    print("✅ AI Chat router registered: /api/v1/incidents/{id}/chat/")
except ImportError as e:
    print(f"⚠️ AI Chat router not available: {e}")
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f"❌ AI Chat router FAILED: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

try:
    from app.api.v1.endpoints import api_keys
    api_router.include_router(api_keys.router, prefix="/api_keys", tags=["api_keys"])
    print("✅ API Keys router registered: /api/v1/api_keys/")
except Exception as e:
    print(f"❌ API Keys router FAILED: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

try:
    from app.api.v1.endpoints import users
    api_router.include_router(users.router, prefix="/users", tags=["users"])
except ImportError:
    pass

try:
    from app.api.v1.endpoints import organizations
    api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
except ImportError:
    pass

try:
    from app.api.v1.endpoints import integrations
    api_router.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
except ImportError:
    pass

try:
    from app.api.v1.endpoints import notifications
    api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
except ImportError:
    pass

try:
    from app.api.v1.endpoints import slack
    api_router.include_router(slack.router, prefix="/slack", tags=["slack"])
    print("✅ Slack router registered: /api/v1/slack/")
except (ImportError, AttributeError) as e:
    print(f"⚠️ Slack router not available: {e}")

try:
    from app.api.v1.endpoints import alerts
    api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
    print("✅ Alerts CRUD router registered: /api/v1/alerts/")
except ImportError as e:
    print(f"⚠️ Alerts router not available: {e}")

try:
    from app.api.v1.endpoints import alert_enrichment
    api_router.include_router(
        alert_enrichment.router, 
        prefix="/alerts",
        tags=["alert-enrichment"]
    )
    print("✅ Alert enrichment router registered: /api/v1/alerts/")
except ImportError as e:
    print(f"⚠️ Alert enrichment router not available: {e}")

try:
    from app.api.v1.endpoints import websocket_notifications
    api_router.include_router(websocket_notifications.router, tags=["websocket"])
    print("✅ WebSocket router registered: /api/v1/ws/notifications")
except ImportError as e:
    print(f"⚠️ WebSocket router not available: {e}")
except Exception as e:
    print(f"⚠️ WebSocket router error: {e}")

try:
    from app.api.v1.endpoints import runbooks
    api_router.include_router(runbooks.router, prefix="/runbooks", tags=["runbooks"])
    print("✅ Runbooks router registered: /api/v1/runbooks/")
except ImportError as e:
    print(f"⚠️ Runbooks router not available: {e}")
except Exception as e:
    print(f"❌ Runbooks router error: {e}")
    import traceback
    traceback.print_exc()

try:
    from app.api.v1.endpoints import on_call_schedules
    api_router.include_router(on_call_schedules.router, prefix="/on-call-schedules", tags=["on-call-schedules"])
    print("✅ On-Call Schedules router registered: /api/v1/on-call-schedules/")
except ImportError as e:
    print(f"⚠️ On-Call Schedules router not available: {e}")
except Exception as e:
    print(f"❌ On-Call Schedules router error: {e}")
    import traceback
    traceback.print_exc()

try:
    from app.api.v1.endpoints import maintenance_windows
    api_router.include_router(maintenance_windows.router, prefix="/maintenance-windows", tags=["maintenance-windows"])
    print("✅ Maintenance Windows router registered: /api/v1/maintenance-windows/")
except ImportError as e:
    print(f"⚠️ Maintenance Windows router not available: {e}")
except Exception as e:
    print(f"❌ Maintenance Windows router error: {e}")
    import traceback
    traceback.print_exc()

try:
    from app.api.v1.endpoints import post_mortems
    api_router.include_router(post_mortems.router, prefix="/post-mortems", tags=["post-mortems"])
    print("✅ Post-Mortems router registered: /api/v1/post-mortems/")
except ImportError as e:
    print(f"⚠️ Post-Mortems router not available: {e}")
except Exception as e:
    print(f"❌ Post-Mortems router error: {e}")
    import traceback
    traceback.print_exc()

try:
    from app.api.v1.endpoints import status_pages
    api_router.include_router(status_pages.router, prefix="/status-pages", tags=["status-pages"])
    print("✅ Status Pages router registered: /api/v1/status-pages/")
except ImportError as e:
    print(f"⚠️ Status Pages router not available: {e}")
except Exception as e:
    print(f"❌ Status Pages router error: {e}")
    import traceback
    traceback.print_exc()

try:
    from app.api.v1.endpoints import analytics
    api_router.include_router(analytics.router, tags=["analytics"])
    print("✅ Analytics router registered: /api/v1/analytics/")
except ImportError as e:
    print(f"⚠️ Analytics router not available: {e}")
except Exception as e:
    print(f"❌ Analytics router error: {e}")
    import traceback
    traceback.print_exc()

try:
    from app.api.v1.endpoints import services
    api_router.include_router(services.router, tags=["services"])
    print("✅ Services router registered: /api/v1/services/")
except ImportError as e:
    print(f"⚠️ Services router not available: {e}")
except Exception as e:
    print(f"❌ Services router error: {e}")
    import traceback
    traceback.print_exc()

try:
    from app.api.v1.endpoints import slos
    api_router.include_router(slos.router, tags=["slos"])
    print("✅ SLOs router registered: /api/v1/slos/")
except ImportError as e:
    print(f"⚠️ SLOs router not available: {e}")
except Exception as e:
    print(f"❌ SLOs router error: {e}")
    import traceback
    traceback.print_exc()

try:
    from app.api.v1.endpoints import calendar
    api_router.include_router(calendar.router, tags=["calendar"])
    print("✅ Calendar router registered: /api/v1/calendar/")
except ImportError as e:
    print(f"⚠️ Calendar router not available: {e}")
except Exception as e:
    print(f"❌ Calendar router error: {e}")
    import traceback
    traceback.print_exc()

try:
    from app.api.v1.endpoints import slack_commands
    api_router.include_router(slack_commands.router, tags=["slack-commands"])
    print("✅ Slack Commands router registered: /api/v1/slack/commands/")
except ImportError as e:
    print(f"⚠️ Slack Commands router not available: {e}")
except Exception as e:
    print(f"❌ Slack Commands router error: {e}")
    import traceback
    traceback.print_exc()

# ============================================
# Monitoring Infrastructure (Metrics Pivot)
# ============================================

try:
    from app.api.v1.endpoints import hosts
    api_router.include_router(hosts.router, prefix="/hosts", tags=["hosts", "infrastructure"])
    print("✅ Hosts router registered: /api/v1/hosts/")
except ImportError as e:
    print(f"⚠️ Hosts router not available: {e}")
except Exception as e:
    print(f"❌ Hosts router error: {e}")
    import traceback
    traceback.print_exc()

try:
    from app.api.v1.endpoints import metrics
    api_router.include_router(metrics.router, prefix="/metrics", tags=["metrics", "infrastructure"])
    print("✅ Metrics router registered: /api/v1/metrics/")
except ImportError as e:
    print(f"⚠️ Metrics router not available: {e}")
except Exception as e:
    print(f"❌ Metrics router error: {e}")
    import traceback
    traceback.print_exc()

# Logs and Traces
try:
    from app.api.v1.endpoints import logs
    api_router.include_router(logs.router, prefix="/logs", tags=["logs", "observability"])
    print("✅ Logs router registered: /api/v1/logs/")
except ImportError as e:
    print(f"⚠️ Logs router not available: {e}")
except Exception as e:
    print(f"❌ Logs router error: {e}")
    import traceback
    traceback.print_exc()

try:
    from app.api.v1.endpoints import traces
    api_router.include_router(traces.router, prefix="/traces", tags=["traces", "observability"])
    print("✅ Traces router registered: /api/v1/traces/")
except ImportError as e:
    print(f"⚠️ Traces router not available: {e}")
except Exception as e:
    print(f"❌ Traces router error: {e}")
    import traceback
    traceback.print_exc()

# Alert Rules
try:
    from app.api.v1.endpoints import alert_rules
    api_router.include_router(alert_rules.router, prefix="/alert-rules", tags=["alert-rules", "monitoring"])
    print("✅ Alert Rules router registered: /api/v1/alert-rules/")
except ImportError as e:
    print(f"⚠️ Alert Rules router not available: {e}")
except Exception as e:
    print(f"❌ Alert Rules router error: {e}")
    import traceback
    traceback.print_exc()

# Dashboards
try:
    from app.api.v1.endpoints import dashboards
    api_router.include_router(dashboards.router, prefix="/dashboards", tags=["dashboards", "observability"])
    print("✅ Dashboards router registered: /api/v1/dashboards/")
except ImportError as e:
    print(f"⚠️ Dashboards router not available: {e}")
except Exception as e:
    print(f"❌ Dashboards router error: {e}")
    import traceback
    traceback.print_exc()

# Anomaly Detection
try:
    from app.api.v1.endpoints import anomalies
    api_router.include_router(anomalies.router, prefix="/anomalies", tags=["anomalies", "ml"])
    print("✅ Anomalies router registered: /api/v1/anomalies/")
except ImportError as e:
    print(f"⚠️ Anomalies router not available: {e}")
except Exception as e:
    print(f"❌ Anomalies router error: {e}")
    import traceback
    traceback.print_exc()

# Containers
try:
    from app.api.v1.endpoints import containers
    api_router.include_router(containers.router, prefix="/containers", tags=["containers", "infrastructure"])
    print("✅ Containers router registered: /api/v1/containers/")
except ImportError as e:
    print(f"⚠️ Containers router not available: {e}")
except Exception as e:
    print(f"❌ Containers router error: {e}")
    import traceback
    traceback.print_exc()

# Databases
try:
    from app.api.v1.endpoints import databases
    api_router.include_router(databases.router, prefix="/databases", tags=["databases", "infrastructure"])
    print("✅ Databases router registered: /api/v1/databases/")
except ImportError as e:
    print(f"⚠️ Databases router not available: {e}")
except Exception as e:
    print(f"❌ Databases router error: {e}")
    import traceback
    traceback.print_exc()

# Auto Remediation
try:
    from app.api.v1.endpoints import remediation
    api_router.include_router(remediation.router, prefix="/remediation", tags=["remediation", "automation"])
    print("✅ Remediation router registered: /api/v1/remediation/")
except ImportError as e:
    print(f"⚠️ Remediation router not available: {e}")
except Exception as e:
    print(f"❌ Remediation router error: {e}")
    import traceback
    traceback.print_exc()

# Synthetic Monitoring
try:
    from app.api.v1.endpoints import synthetic
    api_router.include_router(synthetic.router, prefix="/synthetic", tags=["synthetic", "monitoring"])
    print("✅ Synthetic router registered: /api/v1/synthetic/")
except ImportError as e:
    print(f"⚠️ Synthetic router not available: {e}")
except Exception as e:
    print(f"❌ Synthetic router error: {e}")
    import traceback
    traceback.print_exc()

# Network Monitoring
try:
    from app.api.v1.endpoints import network
    api_router.include_router(network.router, prefix="/network", tags=["network", "infrastructure"])
    print("✅ Network router registered: /api/v1/network/")
except ImportError as e:
    print(f"⚠️ Network router not available: {e}")
except Exception as e:
    print(f"❌ Network router error: {e}")
    import traceback
    traceback.print_exc()

# Real User Monitoring (RUM)
try:
    from app.api.v1.endpoints import rum
    api_router.include_router(rum.router, prefix="/rum", tags=["rum", "frontend-monitoring"])
    print("✅ RUM router registered: /api/v1/rum/")
except ImportError as e:
    print(f"⚠️ RUM router not available: {e}")
except Exception as e:
    print(f"❌ RUM router error: {e}")
    import traceback
    traceback.print_exc()

# Deployment Tracking
try:
    from app.api.v1.endpoints import deployments
    api_router.include_router(deployments.router, prefix="/deployments", tags=["deployments", "cicd"])
    print("✅ Deployments router registered: /api/v1/deployments/")
except ImportError as e:
    print(f"⚠️ Deployments router not available: {e}")
except Exception as e:
    print(f"❌ Deployments router error: {e}")
    import traceback
    traceback.print_exc()

# AI Root Cause Analysis
try:
    from app.api.v1.endpoints import ai_rca
    api_router.include_router(ai_rca.router, tags=["ai-rca", "analysis"])
    print("✅ AI RCA router registered: /api/v1/incidents/{id}/analyze")
except ImportError as e:
    print(f"⚠️ AI RCA router not available: {e}")
except Exception as e:
    print(f"❌ AI RCA router error: {e}")
    import traceback
    traceback.print_exc()

# Natural Language Queries
try:
    from app.api.v1.endpoints import nl_query
    api_router.include_router(nl_query.router, tags=["nl-query", "search"])
    print("✅ NL Query router registered: /api/v1/query")
except ImportError as e:
    print(f"⚠️ NL Query router not available: {e}")
except Exception as e:
    print(f"❌ NL Query router error: {e}")
    import traceback
    traceback.print_exc()

# Error Tracking
try:
    from app.api.v1.endpoints import errors
    api_router.include_router(errors.router, tags=["errors", "error-tracking"])
    print("✅ Error Tracking router registered: /api/v1/errors/")
except ImportError as e:
    print(f"⚠️ Error Tracking router not available: {e}")
except Exception as e:
    print(f"❌ Error Tracking router error: {e}")
    import traceback
    traceback.print_exc()

# Continuous Profiling
try:
    from app.api.v1.endpoints import profiles
    api_router.include_router(profiles.router, tags=["profiles", "profiling"])
    print("✅ Profiling router registered: /api/v1/profiles/")
except ImportError as e:
    print(f"⚠️ Profiling router not available: {e}")
except Exception as e:
    print(f"❌ Profiling router error: {e}")
    import traceback
    traceback.print_exc()

# Sentry SDK Compatibility
# This allows users to use official Sentry SDKs with OffCall AI
# by simply changing the DSN URL
try:
    from app.api.v1.endpoints import sentry_ingest
    api_router.include_router(sentry_ingest.router, prefix="/api", tags=["sentry-compat", "error-tracking"])
    print("✅ Sentry Compat router registered: /api/v1/api/sentry/{project_id}/envelope/")
except ImportError as e:
    print(f"⚠️ Sentry Compat router not available: {e}")
except Exception as e:
    print(f"❌ Sentry Compat router error: {e}")
    import traceback
    traceback.print_exc()

# AI-Powered Incident-Telemetry Correlation
# Uses Claude to intelligently find related traces and logs for incidents
try:
    from app.api.v1.endpoints import incident_correlation
    api_router.include_router(incident_correlation.router, tags=["correlation", "ai"])
    print("✅ Incident Correlation router registered: /api/v1/incidents/{id}/correlated-telemetry")
except ImportError as e:
    print(f"⚠️ Incident Correlation router not available: {e}")
except Exception as e:
    print(f"❌ Incident Correlation router error: {e}")
    import traceback
    traceback.print_exc()