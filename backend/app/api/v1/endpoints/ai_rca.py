# backend/app/api/v1/endpoints/ai_rca.py
"""API endpoints for AI Root Cause Analysis."""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, func
from typing import List, Optional
from uuid import UUID
import logging

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.incident import Incident, IncidentStatus
from app.models.ai_root_cause_analysis import AIRootCauseAnalysis, AnalysisStatus
from app.schemas.ai_rca import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisSummary,
    AnalysisFeedback,
    AnalysisStartResponse,
    AnalysisNotFoundResponse,
    SimilarIncident,
)
from typing import Union
from app.services.ai_rca_service import AIRootCauseAnalysisService

logger = logging.getLogger(__name__)
router = APIRouter()


async def find_similar_incidents(
    db: AsyncSession,
    incident: Incident,
    organization_id: UUID,
    limit: int = 5
) -> List[SimilarIncident]:
    """
    Find similar incidents based on title keywords, service, and severity.
    Returns up to `limit` similar incidents excluding the current one.
    """
    similar_incidents = []

    try:
        # Extract keywords from incident title (words > 3 chars)
        title_words = [word.lower() for word in incident.title.split() if len(word) > 3]

        # Build query for similar incidents
        query = select(Incident).where(
            and_(
                Incident.organization_id == organization_id,
                Incident.id != incident.id,  # Exclude current incident
                Incident.status.in_([IncidentStatus.RESOLVED, IncidentStatus.CLOSED])  # Only resolved/closed
            )
        ).order_by(Incident.created_at.desc()).limit(50)  # Check last 50 incidents

        result = await db.execute(query)
        candidates = result.scalars().all()

        # Score each candidate for similarity
        scored_incidents = []
        for candidate in candidates:
            score = 0.0

            # Title keyword matching (highest weight)
            candidate_words = [word.lower() for word in candidate.title.split() if len(word) > 3]
            matching_words = set(title_words) & set(candidate_words)
            if matching_words:
                score += len(matching_words) * 0.3

            # Same severity (medium weight)
            if candidate.severity == incident.severity:
                score += 0.2

            # Same service (high weight)
            incident_service = incident.extra_data.get('service_name') if incident.extra_data else None
            candidate_service = candidate.extra_data.get('service_name') if candidate.extra_data else None
            if incident_service and candidate_service and incident_service == candidate_service:
                score += 0.4

            # Same alert source (medium weight)
            incident_source = incident.extra_data.get('source') if incident.extra_data else None
            candidate_source = candidate.extra_data.get('source') if candidate.extra_data else None
            if incident_source and candidate_source and incident_source == candidate_source:
                score += 0.1

            if score > 0.2:  # Minimum threshold
                scored_incidents.append((candidate, score))

        # Sort by score and take top N
        scored_incidents.sort(key=lambda x: x[1], reverse=True)

        for candidate, score in scored_incidents[:limit]:
            resolution_time = None
            if candidate.resolved_at and candidate.created_at:
                resolution_time = int((candidate.resolved_at - candidate.created_at).total_seconds())

            similar_incidents.append(SimilarIncident(
                incident_id=candidate.id,
                title=candidate.title,
                severity=candidate.severity.value if hasattr(candidate.severity, 'value') else str(candidate.severity),
                resolved_at=candidate.resolved_at,
                resolution_time_seconds=resolution_time,
                similarity_score=round(score, 2)
            ))

    except Exception as e:
        logger.error(f"Error finding similar incidents: {e}")
        # Return empty list on error - don't fail the entire analysis

    return similar_incidents


