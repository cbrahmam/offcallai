# backend/app/api/v1/endpoints/alert_enrichment.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from app.database import get_async_session
from app.models.user import User
from app.core.security import get_current_user
from app.services.alert_enrichment_service import AlertEnrichmentService

router = APIRouter()

# Schemas
class EnrichmentResponse(BaseModel):
    alert_id: str
    # Every field below can legitimately be absent: enrichment stores whatever
    # the individual steps managed to produce. These were declared as bare
    # `str = None`, which pydantic v2 rejects -- and because ValidationError
    # subclasses ValueError, the endpoint's `except ValueError` turned it into
    # a 404, so enrichment appeared to "not find" alerts that existed.
    related_metrics: dict = {}
    related_logs: list = []
    related_traces: list = []
    dashboard_url: Optional[str] = None
    logs_url: Optional[str] = None
    traces_url: Optional[str] = None
    runbook_url: Optional[str] = None
    correlated_alerts: List[str] = []
    correlation_score: float = 0.0
    correlation_reason: Optional[str] = ""
    ai_severity_score: float = 0.0
    severity_confidence: float = 0.0
    original_severity: Optional[str] = None
    adjusted_severity: Optional[str] = None
    severity_factors: dict = {}
    processing_time_ms: float = 0.0
    enriched_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class CorrelatedAlert(BaseModel):
    alert_id: str
    title: str
    service_name: str
    severity: str
    correlation_score: float
    started_at: datetime

class DrillDownLinks(BaseModel):
    dashboard_url: str = None
    logs_url: str = None
    traces_url: str = None
    runbook_url: str = None

