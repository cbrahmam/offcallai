# backend/app/api/v1/endpoints/alerts.py

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, case, select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.database import get_async_session
from app.core.security import get_current_user
from app.models.alert import Alert
from app.models.alert_enrichment import AlertEnrichment
from app.models.api_keys import APIKey
from app.models.user import User
from app.services.alert_service import AlertService
from app.schemas.alert import (
    AlertResponse, AlertCreate, AlertUpdate, AlertListResponse,
    AlertStatus, AlertSeverity, AlertSource
)
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/", response_model=AlertListResponse)
async def list_alerts(
    status: Optional[AlertStatus] = Query(None, description="Filter by alert status"),
    severity: Optional[AlertSeverity] = Query(None, description="Filter by alert severity"), 
    service: Optional[str] = Query(None, description="Filter by service name"),
    environment: Optional[str] = Query(None, description="Filter by environment"),
    source: Optional[AlertSource] = Query(None, description="Filter by alert source"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """List alerts with filtering and pagination"""
    
    try:
        alert_service = AlertService(db)
        return await alert_service.list_alerts(
            organization_id=current_user.organization_id,
            status=status,
            severity=severity,
            service=service,
            environment=environment,
            source=source.value if source else None,
            page=page,
            per_page=per_page
        )
    except Exception as e:
        logger.error(f"Error listing alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve alerts")

@router.post("/", response_model=AlertResponse)
async def create_alert(
    alert_data: AlertCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Create a new alert"""
    
    try:
        alert_service = AlertService(db)
        return await alert_service.create_alert(alert_data, current_user.organization_id)
        
    except Exception as e:
        logger.error(f"Error creating alert: {e}")
        raise HTTPException(status_code=500, detail="Failed to create alert")

@router.get("/statistics/summary")
async def get_alert_statistics(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get alert statistics and insights"""
    
    try:
        alert_service = AlertService(db)
        return await alert_service.get_alert_statistics(
            organization_id=current_user.organization_id,
            days=days
        )
        
    except Exception as e:
        logger.error(f"Error generating alert statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate statistics")

@router.get("/health-check")
async def alert_system_health():
    """Health check for the alert ingestion system"""
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "alert_system_version": "2.0.0",
        "supported_sources": [
            "datadog", "grafana", "aws-cloudwatch", "new-relic", 
            "prometheus", "pagerduty", "generic"
        ],
        "features": [
            "deduplication", "auto-incident-creation", "flap-detection",
            "maintenance-windows", "multi-source-support"
        ]
    }

@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get a specific alert by ID"""
    
    try:
        alert_service = AlertService(db)
        alert = await alert_service.get_alert_by_id(alert_id, current_user.organization_id)
        
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return AlertResponse(
            id=str(alert.id),
            external_id=alert.external_id,
            fingerprint=alert.fingerprint,
            title=alert.title,
            description=alert.description,
            severity=alert.severity,
            status=alert.status,
            source=alert.source,
            service_name=alert.service_name,
            environment=alert.environment,
            host=alert.host,
            incident_id=str(alert.incident_id) if alert.incident_id else None,
            started_at=alert.started_at,
            ended_at=alert.ended_at,
            created_at=alert.created_at,
            updated_at=alert.updated_at,
            labels=alert.labels,
            raw_data=alert.raw_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve alert")

@router.patch("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: str,
    update_data: AlertUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update an existing alert"""
    
    try:
        alert_service = AlertService(db)
        alert = await alert_service.get_alert_by_id(alert_id, current_user.organization_id)
        
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        # Update fields
        if update_data.title is not None:
            alert.title = update_data.title
        if update_data.description is not None:
            alert.description = update_data.description
        if update_data.severity is not None:
            alert.severity = update_data.severity
        if update_data.status is not None:
            alert.status = update_data.status
        if update_data.service_name is not None:
            alert.service_name = update_data.service_name
        if update_data.environment is not None:
            alert.environment = update_data.environment
        if update_data.host is not None:
            alert.host = update_data.host
        if update_data.ended_at is not None:
            alert.ended_at = update_data.ended_at
        if update_data.labels is not None:
            alert.labels = update_data.labels
        
        alert.updated_at = datetime.utcnow()
        await db.commit()
        
        return AlertResponse(
            id=str(alert.id),
            external_id=alert.external_id,
            fingerprint=alert.fingerprint,
            title=alert.title,
            description=alert.description,
            severity=alert.severity,
            status=alert.status,
            source=alert.source,
            service_name=alert.service_name,
            environment=alert.environment,
            host=alert.host,
            incident_id=str(alert.incident_id) if alert.incident_id else None,
            started_at=alert.started_at,
            ended_at=alert.ended_at,
            created_at=alert.created_at,
            updated_at=alert.updated_at,
            labels=alert.labels,
            raw_data=alert.raw_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update alert")

@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Acknowledge an alert"""
    
    try:
        alert_service = AlertService(db)
        return await alert_service.acknowledge_alert(
            alert_id=alert_id,
            organization_id=current_user.organization_id,
            user_id=str(current_user.id)
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error acknowledging alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to acknowledge alert")

@router.post("/{alert_id}/suppress", response_model=AlertResponse)
async def suppress_alert(
    alert_id: str,
    reason: Optional[str] = Query(None, description="Reason for suppression"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Suppress an alert"""
    
    try:
        alert_service = AlertService(db)
        return await alert_service.suppress_alert(
            alert_id=alert_id,
            organization_id=current_user.organization_id,
            user_id=str(current_user.id),
            reason=reason
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error suppressing alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to suppress alert")

@router.post("/{alert_id}/chat")
async def chat_about_alert(
    alert_id: str,
    request: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Chat with AI about an alert - supports Claude, OpenAI, Gemini"""
    try:
        message = request.get("message", "")
        
        # Get alert and enrichment
        alert_result = await db.execute(
            select(Alert).where(
                and_(
                    Alert.id == alert_id,
                    Alert.organization_id == current_user.organization_id
                )
            )
        )
        alert = alert_result.scalar_one_or_none()
        if not alert:
            raise HTTPException(404, "Alert not found")
            
        enrichment_result = await db.execute(
            select(AlertEnrichment).where(AlertEnrichment.alert_id == alert_id)
        )
        enrichment = enrichment_result.scalar_one_or_none()
        
        # Get any valid API key (prefer Claude > OpenAI > Gemini)
        api_key_result = await db.execute(
            select(APIKey).where(
                APIKey.organization_id == current_user.organization_id,
                APIKey.is_valid == True
            ).order_by(
                case(
                    (APIKey.provider == "claude", 1),
                    (APIKey.provider == "openai", 2),
                    (APIKey.provider == "gemini", 3),
                    else_=4
                )
            ).limit(1)
        )
        api_key = api_key_result.scalar_one_or_none()
        
        if not api_key:
            raise HTTPException(400, "No valid AI API key configured. Please add one in Settings > API Keys")
        
        # Build context for AI
        context = f"""You are an expert SRE analyzing an alert. Here's the context:

Alert Details:
- Title: {alert.title}
- Service: {alert.service_name or 'unknown'}
- Severity: {alert.severity.value}
- Description: {alert.description or 'N/A'}
- Status: {alert.status.value}
- Started: {alert.started_at or alert.created_at}

{f'''Enrichment Data:
- Metrics: {json.dumps(enrichment.related_metrics, indent=2) if enrichment and enrichment.related_metrics else 'Not available'}
- Recent Error Logs: {json.dumps(enrichment.related_logs[:5] if enrichment and enrichment.related_logs else [], indent=2)}
- AI Severity Score: {enrichment.ai_severity_score if enrichment else 'Not calculated'}
- Correlation: {enrichment.correlation_reason if enrichment else 'N/A'}
''' if enrichment else 'Enrichment data not yet available. Run enrichment first.'}

User Question: {message}

Provide a clear, actionable response focusing on troubleshooting and resolution."""

        # Call AI service
        from app.services.real_ai_service import RealAIService
        ai_service = RealAIService(db)
        
        response_text = await ai_service.generate_response(
            provider=api_key.provider,
            prompt=context,
            api_key_id=str(api_key.id)
        )
        
        return {
            "response": response_text,
            "provider": api_key.provider,
            "alert_id": alert_id
        }
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(500, f"Chat failed: {str(e)}")