@router.post(
    "/incidents/{incident_id}/analyze",
    response_model=AnalysisStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_analysis(
    incident_id: UUID,
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger AI root cause analysis for an incident.

    This starts an async analysis that:
    1. Gathers context (metrics, logs, traces, deployments, alerts)
    2. Sends to AI provider (Claude/Gemini) for analysis
    3. Stores results with root cause, timeline, and recommendations

    Returns immediately with analysis ID to poll for results.
    """
    # Verify incident exists and belongs to user's org
    incident_query = select(Incident).where(
        Incident.id == incident_id,
        Incident.organization_id == current_user.organization_id
    )
    result = await db.execute(incident_query)
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found"
        )

    # Check if there's already an in-progress analysis
    existing_query = select(AIRootCauseAnalysis).where(
        AIRootCauseAnalysis.incident_id == incident_id,
        AIRootCauseAnalysis.status.in_([AnalysisStatus.PENDING, AnalysisStatus.ANALYZING])
    )
    existing_result = await db.execute(existing_query)
    existing = existing_result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Analysis already in progress (ID: {existing.id})"
        )

    # Create service and start analysis
    service = AIRootCauseAnalysisService(db)

    # Run analysis (this handles both sync and async internally)
    response = await service.analyze_incident(
        incident_id=incident_id,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        request=request
    )

    return response


@router.get(
    "/incidents/{incident_id}/analysis",
    response_model=Union[AnalysisResponse, AnalysisNotFoundResponse],
)
async def get_latest_analysis(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the latest AI root cause analysis for an incident.

    If no analysis exists, returns a helpful response with instructions
    on how to trigger an analysis.
    """
    # Verify incident exists and belongs to user's org
    incident_query = select(Incident).where(
        Incident.id == incident_id,
        Incident.organization_id == current_user.organization_id
    )
    result = await db.execute(incident_query)
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found"
        )

    # Get the latest analysis
    analysis_query = select(AIRootCauseAnalysis).where(
        AIRootCauseAnalysis.incident_id == incident_id,
        AIRootCauseAnalysis.organization_id == current_user.organization_id
    ).order_by(AIRootCauseAnalysis.requested_at.desc()).limit(1)

    analysis_result = await db.execute(analysis_query)
    analysis = analysis_result.scalar_one_or_none()

    if not analysis:
        # Return helpful response instead of 404
        return AnalysisNotFoundResponse(
            exists=False,
            message="No AI analysis has been run for this incident yet.",
            suggestion="Click 'Run AI Analysis' to get AI-powered root cause analysis, timeline reconstruction, and recommended actions.",
            how_to_trigger=f"POST /api/v1/ai-rca/incidents/{incident_id}/analyze",
            benefits=[
                "AI-powered root cause identification",
                "Timeline of events reconstruction",
                "Similar incident matching",
                "Recommended remediation actions",
                "Contributing factors analysis"
            ]
        )

    # Get requester name if available
    requester_name = None
    if analysis.requested_by:
        requester_name = analysis.requested_by.full_name

    # Find similar incidents
    similar = await find_similar_incidents(db, incident, current_user.organization_id)

    return AnalysisResponse(
        id=analysis.id,
        incident_id=analysis.incident_id,
        status=analysis.status,
        requested_at=analysis.requested_at,
        requested_by_name=requester_name,
        root_cause=analysis.root_cause,
        root_cause_confidence=analysis.root_cause_confidence,
        root_cause_category=analysis.root_cause_category,
        contributing_factors=analysis.contributing_factors or [],
        affected_services=analysis.affected_services or [],
        timeline_of_events=analysis.timeline_of_events or [],
        recommended_actions=analysis.recommended_actions or [],
        similar_incidents=similar,
        provider=analysis.provider,
        model=analysis.model,
        tokens_used=analysis.tokens_used,
        analysis_duration_ms=analysis.analysis_duration_ms,
        error_message=analysis.error_message,
        feedback_helpful=analysis.feedback_helpful,
        feedback_comment=analysis.feedback_comment,
        completed_at=analysis.completed_at,
        created_at=analysis.created_at,
    )


@router.get(
    "/incidents/{incident_id}/analysis/{analysis_id}",
    response_model=AnalysisResponse,
)
async def get_analysis_by_id(
    incident_id: UUID,
    analysis_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific AI root cause analysis by ID.
    """
    # Get incident first for similar incident lookup
    incident_query = select(Incident).where(
        Incident.id == incident_id,
        Incident.organization_id == current_user.organization_id
    )
    incident_result = await db.execute(incident_query)
    incident = incident_result.scalar_one_or_none()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found"
        )

    analysis_query = select(AIRootCauseAnalysis).where(
        AIRootCauseAnalysis.id == analysis_id,
        AIRootCauseAnalysis.incident_id == incident_id,
        AIRootCauseAnalysis.organization_id == current_user.organization_id
    )

    result = await db.execute(analysis_query)
    analysis = result.scalar_one_or_none()

    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found"
        )

    requester_name = None
    if analysis.requested_by:
        requester_name = analysis.requested_by.full_name

    # Find similar incidents
    similar = await find_similar_incidents(db, incident, current_user.organization_id)

    return AnalysisResponse(
        id=analysis.id,
        incident_id=analysis.incident_id,
        status=analysis.status,
        requested_at=analysis.requested_at,
        requested_by_name=requester_name,
        root_cause=analysis.root_cause,
        root_cause_confidence=analysis.root_cause_confidence,
        root_cause_category=analysis.root_cause_category,
        contributing_factors=analysis.contributing_factors or [],
        affected_services=analysis.affected_services or [],
        timeline_of_events=analysis.timeline_of_events or [],
        recommended_actions=analysis.recommended_actions or [],
        similar_incidents=similar,
        provider=analysis.provider,
        model=analysis.model,
        tokens_used=analysis.tokens_used,
        analysis_duration_ms=analysis.analysis_duration_ms,
        error_message=analysis.error_message,
        feedback_helpful=analysis.feedback_helpful,
        feedback_comment=analysis.feedback_comment,
        completed_at=analysis.completed_at,
        created_at=analysis.created_at,
    )


@router.get(
    "/incidents/{incident_id}/analyses",
    response_model=List[AnalysisSummary],
)
async def list_analyses(
    incident_id: UUID,
    limit: int = 10,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all AI root cause analyses for an incident.
    """
    query = select(AIRootCauseAnalysis).where(
        AIRootCauseAnalysis.incident_id == incident_id,
        AIRootCauseAnalysis.organization_id == current_user.organization_id
    ).order_by(AIRootCauseAnalysis.requested_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    analyses = result.scalars().all()

    return [
        AnalysisSummary(
            id=a.id,
            incident_id=a.incident_id,
            status=a.status,
            root_cause_category=a.root_cause_category,
            root_cause_confidence=a.root_cause_confidence,
            requested_at=a.requested_at,
            completed_at=a.completed_at,
        )
        for a in analyses
    ]


@router.post(
    "/incidents/{incident_id}/analysis/{analysis_id}/feedback",
    response_model=AnalysisResponse,
)
async def submit_feedback(
    incident_id: UUID,
    analysis_id: UUID,
    feedback: AnalysisFeedback,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit feedback on an AI root cause analysis.

    This helps improve future analyses by learning what's helpful.
    """
    # Get incident first for similar incident lookup
    incident_query = select(Incident).where(
        Incident.id == incident_id,
        Incident.organization_id == current_user.organization_id
    )
    incident_result = await db.execute(incident_query)
    incident = incident_result.scalar_one_or_none()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found"
        )

    analysis_query = select(AIRootCauseAnalysis).where(
        AIRootCauseAnalysis.id == analysis_id,
        AIRootCauseAnalysis.incident_id == incident_id,
        AIRootCauseAnalysis.organization_id == current_user.organization_id
    )

    result = await db.execute(analysis_query)
    analysis = result.scalar_one_or_none()

    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found"
        )

    # Update feedback
    analysis.feedback_helpful = feedback.helpful
    analysis.feedback_comment = feedback.comment

    await db.commit()
    await db.refresh(analysis)

    requester_name = None
    if analysis.requested_by:
        requester_name = analysis.requested_by.full_name

    # Find similar incidents
    similar = await find_similar_incidents(db, incident, current_user.organization_id)

    return AnalysisResponse(
        id=analysis.id,
        incident_id=analysis.incident_id,
        status=analysis.status,
        requested_at=analysis.requested_at,
        requested_by_name=requester_name,
        root_cause=analysis.root_cause,
        root_cause_confidence=analysis.root_cause_confidence,
        root_cause_category=analysis.root_cause_category,
        contributing_factors=analysis.contributing_factors or [],
        affected_services=analysis.affected_services or [],
        timeline_of_events=analysis.timeline_of_events or [],
        recommended_actions=analysis.recommended_actions or [],
        similar_incidents=similar,
        provider=analysis.provider,
        model=analysis.model,
        tokens_used=analysis.tokens_used,
        analysis_duration_ms=analysis.analysis_duration_ms,
        error_message=analysis.error_message,
        feedback_helpful=analysis.feedback_helpful,
        feedback_comment=analysis.feedback_comment,
        completed_at=analysis.completed_at,
        created_at=analysis.created_at,
    )


@router.delete(
    "/incidents/{incident_id}/analysis/{analysis_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_analysis(
    incident_id: UUID,
    analysis_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete an AI root cause analysis.

    Only admins can delete analyses to preserve audit trail.
    """
    if current_user.role not in ["admin", "owner"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete analyses"
        )

    analysis_query = select(AIRootCauseAnalysis).where(
        AIRootCauseAnalysis.id == analysis_id,
        AIRootCauseAnalysis.incident_id == incident_id,
        AIRootCauseAnalysis.organization_id == current_user.organization_id
    )

    result = await db.execute(analysis_query)
    analysis = result.scalar_one_or_none()

    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found"
        )

    await db.delete(analysis)
    await db.commit()