@router.post("/{alert_id}/enrich", response_model=EnrichmentResponse)
async def enrich_alert(
    alert_id: str,
    force_refresh: bool = False,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Enrich an alert with context-rich data
    - Fetches metrics, logs, traces
    - Correlates with other alerts
    - Calculates smart severity score
    - Generates drill-down links
    """
    try:
        enrichment_service = AlertEnrichmentService(db)
        
        enrichment = await enrichment_service.enrich_alert(
            alert_id=alert_id,
            organization_id=str(current_user.organization_id),
            force_refresh=force_refresh
        )
        
        return EnrichmentResponse(
            alert_id=str(enrichment.alert_id),
            related_metrics=enrichment.related_metrics,
            related_logs=enrichment.related_logs,
            related_traces=enrichment.related_traces,
            dashboard_url=enrichment.dashboard_url,
            logs_url=enrichment.logs_url,
            traces_url=enrichment.traces_url,
            runbook_url=enrichment.runbook_url,
            correlated_alerts=enrichment.correlated_alert_ids,
            correlation_score=enrichment.correlation_score,
            correlation_reason=enrichment.correlation_reason,
            ai_severity_score=enrichment.ai_severity_score,
            severity_confidence=enrichment.severity_confidence,
            original_severity=enrichment.original_severity,
            adjusted_severity=enrichment.adjusted_severity,
            severity_factors=enrichment.severity_factors,
            processing_time_ms=enrichment.processing_time_ms,
            enriched_at=enrichment.enriched_at
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Enrichment failed: {str(e)}")

@router.get("/{alert_id}/enrichment", response_model=EnrichmentResponse)
async def get_alert_enrichment(
    alert_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get existing enrichment data for an alert"""
    from sqlalchemy import select, and_
    from app.models.alert_enrichment import AlertEnrichment
    
    try:
        result = await db.execute(
            select(AlertEnrichment).where(
                and_(
                    AlertEnrichment.alert_id == alert_id,
                    AlertEnrichment.organization_id == current_user.organization_id
                )
            )
        )
        enrichment = result.scalar_one_or_none()
        
        if not enrichment:
            raise HTTPException(status_code=404, detail="Enrichment data not found")
        
        return EnrichmentResponse(
            alert_id=str(enrichment.alert_id),
            related_metrics=enrichment.related_metrics,
            related_logs=enrichment.related_logs,
            related_traces=enrichment.related_traces,
            dashboard_url=enrichment.dashboard_url,
            logs_url=enrichment.logs_url,
            traces_url=enrichment.traces_url,
            runbook_url=enrichment.runbook_url,
            correlated_alerts=enrichment.correlated_alert_ids,
            correlation_score=enrichment.correlation_score,
            correlation_reason=enrichment.correlation_reason,
            ai_severity_score=enrichment.ai_severity_score,
            severity_confidence=enrichment.severity_confidence,
            original_severity=enrichment.original_severity,
            adjusted_severity=enrichment.adjusted_severity,
            severity_factors=enrichment.severity_factors,
            processing_time_ms=enrichment.processing_time_ms,
            enriched_at=enrichment.enriched_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching enrichment: {str(e)}")

@router.get("/{alert_id}/correlated-alerts", response_model=List[CorrelatedAlert])
async def get_correlated_alerts(
    alert_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get list of alerts correlated with this one"""
    from sqlalchemy import select, and_
    from app.models.alert_enrichment import AlertEnrichment
    from app.models.alert import Alert
    
    try:
        # Get enrichment data
        result = await db.execute(
            select(AlertEnrichment).where(
                and_(
                    AlertEnrichment.alert_id == alert_id,
                    AlertEnrichment.organization_id == current_user.organization_id
                )
            )
        )
        enrichment = result.scalar_one_or_none()
        
        if not enrichment or not enrichment.correlated_alert_ids:
            return []
        
        # Fetch correlated alerts
        result = await db.execute(
            select(Alert).where(
                Alert.id.in_(enrichment.correlated_alert_ids)
            )
        )
        correlated = result.scalars().all()
        
        return [
            CorrelatedAlert(
                alert_id=str(alert.id),
                title=alert.title,
                service_name=alert.service_name or "unknown",
                severity=alert.severity.value,
                correlation_score=0.8,  # Could store individual scores
                started_at=alert.started_at or alert.created_at
            )
            for alert in correlated
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching correlated alerts: {str(e)}")

@router.get("/{alert_id}/drill-down", response_model=DrillDownLinks)
async def get_drill_down_links(
    alert_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get one-click drill-down links for an alert"""
    from sqlalchemy import select, and_
    from app.models.alert_enrichment import AlertEnrichment
    
    try:
        result = await db.execute(
            select(AlertEnrichment).where(
                and_(
                    AlertEnrichment.alert_id == alert_id,
                    AlertEnrichment.organization_id == current_user.organization_id
                )
            )
        )
        enrichment = result.scalar_one_or_none()
        
        if not enrichment:
            # Generate links on-the-fly if enrichment doesn't exist
            from app.models.alert import Alert
            alert_result = await db.execute(
                select(Alert).where(Alert.id == alert_id)
            )
            alert = alert_result.scalar_one_or_none()
            
            if not alert:
                raise HTTPException(status_code=404, detail="Alert not found")
            
            service = AlertEnrichmentService(db)
            links = await service._build_drill_down_links(alert)
            
            return DrillDownLinks(**links)
        
        return DrillDownLinks(
            dashboard_url=enrichment.dashboard_url,
            logs_url=enrichment.logs_url,
            traces_url=enrichment.traces_url,
            runbook_url=enrichment.runbook_url
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching drill-down links: {str(e)}")

@router.post("/batch-enrich")
async def batch_enrich_alerts(
    alert_ids: List[str],
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Enrich multiple alerts in background
    Useful when incident has many alerts
    """
    enrichment_service = AlertEnrichmentService(db)
    
    # Queue enrichment tasks in background
    for alert_id in alert_ids:
        background_tasks.add_task(
            enrichment_service.enrich_alert,
            alert_id=alert_id,
            organization_id=str(current_user.organization_id),
            force_refresh=False
        )
    
    return {
        "message": f"Queued {len(alert_ids)} alerts for enrichment",
        "alert_ids": alert_ids
    }

# Correlation tuning endpoints
class CorrelationWeights(BaseModel):
    service: float = Field(0.35, ge=0, le=1)
    host: float = Field(0.25, ge=0, le=1)
    environment: float = Field(0.15, ge=0, le=1)
    title_similarity: float = Field(0.20, ge=0, le=1)
    severity: float = Field(0.05, ge=0, le=1)
    tags: float = Field(0.10, ge=0, le=1)
    temporal: float = Field(0.10, ge=0, le=1)
    error_pattern: float = Field(0.15, ge=0, le=1)

@router.get("/correlation/weights", response_model=CorrelationWeights)
async def get_correlation_weights(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get current correlation algorithm weights"""
    from app.services.correlation_engine import CorrelationEngine
    
    engine = CorrelationEngine(db)
    return CorrelationWeights(**engine.weights)

@router.post("/correlation/weights")
async def update_correlation_weights(
    weights: CorrelationWeights,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Update correlation algorithm weights
    Allows tuning based on feedback
    """
    from app.services.correlation_engine import CorrelationEngine
    
    engine = CorrelationEngine(db)
    engine.update_weights(weights.dict())
    
    return {
        "message": "Correlation weights updated successfully",
        "weights": engine.weights
    }

@router.get("/correlation/statistics")
async def get_correlation_statistics(
    days: int = Query(7, ge=1, le=30),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get correlation accuracy statistics
    Helps understand how well correlation is working
    """
    from app.services.correlation_engine import CorrelationEngine
    
    engine = CorrelationEngine(db)
    stats = await engine.get_correlation_statistics(
        organization_id=str(current_user.organization_id),
        days=days
    )
    
    return stats
