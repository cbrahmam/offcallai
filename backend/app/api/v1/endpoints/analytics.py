# backend/app/api/v1/endpoints/analytics.py
"""Analytics API endpoints - Premium Feature"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime

from app.database import get_async_session
from app.core.security import get_current_user
from app.models.user import User
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
async def get_overview(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get high-level overview metrics (MTTR, MTTA, totals)"""
    service = AnalyticsService(db)
    return await service.get_overview_metrics(current_user.organization_id, days)


@router.get("/by-severity")
async def get_by_severity(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get incident breakdown by severity"""
    service = AnalyticsService(db)
    return await service.get_incidents_by_severity(current_user.organization_id, days)


@router.get("/by-status")
async def get_by_status(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get incident breakdown by status"""
    service = AnalyticsService(db)
    return await service.get_incidents_by_status(current_user.organization_id, days)


@router.get("/trend")
async def get_trend(
    days: int = Query(30, ge=1, le=365),
    granularity: str = Query("day", pattern="^(day|week|month)$"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get incident trend over time"""
    service = AnalyticsService(db)
    return await service.get_incident_trend(current_user.organization_id, days, granularity)


@router.get("/mttr-trend")
async def get_mttr_trend(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get MTTR trend over time"""
    service = AnalyticsService(db)
    return await service.get_mttr_trend(current_user.organization_id, days)


@router.get("/responders")
async def get_responder_stats(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get stats per responder/engineer"""
    service = AnalyticsService(db)
    return await service.get_responder_stats(current_user.organization_id, days)


@router.get("/on-call-load")
async def get_on_call_load(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get on-call load distribution"""
    service = AnalyticsService(db)
    return await service.get_on_call_load(current_user.organization_id, days)


@router.get("/alert-sources")
async def get_alert_sources(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get alert count by source"""
    service = AnalyticsService(db)
    return await service.get_alert_sources(current_user.organization_id, days)


@router.get("/top-services")
async def get_top_services(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get top services by incident count"""
    service = AnalyticsService(db)
    return await service.get_top_services(current_user.organization_id, days, limit)


@router.get("/hourly-distribution")
async def get_hourly_distribution(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get incident distribution by hour of day"""
    service = AnalyticsService(db)
    return await service.get_hourly_distribution(current_user.organization_id, days)


@router.get("/day-of-week")
async def get_day_of_week_distribution(
    days: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get incident distribution by day of week"""
    service = AnalyticsService(db)
    return await service.get_day_of_week_distribution(current_user.organization_id, days)


@router.get("/full")
async def get_full_analytics(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get all analytics data in one call"""
    service = AnalyticsService(db)
    return await service.get_full_analytics(current_user.organization_id, days)


@router.get("/export")
async def export_analytics(
    days: int = Query(30, ge=1, le=365),
    format: str = Query("json", pattern="^(json|csv)$"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Export analytics data"""
    service = AnalyticsService(db)
    data = await service.get_full_analytics(current_user.organization_id, days)

    if format == "csv":
        # Return CSV format for trend data
        import csv
        import io
        from fastapi.responses import StreamingResponse

        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(["date", "total", "critical", "high", "medium", "low"])

        # Write data
        for row in data.get("trend", []):
            writer.writerow([
                row.get("date"),
                row.get("total"),
                row.get("critical"),
                row.get("high"),
                row.get("medium"),
                row.get("low")
            ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=analytics_{days}d_{datetime.utcnow().strftime('%Y%m%d')}.csv"
            }
        )

    return data


# ============================================
# Alert Analytics Endpoints
# ============================================


@router.get("/alert-overview")
async def get_alert_overview(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get high-level alert metrics (totals, active, resolved, trend vs previous period)"""
    service = AnalyticsService(db)
    return await service.get_alert_overview(current_user.organization_id, days)


@router.get("/alert-trend")
async def get_alert_trend(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get alert trend over time by severity"""
    service = AnalyticsService(db)
    return await service.get_alert_trend(current_user.organization_id, days)


@router.get("/alerts-by-severity")
async def get_alerts_by_severity(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get alert count breakdown by severity"""
    service = AnalyticsService(db)
    return await service.get_alerts_by_severity(current_user.organization_id, days)


# ============================================
# Cost Attribution Endpoints
# ============================================

@router.get("/cost-attribution")
async def get_cost_attribution(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive cost attribution report.

    Shows which services/teams generate the most operational burden:
    - Alert volume by service
    - Incident burden by team
    - On-call load distribution
    - Noise analysis
    """
    service = AnalyticsService(db)
    return await service.get_cost_attribution(current_user.organization_id, days)


@router.get("/alerts-by-service")
async def get_alerts_by_service(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get alert counts grouped by service"""
    service = AnalyticsService(db)
    return await service.get_alerts_by_service(current_user.organization_id, days, limit)


@router.get("/alerts-by-team")
async def get_alerts_by_team(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get alert counts grouped by team"""
    service = AnalyticsService(db)
    return await service.get_alerts_by_team(current_user.organization_id, days)


@router.get("/oncall-burden")
async def get_oncall_burden(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get on-call burden metrics per user.

    Calculates weighted burden score based on:
    - On-call hours
    - Incidents handled
    - Critical incident weight (3x)
    """
    service = AnalyticsService(db)
    return await service.get_oncall_burden_by_team(current_user.organization_id, days)


@router.get("/noise-analysis")
async def get_noise_analysis(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Analyze alert noise.

    Identifies:
    - Auto-resolved alerts ratio
    - Duplicate/flapping alerts
    - Alerts that never became incidents
    - Noisiest services
    - Recommendations for reducing noise
    """
    service = AnalyticsService(db)
    return await service.get_noise_analysis(current_user.organization_id, days)
