# backend/app/main.py - FIXED: Use v1 api_router instead of rebuilding it
import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, WebSocket, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from datetime import datetime
import time
from sqlalchemy import text
from app.api.v1 import api_router
from app.core.config import settings
from app.database import get_async_session
from opencensus.ext.azure.log_exporter import AzureLogHandler
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.trace.samplers import ProbabilitySampler
import logging

# Initialize Sentry SDK for error tracking (sends to OffCall test backend)
SENTRY_AVAILABLE = False
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    from sentry_sdk.integrations.asyncio import AsyncioIntegration

    # DSN format for OffCall: https://<api_key>@<host>/<numeric_project_id>
    # The Sentry SDK expects /api/{project_id}/envelope/ path format
    # Using a numeric project ID (0) and we'll set up route aliases
    OFFCALL_SENTRY_DSN = os.getenv("SENTRY_DSN", "")  # Disabled by default, set via env var

    # Only initialize if DSN is set and not empty
    if OFFCALL_SENTRY_DSN:
        sentry_sdk.init(
            dsn=OFFCALL_SENTRY_DSN,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                AsyncioIntegration(),
            ],
            # Send 100% of errors
            sample_rate=1.0,
            # Send 10% of transactions for performance monitoring
            traces_sample_rate=0.1,
            # Set environment
            environment=os.getenv("ENVIRONMENT", "production"),
            # Release version
            release="offcall-backend@2.0.0",
            # Don't send PII
            send_default_pii=False,
            # Attach stacktrace to messages
            attach_stacktrace=True,
        )
        SENTRY_AVAILABLE = True
        print("✅ Sentry SDK initialized")
    else:
        print("ℹ️ Sentry SDK available but not configured (set SENTRY_DSN to enable)")
except ImportError as e:
    print(f"⚠️ Sentry SDK not available: {e}")

# Import background workers
try:
    from app.background.worker import (
        escalation_worker,
        alert_rule_evaluation_worker,
        host_status_worker,
        metrics_aggregation_worker,
        database_monitoring_worker
    )
    BACKGROUND_WORKERS_AVAILABLE = True
    print("✅ Background workers loaded")
except ImportError as e:
    BACKGROUND_WORKERS_AVAILABLE = False
    print(f"⚠️ Background workers not available: {e}")

# SECURITY: Import security middleware
try:
    from app.middleware.security import SecurityMiddleware, setup_security_middleware
    SECURITY_MIDDLEWARE_AVAILABLE = True
    print("✅ Security middleware loaded")
except ImportError as e:
    SECURITY_MIDDLEWARE_AVAILABLE = False
    print(f"⚠️ Security middleware not available: {e}")

# SECURITY: Import input sanitization middleware
try:
    from app.middleware.input_sanitization import InputSanitizationMiddleware
    INPUT_SANITIZATION_AVAILABLE = True
    print("✅ Input sanitization middleware loaded")
except ImportError as e:
    INPUT_SANITIZATION_AVAILABLE = False
    print(f"⚠️ Input sanitization middleware not available: {e}")

# Import additional endpoints for feature checks
INCIDENTS_AVAILABLE = False
WEBHOOKS_AVAILABLE = False
TEAMS_AVAILABLE = False
SLACK_AVAILABLE = False
INTEGRATIONS_AVAILABLE = False
ORGANIZATIONS_AVAILABLE = False

try:
    from app.api.v1.endpoints import incidents
    INCIDENTS_AVAILABLE = True
    print("✅ Incidents endpoints loaded")
except ImportError as e:
    print(f"⚠️ Incidents endpoints not available: {e}")

try:
    from app.api.v1.endpoints import webhooks
    WEBHOOKS_AVAILABLE = True
    print("✅ Webhooks endpoints loaded")
except ImportError as e:
    print(f"⚠️ Webhooks endpoints not available: {e}")

try:
    from app.api.v1.endpoints import teams
    TEAMS_AVAILABLE = True
    print("✅ Teams endpoints loaded")
except ImportError as e:
    print(f"⚠️ Teams endpoints not available: {e}")

try:
    from app.api.v1.endpoints import slack
    SLACK_AVAILABLE = True
    print("✅ Slack endpoints loaded")
except ImportError as e:
    print(f"⚠️ Slack endpoints not available: {e}")

try:
    from app.api.v1.endpoints import organizations
    ORGANIZATIONS_AVAILABLE = True
    print("✅ Organizations endpoints loaded")
except ImportError as e:
    print(f"⚠️ Organizations endpoints not available: {e}")

try:
    from app.api.v1.endpoints import integrations
    INTEGRATIONS_AVAILABLE = True
    print("✅ Integrations endpoints loaded")
