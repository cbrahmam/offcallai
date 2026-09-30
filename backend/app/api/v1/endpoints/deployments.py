# backend/app/api/v1/endpoints/deployments.py
"""
Deployment Tracking API Endpoints

Provides endpoints for CI/CD integration and deployment correlation.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from app.database import get_async_session
from app.core.security import get_current_user
from app.models.user import User
from app.services.deployment_tracking_service import DeploymentTrackingService
from app.schemas.deployment import (
    DeploymentNotify, DeploymentUpdate, DeploymentResponse,
    DeploymentListResponse, DeploymentCorrelation, DeploymentTimeline,
    DeploymentFilters, DeploymentStatus
)
import logging
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================
# CI/CD Webhook Endpoints (API Key Auth)
# ============================================

@router.post("/notify", response_model=DeploymentResponse)
async def notify_deployment(
    deployment_data: DeploymentNotify,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Notify of a deployment from CI/CD system.

    This endpoint is called by CI/CD systems (GitHub Actions, Jenkins, etc.)
    to record deployments. The deployment will be automatically correlated
    with any incidents/alerts that occur within 30 minutes.

    Example CI/CD integration (GitHub Actions):
    ```yaml
    - name: Notify OffCall AI
      run: |
        curl -X POST $OFFCALL_API_URL/api/v1/deployments/notify \\
          -H "Authorization: Bearer ${{ secrets.OFFCALL_API_KEY }}" \\
          -H "Content-Type: application/json" \\
          -d '{
            "service_name": "api-service",
            "version": "${{ github.sha }}",
            "environment": "production",
            "commit_sha": "${{ github.sha }}",
            "branch": "${{ github.ref_name }}",
            "repository": "${{ github.repository }}",
            "deployed_by": "${{ github.actor }}"
          }'
    ```
    """
    try:
        service = DeploymentTrackingService(db)
        deployment = await service.record_deployment(
            organization_id=current_user.organization_id,
            deployment_data=deployment_data
        )

        return DeploymentResponse(
            id=deployment.id,
            organization_id=deployment.organization_id,
            service_name=deployment.service_name,
            version=deployment.version,
            environment=deployment.environment,
            deployed_by=deployment.deployed_by,
            deployed_at=deployment.deployed_at,
            commit_sha=deployment.commit_sha,
            commit_message=deployment.commit_message,
            branch=deployment.branch,
            repository=deployment.repository,
            pull_request_url=deployment.pull_request_url,
            pull_request_number=deployment.pull_request_number,
            status=DeploymentStatus(deployment.status.value),
            duration_seconds=deployment.duration_seconds,
            rollback_of=deployment.rollback_of,
            incidents_within_30min=deployment.incidents_within_30min or 0,
            alerts_within_30min=deployment.alerts_within_30min or 0,
            correlated_incident_ids=deployment.correlated_incident_ids or [],
            correlated_alert_ids=deployment.correlated_alert_ids or [],
            tags=deployment.tags or {},
            extra_data=deployment.extra_data or {},
            description=deployment.description,
            created_at=deployment.created_at,
            updated_at=deployment.updated_at
        )
    except Exception as e:
        logger.error(f"Error recording deployment: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to record deployment: {str(e)}")


# ============================================
# Dashboard Endpoints (JWT Auth)
# ============================================

