# backend/app/api/v1/endpoints/anomalies.py
"""
Anomaly Detection API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime
from uuid import UUID

from app.database import get_db
from app.services.anomaly_service import anomaly_service
from app.schemas.anomaly import (
    DetectorCreate, DetectorUpdate, DetectorResponse, DetectorListResponse,
    AnomalyResponse, AnomalyListResponse, AnomalySummary, DetectionResult,
    AnomalyAcknowledge, AnomalyFeedbackCreate
)
from app.api.deps import get_current_user, get_current_organization
from app.models.user import User
from app.models.organization import Organization

router = APIRouter()


# ============================================
# Detector CRUD
# ============================================

@router.post("/detectors", response_model=DetectorResponse)
async def create_detector(
    data: DetectorCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Create a new anomaly detector."""
    result = await anomaly_service.create_detector(
        data=data,
        organization_id=organization.id,
        db=db
    )
    return result


@router.get("/detectors", response_model=DetectorListResponse)
async def list_detectors(
    enabled_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """List all anomaly detectors."""
    result = await anomaly_service.list_detectors(
        organization_id=organization.id,
        db=db,
        enabled_only=enabled_only,
        limit=limit,
        offset=offset
    )
    return result


@router.get("/detectors/{detector_id}", response_model=DetectorResponse)
async def get_detector(
    detector_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get a detector by ID."""
    result = await anomaly_service.get_detector(
        detector_id=detector_id,
        organization_id=organization.id,
        db=db
    )
    if not result:
        raise HTTPException(status_code=404, detail="Detector not found")
    return result


@router.patch("/detectors/{detector_id}", response_model=DetectorResponse)
async def update_detector(
    detector_id: UUID,
    data: DetectorUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Update a detector."""
    result = await anomaly_service.update_detector(
        detector_id=detector_id,
        data=data,
        organization_id=organization.id,
        db=db
    )
    if not result:
        raise HTTPException(status_code=404, detail="Detector not found")
    return result


@router.delete("/detectors/{detector_id}")
async def delete_detector(
    detector_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Delete a detector."""
    success = await anomaly_service.delete_detector(
        detector_id=detector_id,
        organization_id=organization.id,
        db=db
    )
    if not success:
        raise HTTPException(status_code=404, detail="Detector not found")
    return {"message": "Detector deleted successfully"}


@router.post("/detectors/{detector_id}/toggle", response_model=DetectorResponse)
async def toggle_detector(
    detector_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Toggle detector enabled/disabled status."""
    detector = await anomaly_service.get_detector(detector_id, organization.id, db)
    if not detector:
        raise HTTPException(status_code=404, detail="Detector not found")

    from app.schemas.anomaly import DetectorUpdate
    result = await anomaly_service.update_detector(
        detector_id=detector_id,
        data=DetectorUpdate(enabled=not detector.enabled),
        organization_id=organization.id,
        db=db
    )
    return result


# ============================================
# Detection
# ============================================

@router.post("/detectors/{detector_id}/run", response_model=DetectionResult)
async def run_detection(
    detector_id: UUID,
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Run anomaly detection for a specific detector."""
    try:
        result = await anomaly_service.run_detection(
            detector_id=detector_id,
            organization_id=organization.id,
            db=db,
            start_time=start_time,
            end_time=end_time
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/run-all")
async def run_all_detectors(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Run all enabled detectors."""
    results = await anomaly_service.run_all_detectors(
        organization_id=organization.id,
        db=db
    )
    return {
        "detectors_run": len(results),
        "total_anomalies_found": sum(r.anomalies_found for r in results),
        "results": results
    }


# ============================================
# Anomalies
# ============================================

@router.get("/", response_model=AnomalyListResponse)
async def list_anomalies(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    detector_id: Optional[UUID] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """List anomalies with filtering."""
    result = await anomaly_service.list_anomalies(
        organization_id=organization.id,
        db=db,
        status=status,
        severity=severity,
        detector_id=detector_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset
    )
    return result


@router.get("/summary", response_model=AnomalySummary)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get anomaly summary statistics."""
    result = await anomaly_service.get_summary(
        organization_id=organization.id,
        db=db
    )
    return result


@router.get("/{anomaly_id}", response_model=AnomalyResponse)
async def get_anomaly(
    anomaly_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get an anomaly by ID."""
    result = await anomaly_service.get_anomaly(
        anomaly_id=anomaly_id,
        organization_id=organization.id,
        db=db
    )
    if not result:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return result


@router.post("/{anomaly_id}/acknowledge", response_model=AnomalyResponse)
async def acknowledge_anomaly(
    anomaly_id: UUID,
    data: AnomalyAcknowledge,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Acknowledge an anomaly."""
    result = await anomaly_service.acknowledge_anomaly(
        anomaly_id=anomaly_id,
        user_id=current_user.id,
        organization_id=organization.id,
        db=db,
        comment=data.comment
    )
    if not result:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return result


@router.post("/{anomaly_id}/resolve", response_model=AnomalyResponse)
async def resolve_anomaly(
    anomaly_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Resolve an anomaly."""
    result = await anomaly_service.resolve_anomaly(
        anomaly_id=anomaly_id,
        organization_id=organization.id,
        db=db
    )
    if not result:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return result