except ImportError as e:
    print(f"⚠️ Integrations endpoints not available: {e}")

# Import security components with error handling
SECURITY_AVAILABLE = False
ENHANCED_SECURITY_AVAILABLE = False

try:
    from app.api.v1.endpoints import security
    SECURITY_AVAILABLE = True
    print("✅ Security endpoints available")
except ImportError as e:
    print(f"⚠️ Security endpoints not found: {e}")

try:
    from app.core.enhanced_security import security_logger, rate_limiter
    ENHANCED_SECURITY_AVAILABLE = True
    print("✅ Enhanced security available")
except ImportError as e:
    print(f"⚠️ Enhanced security not available: {e}")

# WebSocket support
WEBSOCKET_AVAILABLE = False
try:
    from app.api.v1.endpoints.websocket_notifications import router as websocket_router
    WEBSOCKET_AVAILABLE = True
    print("✅ WebSocket notifications available")
except ImportError as e:
    print(f"⚠️ WebSocket notifications not available: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    print("🚀 OffCall AI starting up...")
    
    if not settings.SECRET_KEY or settings.SECRET_KEY == "your-secret-key":
        print("❌ CRITICAL: SECRET_KEY not properly configured!")
        
    if settings.DEBUG and settings.ENVIRONMENT == "production":
        print("⚠️ WARNING: DEBUG=true in production environment!")
    
    print("✅ FastAPI application initialized")

    print("✅ Database connections ready")

    # Ensure ClickHouse tables exist
    if settings.CLICKHOUSE_ENABLED:
        try:
            from app.services.clickhouse_service import clickhouse_service
            await clickhouse_service.ensure_tables()
            print("✅ ClickHouse tables verified")
        except Exception as e:
            print(f"⚠️ ClickHouse table setup: {e}")
    
    if ENHANCED_SECURITY_AVAILABLE:
        print("✅ Enhanced security features enabled")
    else:
        print("⚠️ Running with basic security")
    
    features = []
    if ENHANCED_SECURITY_AVAILABLE:
        features.append("🛡️ Enhanced Security")
    
    if WEBSOCKET_AVAILABLE:
        features.append("🔗 WebSocket Notifications")
    
    if INTEGRATIONS_AVAILABLE:
        features.append("🔌 Integration Management")

    if SENTRY_AVAILABLE:
        features.append("🐛 Sentry Error Tracking (OffCall)")

    if features:
        print("🎯 Active Features:")
        for feature in features:
            print(f"   {feature}")

    # Start background workers
    background_tasks = []
    if BACKGROUND_WORKERS_AVAILABLE:
        print("🔄 Starting background workers...")
        background_tasks = [
            asyncio.create_task(escalation_worker()),
            asyncio.create_task(alert_rule_evaluation_worker()),
            asyncio.create_task(host_status_worker()),
            asyncio.create_task(metrics_aggregation_worker()),
            asyncio.create_task(database_monitoring_worker()),
        ]
        print("   - Escalation worker (every 5 min)")
        print("   - Alert rule evaluation (every 60 sec)")
        print("   - Host status check (every 2 min)")
        print("   - Metrics cleanup (every 1 hour)")
        print("   - Metrics aggregation (every 15 min)")
        print("   - Database monitoring (every 60 sec)")
        print("✅ Background workers started")

    yield

    # Shutdown - cancel background tasks
    if background_tasks:
        print("🛑 Stopping background workers...")
        for task in background_tasks:
            task.cancel()
        await asyncio.gather(*background_tasks, return_exceptions=True)

    print("🛑 OffCall AI shutting down...")

# Create FastAPI app
app = FastAPI(
    title="OffCall AI - Enterprise Edition",
    description="AI-powered incident response with enterprise SSO and security",
    version="2.0.0",
    lifespan=lifespan
)

if settings.AZURE_APP_INSIGHTS_CONNECTION_STRING:
    # Setup logging to Azure
    logger = logging.getLogger(__name__)
    logger.addHandler(AzureLogHandler(
        connection_string=settings.AZURE_APP_INSIGHTS_CONNECTION_STRING
    ))
    logger.setLevel(logging.INFO)
    
    # Log startup
    logger.info("OffCallAI backend started - Azure monitoring active")
    
# Optional: trace this backend with OffCall's own Python SDK.
# Install it first:  pip install ./sdk/python
OFFCALL_TRACING_AVAILABLE = False
try:
    from offcall_errors.integrations.fastapi import OffCallFastAPI
    OFFCALL_APM_KEY = os.getenv("OFFCALL_APM_API_KEY", "")
    if OFFCALL_APM_KEY:
        OffCallFastAPI(
            app,
            api_key=OFFCALL_APM_KEY,
            environment=settings.ENVIRONMENT,
            release="offcall-backend@2.0.0",
            service="offcall-backend",
            enable_tracing=True,
            traces_endpoint=os.getenv("OFFCALL_TRACES_ENDPOINT", "http://localhost:8000/api/v1/traces/ingest"),
            traces_sample_rate=float(os.getenv("OFFCALL_TRACES_SAMPLE_RATE", "0.5")),
            debug=settings.DEBUG,
        )
        OFFCALL_TRACING_AVAILABLE = True
        print("✅ OffCall APM tracing initialized")
    else:
        print("ℹ️ OffCall APM tracing not configured (set OFFCALL_APM_API_KEY to enable)")
except ImportError:
    pass
except Exception as e:
    print(f"⚠️ OffCall APM tracing not available: {e}")

# Remove docs routes in production
if not settings.DEBUG:
    routes_to_remove = []
    for route in app.routes:
        if hasattr(route, 'path') and route.path in ['/docs', '/redoc', '/openapi.json']:
            routes_to_remove.append(route)
    
    for route in routes_to_remove:
        app.routes.remove(route)

# SECURITY: Add trusted host middleware — driven by settings
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS
)