@router.get("/", response_model=DeploymentListResponse)
async def list_deployments(
    service_name: Optional[str] = Query(None, description="Filter by service name"),
    environment: Optional[str] = Query(None, description="Filter by environment"),
    status: Optional[DeploymentStatus] = Query(None, description="Filter by status"),
    branch: Optional[str] = Query(None, description="Filter by branch"),
    deployed_by: Optional[str] = Query(None, description="Filter by deployer"),
    date_from: Optional[datetime] = Query(None, description="Filter from date"),
    date_to: Optional[datetime] = Query(None, description="Filter to date"),
    has_incidents: Optional[bool] = Query(None, description="Filter by incident correlation"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """List deployments with filtering and pagination."""
    try:
        service = DeploymentTrackingService(db)

        filters = DeploymentFilters(
            service_name=service_name,
            environment=environment,
            status=status,
            branch=branch,
            deployed_by=deployed_by,
            date_from=date_from,
            date_to=date_to,
            has_incidents=has_incidents
        )

        return await service.list_deployments(
            organization_id=current_user.organization_id,
            filters=filters,
            page=page,
            per_page=per_page
        )
    except Exception as e:
        logger.error(f"Error listing deployments: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve deployments")


@router.get("/timeline", response_model=DeploymentTimeline)
async def get_deployment_timeline(
    hours: int = Query(24, ge=1, le=720, description="Time range in hours"),
    service_name: Optional[str] = Query(None, description="Filter by service"),
    environment: Optional[str] = Query(None, description="Filter by environment"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get deployment timeline with incident markers.

    Returns a list of deployments in the specified time range,
    with indicators for which deployments had incidents/alerts
    within 30 minutes of deployment.
    """
    try:
        service = DeploymentTrackingService(db)
        return await service.get_deployment_timeline(
            organization_id=current_user.organization_id,
            hours=hours,
            service_name=service_name,
            environment=environment
        )
    except Exception as e:
        logger.error(f"Error getting deployment timeline: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve deployment timeline")


@router.get("/stats")
async def get_deployment_stats(
    days: int = Query(30, ge=1, le=365, description="Period in days"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get deployment statistics for dashboard.

    Returns:
    - Total deployments
    - Status breakdown (success, failed, etc.)
    - Deployments with incidents
    - Top deployed services
    - Daily deployment counts
    """
    try:
        service = DeploymentTrackingService(db)
        return await service.get_deployment_stats(
            organization_id=current_user.organization_id,
            days=days
        )
    except Exception as e:
        logger.error(f"Error getting deployment stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve deployment stats")


@router.get("/{deployment_id}", response_model=DeploymentResponse)
async def get_deployment(
    deployment_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get a specific deployment by ID."""
    try:
        service = DeploymentTrackingService(db)
        deployment = await service.get_deployment(
            deployment_id=deployment_id,
            organization_id=current_user.organization_id
        )

        if not deployment:
            raise HTTPException(status_code=404, detail="Deployment not found")

        return DeploymentResponse(
            id=deployment.id,
            organization_id=deployment.organization_id,
            service_name=deployment.service_name,
            version=deployment.version,
            environment=deployment.environment,
            deployed_by=deployment.deployed_by,
            deployed_at=deployment.deployed_at,
            commit_sha=deployment.commit_sha,
            commit_message=deployment.commit_message,
            branch=deployment.branch,
            repository=deployment.repository,
            pull_request_url=deployment.pull_request_url,
            pull_request_number=deployment.pull_request_number,
            status=DeploymentStatus(deployment.status.value),
            duration_seconds=deployment.duration_seconds,
            rollback_of=deployment.rollback_of,
            incidents_within_30min=deployment.incidents_within_30min or 0,
            alerts_within_30min=deployment.alerts_within_30min or 0,
            correlated_incident_ids=deployment.correlated_incident_ids or [],
            correlated_alert_ids=deployment.correlated_alert_ids or [],
            tags=deployment.tags or {},
            extra_data=deployment.extra_data or {},
            description=deployment.description,
            created_at=deployment.created_at,
            updated_at=deployment.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving deployment {deployment_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve deployment")


@router.get("/{deployment_id}/correlation", response_model=DeploymentCorrelation)
async def get_deployment_correlation(
    deployment_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get deployment correlation with incidents and alerts.

    Returns detailed information about which incidents and alerts
    occurred within 30 minutes of the deployment.
    """
    try:
        service = DeploymentTrackingService(db)
        correlation = await service.get_deployment_correlation(
            deployment_id=deployment_id,
            organization_id=current_user.organization_id
        )

        if not correlation:
            raise HTTPException(status_code=404, detail="Deployment not found")

        return correlation
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting deployment correlation {deployment_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve deployment correlation")


@router.patch("/{deployment_id}", response_model=DeploymentResponse)
async def update_deployment(
    deployment_id: UUID,
    update_data: DeploymentUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Update a deployment status.

    Used to mark deployments as failed, rolling back, or rolled back.
    """
    try:
        service = DeploymentTrackingService(db)
        deployment = await service.update_deployment(
            deployment_id=deployment_id,
            organization_id=current_user.organization_id,
            update_data=update_data
        )

        if not deployment:
            raise HTTPException(status_code=404, detail="Deployment not found")

        return DeploymentResponse(
            id=deployment.id,
            organization_id=deployment.organization_id,
            service_name=deployment.service_name,
            version=deployment.version,
            environment=deployment.environment,
            deployed_by=deployment.deployed_by,
            deployed_at=deployment.deployed_at,
            commit_sha=deployment.commit_sha,
            commit_message=deployment.commit_message,
            branch=deployment.branch,
            repository=deployment.repository,
            pull_request_url=deployment.pull_request_url,
            pull_request_number=deployment.pull_request_number,
            status=DeploymentStatus(deployment.status.value),
            duration_seconds=deployment.duration_seconds,
            rollback_of=deployment.rollback_of,
            incidents_within_30min=deployment.incidents_within_30min or 0,
            alerts_within_30min=deployment.alerts_within_30min or 0,
            correlated_incident_ids=deployment.correlated_incident_ids or [],
            correlated_alert_ids=deployment.correlated_alert_ids or [],
            tags=deployment.tags or {},
            extra_data=deployment.extra_data or {},
            description=deployment.description,
            created_at=deployment.created_at,
            updated_at=deployment.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating deployment {deployment_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update deployment")


@router.post("/{deployment_id}/correlate")
async def trigger_correlation(
    deployment_id: UUID,
    window_minutes: int = Query(30, ge=5, le=120, description="Correlation window in minutes"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Manually trigger correlation for a deployment.

    Use this to re-run correlation after incidents have been resolved
    or to use a different time window.
    """
    try:
        service = DeploymentTrackingService(db)
        result = await service.correlate_with_incidents(
            deployment_id=deployment_id,
            organization_id=current_user.organization_id,
            window_minutes=window_minutes
        )

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error correlating deployment {deployment_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to correlate deployment")


# ============================================
# Incident-centric Endpoints
# ============================================

@router.get("/for-incident/{incident_id}")
async def get_deployments_for_incident(
    incident_id: UUID,
    window_minutes: int = Query(30, ge=5, le=120, description="Time window in minutes"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Find deployments that occurred near an incident.

    This is useful for root cause analysis - given an incident,
    find which deployments might have caused it.
    """
    try:
        service = DeploymentTrackingService(db)
        deployments = await service.find_deployments_for_incident(
            incident_id=incident_id,
            organization_id=current_user.organization_id,
            window_minutes=window_minutes
        )

        return {
            "incident_id": str(incident_id),
            "window_minutes": window_minutes,
            "deployments": [
                {
                    "id": str(d.id),
                    "service_name": d.service_name,
                    "version": d.version,
                    "environment": d.environment,
                    "deployed_at": d.deployed_at.isoformat() if d.deployed_at else None,
                    "deployed_by": d.deployed_by,
                    "commit_sha": d.commit_sha,
                    "branch": d.branch,
                    "status": d.status.value
                }
                for d in deployments
            ]
        }
    except Exception as e:
        logger.error(f"Error finding deployments for incident {incident_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to find deployments for incident"
        )
