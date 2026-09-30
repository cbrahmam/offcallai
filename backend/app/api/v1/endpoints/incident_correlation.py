# backend/app/api/v1/endpoints/incident_correlation.py
"""
API endpoint for AI-powered incident-telemetry correlation.

This endpoint uses Claude AI to intelligently identify traces and logs
that are related to a specific incident.
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.correlation import (
    CorrelatedTelemetryResponse,
    TelemetrySummary,
)
from app.services.correlation_service import CorrelationService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/incidents/{incident_id}/correlated-telemetry",
    response_model=CorrelatedTelemetryResponse,
)
async def get_correlated_telemetry(
    incident_id: UUID,
    window_hours: float = Query(1.0, ge=0.25, le=24.0, description="Time window in hours around incident"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get AI-correlated traces and logs for an incident.

    Uses Claude AI to analyze telemetry and identify:
    - Traces that are likely related to this incident
    - Logs that provide context for root cause
    - A root cause hypothesis based on the evidence
    - Recommended actions for resolution

    The AI analyzes telemetry within a time window around the incident creation time.

    Requires a Claude API key configured in Settings for full AI analysis.
    Falls back to time-based correlation if no API key is available.
    """
    try:
        service = CorrelationService(db)
        result = await service.get_correlated_telemetry(
            incident_id=incident_id,
            organization_id=current_user.organization_id,
            window_hours=window_hours,
        )
        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Correlation failed for incident {incident_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to correlate telemetry: {str(e)}"
        )


@router.get(
    "/incidents/{incident_id}/telemetry-summary",
    response_model=TelemetrySummary,
)
async def get_telemetry_summary(
    incident_id: UUID,
    window_hours: float = Query(1.0, ge=0.25, le=24.0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a lightweight summary of available telemetry for an incident.

    Useful for showing a preview before loading full correlated telemetry.
    """
    from datetime import timedelta, timezone
    from sqlalchemy import select
    from app.models.incident import Incident
    from app.services.clickhouse_service import ClickHouseService

    try:
        # Get incident
        result = await db.execute(
            select(Incident).where(
                Incident.id == incident_id,
                Incident.organization_id == current_user.organization_id
            )
        )
        incident = result.scalar_one_or_none()

        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident {incident_id} not found"
            )

        # Calculate time window
        incident_time = incident.created_at
        if incident_time.tzinfo is None:
            incident_time = incident_time.replace(tzinfo=timezone.utc)

        window_start = incident_time - timedelta(hours=window_hours)
        window_end = incident_time + timedelta(hours=window_hours)

        clickhouse = ClickHouseService()

        # Count traces
        trace_count_query = f"""
            SELECT
                count() as count,
                groupArray(DISTINCT service_name) as services,
                sum(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) as error_count
            FROM offcall.spans
            WHERE organization_id = '{current_user.organization_id}'
                AND timestamp >= '{window_start.strftime('%Y-%m-%d %H:%M:%S')}'
                AND timestamp <= '{window_end.strftime('%Y-%m-%d %H:%M:%S')}'
        """

        trace_result = await clickhouse.execute_query(trace_count_query)
        trace_data = trace_result[0] if trace_result else {}

        # Count logs
        log_count_query = f"""
            SELECT
                count() as count,
                sum(CASE WHEN level IN ('ERROR', 'FATAL', 'CRITICAL') THEN 1 ELSE 0 END) as error_count
            FROM offcall.logs
            WHERE organization_id = '{current_user.organization_id}'
                AND timestamp >= '{window_start.strftime('%Y-%m-%d %H:%M:%S')}'
                AND timestamp <= '{window_end.strftime('%Y-%m-%d %H:%M:%S')}'
        """

        log_result = await clickhouse.execute_query(log_count_query)
        log_data = log_result[0] if log_result else {}

        trace_count = int(trace_data.get('count', 0))
        log_count = int(log_data.get('count', 0))
        services = trace_data.get('services', [])
        if isinstance(services, str):
            services = [services]

        has_errors = (
            int(trace_data.get('error_count', 0)) > 0 or
            int(log_data.get('error_count', 0)) > 0
        )

        return TelemetrySummary(
            incident_id=incident_id,
            has_correlated_traces=trace_count > 0,
            has_correlated_logs=log_count > 0,
            trace_count=trace_count,
            log_count=log_count,
            top_services=services[:5] if services else [],
            has_errors=has_errors,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get telemetry summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get telemetry summary: {str(e)}"
        )