# SECURITY: Enhanced security headers middleware
@app.middleware("http")
async def enhanced_security_headers(request: Request, call_next):
    start_time = time.time()
    
    response = await call_next(request)
    
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"

    # Content Security Policy — driven by settings
    api_host = settings.API_URL.replace('https://', '').replace('http://', '')
    csp_directives = [
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data: https:",
        f"connect-src 'self' {settings.API_URL} {settings.FRONTEND_URL} wss://{api_host}",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
    ]
    response.headers["Content-Security-Policy"] = "; ".join(csp_directives)
    
    response.headers["X-Security-Level"] = "enterprise" if ENHANCED_SECURITY_AVAILABLE else "basic"
    
    if not request.url.path.startswith("/static"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    
    if not request.url.path.startswith("/api/v1/ws/"):
        if response.status_code < 300:
            status_color = "🟢"
        elif response.status_code < 400:
            status_color = "🟡"
        else:
            status_color = "🔴"
            
        print(f"{status_color} {request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")
    
    return response

# CORS middleware — single source of truth
print(f"🔧 CORS origins configured: {settings.CORS_ORIGINS}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"]
)

# SECURITY: Add input sanitization middleware
if INPUT_SANITIZATION_AVAILABLE:
    app.add_middleware(InputSanitizationMiddleware)
    print("✅ Input sanitization middleware enabled")

# CRITICAL FIX: Include the v1 api_router which has ALL routes registered
app.include_router(api_router, prefix="/api/v1")
print("✅ All API v1 routes registered")

# Register WebSocket endpoint directly (doesn't work through APIRouter)
if WEBSOCKET_AVAILABLE:
    from app.api.v1.endpoints.websocket_notifications import websocket_notifications_endpoint, manager

    @app.websocket("/api/v1/ws/notifications")
    async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
        await websocket_notifications_endpoint(websocket, token)

    print("✅ WebSocket endpoint registered at /api/v1/ws/notifications")

# Database health check function
async def check_db_health():
    """Enhanced database health check"""
    try:
        async for session in get_async_session():
            try:
                await session.execute(text("SELECT 1"))

                tables_query = text("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                """)
                result = await session.execute(tables_query)
                tables = [row[0] for row in result.fetchall()]
                
                return {
                    "status": "healthy",
                    "database": "postgresql",
                    "tables_count": len(tables),
                    "critical_tables": {
                        "users": "users" in tables,
                        "organizations": "organizations" in tables,
                        "incidents": "incidents" in tables,
                        "integrations": "integrations" in tables,
                        "teams": "teams" in tables,
                        "ai_ready": True
                    }
                }
            finally:
                await session.close()
            
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with feature overview"""
    
    if settings.DEBUG:
        return {
            "message": "OffCall AI",
            "version": "2.0.0",
            "status": "operational",
            "security_level": "enterprise" if ENHANCED_SECURITY_AVAILABLE else "basic",
            "features": {
                "enhanced_security": ENHANCED_SECURITY_AVAILABLE,
                "real_time_notifications": WEBSOCKET_AVAILABLE,
                "multi_factor_auth": ENHANCED_SECURITY_AVAILABLE,
                "enterprise_ready": ENHANCED_SECURITY_AVAILABLE,
                "integrations": INTEGRATIONS_AVAILABLE
            },
            "documentation": "/docs",
            "endpoints": {
                "auth": "/api/v1/auth",
                "incidents": "/api/v1/incidents",
                "api_keys": "/api/v1/api_keys",
                "integrations": "/api/v1/integrations" if INTEGRATIONS_AVAILABLE else "not_available",
                "health": "/health"
            }
        }
    else:
        return {
            "message": "OffCall AI API",
            "status": "operational",
            "version": "2.0.0"
        }

# Health check
@app.get("/health")
async def health_check():
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0"
    }
    
    try:
        db_status = await check_db_health()
        health_status["database"] = db_status
    except Exception as e:
        health_status["database"] = {"status": "unhealthy", "error": str(e)}
    
    return health_status

# Test database connection
@app.get("/test-db")
async def test_db():
    """Test database connectivity with detailed info"""
    try:
        db_status = await check_db_health()
        if db_status["status"] == "healthy":
            return {"status": "success", "message": "Database connection successful", "details": db_status}
        else:
            return {"status": "error", "message": "Database connection failed", "details": db_status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database test failed: {str(e)}")

# Error handlers — CORSMiddleware already adds CORS headers to all responses
# Do NOT manually add CORS headers here as it causes duplicate header values

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    if settings.DEBUG:
        error_detail = str(exc)
    else:
        error_detail = "Internal server error"

    response = JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": error_detail,
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": getattr(request.state, "request_id", "unknown")
        }
    )
    return response

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    # Don't intercept WebSocket connection attempts
    if request.headers.get("upgrade") == "websocket":
        raise exc

    return JSONResponse(
        status_code=404,
        content={
            "error": "Not found",
            "message": "The requested resource was not found",
            "timestamp": datetime.utcnow().isoformat(),
            "suggestion": "Check API documentation" if settings.DEBUG else None
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"❌ Global exception on {request.method} {request.url}: {exc}")

    # Capture exception with Sentry if available
    if SENTRY_AVAILABLE:
        sentry_sdk.capture_exception(exc)

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "path": str(request.url.path)}
    )


# Test endpoint to verify Sentry integration
@app.get("/debug-sentry")
async def debug_sentry():
    """Trigger a test error to verify Sentry integration."""
    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="Not found")

    if SENTRY_AVAILABLE:
        try:
            # This will be captured by Sentry
            division_by_zero = 1 / 0
        except Exception as e:
            sentry_sdk.capture_exception(e)
            return {"status": "error_captured", "message": "Test error sent to Sentry/OffCall"}

    return {"status": "sentry_not_available", "message": "Sentry SDK not initialized"}


# =============================================================================
# Sentry SDK Compatibility Routes
# =============================================================================
# These routes support the standard Sentry SDK DSN format:
# DSN: https://<api_key>@<host>/<project_id>
# SDK sends to: /api/<project_id>/envelope/ and /api/<project_id>/store/
# =============================================================================

from app.api.v1.endpoints.sentry_ingest import (
    ingest_sentry_envelope,
    ingest_sentry_store,
    sentry_envelope_options,
    sentry_store_options,
)

# Import database dependency for Sentry routes
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

# Mount Sentry-compatible routes at /api/{project_id}/ (standard Sentry SDK path)
@app.post("/api/{project_id}/envelope/")
async def sentry_envelope_compat(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Sentry SDK envelope endpoint (standard path)."""
    x_sentry_auth = request.headers.get("X-Sentry-Auth")
    authorization = request.headers.get("Authorization")

    return await ingest_sentry_envelope(
        project_id=project_id,
        request=request,
        x_sentry_auth=x_sentry_auth,
        authorization=authorization,
        db=db,
    )

@app.post("/api/{project_id}/store/")
async def sentry_store_compat(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Sentry SDK store endpoint (standard path)."""
    x_sentry_auth = request.headers.get("X-Sentry-Auth")
    authorization = request.headers.get("Authorization")

    return await ingest_sentry_store(
        project_id=project_id,
        request=request,
        x_sentry_auth=x_sentry_auth,
        authorization=authorization,
        db=db,
    )

@app.options("/api/{project_id}/envelope/")
async def sentry_envelope_options_compat(project_id: str):
    """CORS preflight for Sentry envelope endpoint."""
    return await sentry_envelope_options(project_id)

@app.options("/api/{project_id}/store/")
async def sentry_store_options_compat(project_id: str):
    """CORS preflight for Sentry store endpoint."""
    return await sentry_store_options(project_id)

print("✅ Sentry SDK compatible routes registered at /api/{project_id}/envelope/ and /api/{project_id}/store/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"
    )