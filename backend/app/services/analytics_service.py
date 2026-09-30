# backend/app/services/analytics_service.py
"""Analytics service for calculating incident metrics and trends"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, case, extract
from sqlalchemy.orm import selectinload

from app.models.incident import Incident
from app.models.user import User
from app.models.alert import Alert, AlertSeverity
from app.models.on_call_schedule import OnCallSchedule
from app.models.on_call_shift import OnCallShift

import logging

logger = logging.getLogger(__name__)


class AnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_overview_metrics(
        self,
        organization_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get high-level overview metrics"""
        start_date = datetime.utcnow() - timedelta(days=days)

        # Total incidents in period
        total_query = select(func.count(Incident.id)).where(
            and_(
                Incident.organization_id == organization_id,
                Incident.created_at >= start_date
            )
        )
        total_result = await self.db.execute(total_query)
        total_incidents = total_result.scalar() or 0

        # Open incidents
        open_query = select(func.count(Incident.id)).where(
            and_(
                Incident.organization_id == organization_id,
                Incident.status.in_(['open', 'acknowledged'])
            )
        )
        open_result = await self.db.execute(open_query)
        open_incidents = open_result.scalar() or 0

        # Resolved in period
        resolved_query = select(func.count(Incident.id)).where(
            and_(
                Incident.organization_id == organization_id,
                Incident.resolved_at >= start_date,
                Incident.status.in_(['resolved', 'closed'])
            )
        )
        resolved_result = await self.db.execute(resolved_query)
        resolved_incidents = resolved_result.scalar() or 0

        # Calculate MTTR (Mean Time To Resolve)
        mttr = await self._calculate_mttr(organization_id, start_date)

        # Calculate MTTA (Mean Time To Acknowledge)
        mtta = await self._calculate_mtta(organization_id, start_date)

        # Previous period for comparison
        prev_start = start_date - timedelta(days=days)
        prev_total_query = select(func.count(Incident.id)).where(
            and_(
                Incident.organization_id == organization_id,
                Incident.created_at >= prev_start,
                Incident.created_at < start_date
            )
        )
        prev_result = await self.db.execute(prev_total_query)
        prev_total = prev_result.scalar() or 0

        # Calculate change percentage
        if prev_total > 0:
            change_pct = ((total_incidents - prev_total) / prev_total) * 100
        else:
            change_pct = 0 if total_incidents == 0 else 100

        return {
            "total_incidents": total_incidents,
            "open_incidents": open_incidents,
            "resolved_incidents": resolved_incidents,
            "mttr_minutes": mttr,
            "mtta_minutes": mtta,
            "period_days": days,
            "incident_change_pct": round(change_pct, 1),
            "previous_period_incidents": prev_total
        }

    async def _calculate_mttr(
        self,
        organization_id: UUID,
        start_date: datetime
    ) -> Optional[float]:
        """Calculate Mean Time To Resolve in minutes"""
        query = select(
            func.avg(
                extract('epoch', Incident.resolved_at) - extract('epoch', Incident.created_at)
            )
        ).where(
            and_(
                Incident.organization_id == organization_id,
                Incident.created_at >= start_date,
                Incident.resolved_at.isnot(None)
            )
        )
        result = await self.db.execute(query)
        avg_seconds = result.scalar()

        if avg_seconds:
            return round(avg_seconds / 60, 1)  # Convert to minutes
        return None

    async def _calculate_mtta(
        self,
        organization_id: UUID,
        start_date: datetime
    ) -> Optional[float]:
        """Calculate Mean Time To Acknowledge in minutes"""
        query = select(
            func.avg(
                extract('epoch', Incident.acknowledged_at) - extract('epoch', Incident.created_at)
            )
        ).where(
            and_(
                Incident.organization_id == organization_id,
                Incident.created_at >= start_date,
                Incident.acknowledged_at.isnot(None)
            )
        )
        result = await self.db.execute(query)
        avg_seconds = result.scalar()

        if avg_seconds:
            return round(avg_seconds / 60, 1)  # Convert to minutes
        return None

    async def get_incidents_by_severity(
        self,
        organization_id: UUID,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get incident count breakdown by severity"""
        start_date = datetime.utcnow() - timedelta(days=days)

        query = select(
            Incident.severity,
            func.count(Incident.id).label('count')
        ).where(
            and_(
                Incident.organization_id == organization_id,
                Incident.created_at >= start_date
            )
        ).group_by(Incident.severity)

        result = await self.db.execute(query)
        rows = result.all()

        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        data = [{"severity": row[0], "count": row[1]} for row in rows]
        data.sort(key=lambda x: severity_order.get(x['severity'], 99))

        return data

    async def get_incidents_by_status(
        self,
        organization_id: UUID,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get incident count breakdown by status"""
        start_date = datetime.utcnow() - timedelta(days=days)

        query = select(
            Incident.status,
            func.count(Incident.id).label('count')
        ).where(
            and_(
                Incident.organization_id == organization_id,
                Incident.created_at >= start_date
            )
        ).group_by(Incident.status)

        result = await self.db.execute(query)
        rows = result.all()

        return [{"status": row[0], "count": row[1]} for row in rows]

    async def get_incident_trend(
        self,
        organization_id: UUID,
        days: int = 30,
        granularity: str = "day"  # day, week, month
    ) -> List[Dict[str, Any]]:
        """Get incident trend over time"""
        start_date = datetime.utcnow() - timedelta(days=days)

        if granularity == "day":
            date_trunc = func.date_trunc('day', Incident.created_at)
        elif granularity == "week":
            date_trunc = func.date_trunc('week', Incident.created_at)
        else:
            date_trunc = func.date_trunc('month', Incident.created_at)

        query = select(
            date_trunc.label('date'),
            func.count(Incident.id).label('total'),
            func.count(case((Incident.severity == 'critical', 1))).label('critical'),
            func.count(case((Incident.severity == 'high', 1))).label('high'),
            func.count(case((Incident.severity == 'medium', 1))).label('medium'),
            func.count(case((Incident.severity == 'low', 1))).label('low')
        ).where(
            and_(
                Incident.organization_id == organization_id,
                Incident.created_at >= start_date
            )
        ).group_by(date_trunc).order_by(date_trunc)

        result = await self.db.execute(query)
        rows = result.all()

        return [{
            "date": row[0].isoformat() if row[0] else None,
            "total": row[1],
            "critical": row[2],
            "high": row[3],
            "medium": row[4],
            "low": row[5]
        } for row in rows]

    async def get_mttr_trend(
        self,
        organization_id: UUID,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get MTTR trend over time (daily)"""
        start_date = datetime.utcnow() - timedelta(days=days)

        date_col = func.date_trunc('day', Incident.created_at)
        query = select(
            date_col.label('date'),
            func.avg(
                extract('epoch', Incident.resolved_at) - extract('epoch', Incident.created_at)
            ).label('mttr_seconds'),
            func.count(Incident.id).label('resolved_count')
        ).where(
            and_(
                Incident.organization_id == organization_id,
                Incident.created_at >= start_date,
                Incident.resolved_at.isnot(None)
            )
        ).group_by(date_col).order_by(date_col)

        result = await self.db.execute(query)
        rows = result.all()

        return [{
            "date": row[0].isoformat() if row[0] else None,
            "mttr_minutes": round(row[1] / 60, 1) if row[1] else None,
            "resolved_count": row[2]
        } for row in rows]

    async def get_responder_stats(
        self,
        organization_id: UUID,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get stats per responder/assignee"""
        start_date = datetime.utcnow() - timedelta(days=days)

        # Get incidents assigned to each user
        query = select(
            User.id,
            User.full_name,
            User.email,
            func.count(Incident.id).label('incidents_handled'),
            func.count(case((Incident.status.in_(['resolved', 'closed']), 1))).label('resolved'),
            func.avg(
                case(
                    (Incident.resolved_at.isnot(None),
                     extract('epoch', Incident.resolved_at) - extract('epoch', Incident.created_at))
                )
            ).label('avg_resolution_seconds')
        ).join(
            Incident, Incident.assigned_to_id == User.id
        ).where(
            and_(
                Incident.organization_id == organization_id,
                Incident.created_at >= start_date
            )
        ).group_by(User.id, User.full_name, User.email).order_by(func.count(Incident.id).desc())

        result = await self.db.execute(query)
        rows = result.all()

        return [{
            "user_id": str(row[0]),
            "name": row[1],
            "email": row[2],
            "incidents_handled": row[3],
            "resolved": row[4],
            "avg_resolution_minutes": round(row[5] / 60, 1) if row[5] else None
        } for row in rows]

    async def get_on_call_load(
        self,
        organization_id: UUID,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get on-call load distribution"""
        # Get all users with their on-call shifts
        query = select(
            User.id,
            User.full_name,
            func.count(OnCallShift.id).label('shift_count')
        ).outerjoin(
            OnCallShift, OnCallShift.user_id == User.id
        ).outerjoin(
            OnCallSchedule, OnCallShift.schedule_id == OnCallSchedule.id
        ).where(
            User.organization_id == organization_id
        ).group_by(User.id, User.full_name)

        result = await self.db.execute(query)
        rows = result.all()

        return [{
            "user_id": str(row[0]),
            "name": row[1],
            "shift_count": row[2]
        } for row in rows]

    async def get_alert_sources(
        self,
        organization_id: UUID,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get alert count by source"""
        start_date = datetime.utcnow() - timedelta(days=days)

        query = select(
            Alert.source,
            func.count(Alert.id).label('count')
        ).where(
            and_(
                Alert.organization_id == organization_id,
                Alert.created_at >= start_date
            )
        ).group_by(Alert.source).order_by(func.count(Alert.id).desc())

        result = await self.db.execute(query)
        rows = result.all()

        return [{"source": row[0] or "unknown", "count": row[1]} for row in rows]

    async def get_top_services(
        self,
        organization_id: UUID,
        days: int = 30,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get top services/tags by incident count"""
        start_date = datetime.utcnow() - timedelta(days=days)

        # Get incidents and extract service from tags
        query = select(Incident).where(
            and_(
                Incident.organization_id == organization_id,
                Incident.created_at >= start_date
            )
        )
        result = await self.db.execute(query)
        incidents = result.scalars().all()

        # Count services from tags
        service_counts: Dict[str, int] = {}
        for incident in incidents:
            for tag in (incident.tags or []):
                if tag.startswith('service:') or tag.startswith('source:'):
                    service = tag.split(':', 1)[1]
                    service_counts[service] = service_counts.get(service, 0) + 1

        # Sort and limit
        sorted_services = sorted(service_counts.items(), key=lambda x: x[1], reverse=True)[:limit]

        return [{"service": s[0], "incident_count": s[1]} for s in sorted_services]

    async def get_hourly_distribution(
        self,
        organization_id: UUID,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get incident distribution by hour of day"""
        start_date = datetime.utcnow() - timedelta(days=days)

        query = select(
            extract('hour', Incident.created_at).label('hour'),
            func.count(Incident.id).label('count')
        ).where(
            and_(
                Incident.organization_id == organization_id,
                Incident.created_at >= start_date
            )
        ).group_by(extract('hour', Incident.created_at)).order_by('hour')

        result = await self.db.execute(query)
        rows = result.all()

        # Fill in missing hours with 0
        hour_data = {int(row[0]): row[1] for row in rows}
        return [{
            "hour": h,
            "count": hour_data.get(h, 0)
        } for h in range(24)]

    async def get_day_of_week_distribution(
        self,
        organization_id: UUID,
        days: int = 90
    ) -> List[Dict[str, Any]]:
        """Get incident distribution by day of week"""
        start_date = datetime.utcnow() - timedelta(days=days)

        query = select(
            extract('dow', Incident.created_at).label('day_of_week'),
            func.count(Incident.id).label('count')
        ).where(
            and_(
                Incident.organization_id == organization_id,
                Incident.created_at >= start_date
            )
        ).group_by(extract('dow', Incident.created_at)).order_by('day_of_week')

        result = await self.db.execute(query)
        rows = result.all()

        day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        day_data = {int(row[0]): row[1] for row in rows}

        return [{
            "day": day_names[d],
            "day_number": d,
            "count": day_data.get(d, 0)
        } for d in range(7)]

    async def get_alert_overview(
        self,
        organization_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get high-level alert metrics alongside incident metrics"""
        start_date = datetime.utcnow() - timedelta(days=days)

        total_q = select(func.count(Alert.id)).where(
            and_(Alert.organization_id == organization_id, Alert.created_at >= start_date)
        )
        total = (await self.db.execute(total_q)).scalar() or 0

        active_q = select(func.count(Alert.id)).where(
            and_(
                Alert.organization_id == organization_id,
                Alert.status.in_(['active', 'acknowledged'])
            )
        )
        active = (await self.db.execute(active_q)).scalar() or 0

        resolved_q = select(func.count(Alert.id)).where(
            and_(
                Alert.organization_id == organization_id,
                Alert.created_at >= start_date,
                Alert.status == 'resolved'
            )
        )
        resolved = (await self.db.execute(resolved_q)).scalar() or 0

        # Previous period comparison
        prev_start = start_date - timedelta(days=days)
        prev_q = select(func.count(Alert.id)).where(
            and_(
                Alert.organization_id == organization_id,
                Alert.created_at >= prev_start,
                Alert.created_at < start_date
            )
        )
        prev_total = (await self.db.execute(prev_q)).scalar() or 0
        change_pct = ((total - prev_total) / prev_total * 100) if prev_total > 0 else (0 if total == 0 else 100)

        return {
            "total_alerts": total,
            "active_alerts": active,
            "resolved_alerts": resolved,
            "alert_change_pct": round(change_pct, 1),
            "previous_period_alerts": prev_total,
            "period_days": days
        }

    async def get_alert_trend(
        self,
        organization_id: UUID,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get alert trend over time (daily), broken down by severity"""
        start_date = datetime.utcnow() - timedelta(days=days)
        date_trunc = func.date_trunc('day', Alert.created_at)

        query = select(
            date_trunc.label('date'),
            func.count(Alert.id).label('total'),
            func.count(case((Alert.severity == AlertSeverity.CRITICAL, 1))).label('critical'),
            func.count(case((Alert.severity == AlertSeverity.HIGH, 1))).label('high'),
            func.count(case((Alert.severity == AlertSeverity.WARNING, 1))).label('warning'),
            func.count(case((Alert.severity == AlertSeverity.ERROR, 1))).label('error')
        ).where(
            and_(
                Alert.organization_id == organization_id,
                Alert.created_at >= start_date
            )
        ).group_by(date_trunc).order_by(date_trunc)

        result = await self.db.execute(query)
        rows = result.all()

        return [{
            "date": row[0].isoformat() if row[0] else None,
            "total": row[1],
            "critical": row[2],
            "high": row[3],
            "warning": row[4],
            "error": row[5]
        } for row in rows]

    async def get_alerts_by_severity(
        self,
        organization_id: UUID,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get alert count breakdown by severity"""
        start_date = datetime.utcnow() - timedelta(days=days)

        query = select(
            Alert.severity,
            func.count(Alert.id).label('count')
        ).where(
            and_(
                Alert.organization_id == organization_id,
                Alert.created_at >= start_date
            )
        ).group_by(Alert.severity)

        result = await self.db.execute(query)
        rows = result.all()

        return [{
            "severity": row[0].value if hasattr(row[0], 'value') else str(row[0]),
            "count": row[1]
        } for row in rows]

    async def get_full_analytics(
        self,
        organization_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get all analytics data in one call — incidents AND alerts"""
        return {
            "overview": await self.get_overview_metrics(organization_id, days),
            "by_severity": await self.get_incidents_by_severity(organization_id, days),
            "by_status": await self.get_incidents_by_status(organization_id, days),
            "trend": await self.get_incident_trend(organization_id, days),
            "mttr_trend": await self.get_mttr_trend(organization_id, days),
            "responders": await self.get_responder_stats(organization_id, days),
            "alert_sources": await self.get_alert_sources(organization_id, days),
            "top_services": await self.get_top_services(organization_id, days),
            "hourly_distribution": await self.get_hourly_distribution(organization_id, days),
            "day_of_week": await self.get_day_of_week_distribution(organization_id, days),
            # Alert-specific analytics
            "alert_overview": await self.get_alert_overview(organization_id, days),
            "alert_trend": await self.get_alert_trend(organization_id, days),
            "alerts_by_severity": await self.get_alerts_by_severity(organization_id, days),
            "generated_at": datetime.utcnow().isoformat()
        }

    # ============================================
    # Cost Attribution Methods
    # ============================================

    async def get_alerts_by_service(
        self,
        organization_id: UUID,
        days: int = 30,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get alert counts grouped by service.

        Answers: "Which service generates the most alerts?"
        """
        start_date = datetime.utcnow() - timedelta(days=days)

        query = select(
            Alert.service_name,
            func.count(Alert.id).label('total_alerts'),
            func.count(case((Alert.status == 'resolved', 1))).label('resolved'),
            func.count(case((Alert.status == 'acknowledged', 1))).label('acknowledged'),
            func.count(case((Alert.severity == AlertSeverity.CRITICAL, 1))).label('critical'),
            func.count(case((Alert.severity == AlertSeverity.HIGH, 1))).label('high'),
            func.count(case((Alert.severity == AlertSeverity.ERROR, 1))).label('error'),
            func.count(case((Alert.severity == AlertSeverity.WARNING, 1))).label('warning')
        ).where(
            and_(
                Alert.organization_id == organization_id,
                Alert.created_at >= start_date,
                Alert.service_name.isnot(None)
            )
        ).group_by(Alert.service_name).order_by(func.count(Alert.id).desc()).limit(limit)

        result = await self.db.execute(query)
        rows = result.all()

        return [{
            "service_name": row[0] or "unknown",
            "total_alerts": row[1],
            "resolved": row[2],
            "acknowledged": row[3],
            "severity_breakdown": {
                "critical": row[4],
                "high": row[5],
                "error": row[6],
                "warning": row[7]
            }
        } for row in rows]

    async def get_alerts_by_team(
        self,
        organization_id: UUID,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get alert counts grouped by team (from tags).

        Teams are identified via alert tags like 'team:platform'.
        """
        start_date = datetime.utcnow() - timedelta(days=days)

        # Fetch alerts and extract team from labels/tags
        query = select(Alert).where(
            and_(
                Alert.organization_id == organization_id,
                Alert.created_at >= start_date
            )
        )
        result = await self.db.execute(query)
        alerts = result.scalars().all()

        team_counts: Dict[str, Dict[str, int]] = {}
        for alert in alerts:
            team = "unassigned"
            # Check labels for team
            if alert.labels:
                team = alert.labels.get('team', 'unassigned')

            if team not in team_counts:
                team_counts[team] = {
                    "total": 0, "critical": 0, "high": 0, "error": 0, "warning": 0, "info": 0
                }

            team_counts[team]["total"] += 1
            severity = alert.severity.value if hasattr(alert.severity, 'value') else str(alert.severity)
            if severity in team_counts[team]:
                team_counts[team][severity] += 1

        return [{
            "team": team,
            "total_alerts": counts["total"],
            "critical": counts["critical"],
            "high": counts["high"],
            "error": counts["error"],
            "warning": counts["warning"],
            "info": counts["info"]
        } for team, counts in sorted(team_counts.items(), key=lambda x: x[1]["total"], reverse=True)]

    async def get_oncall_burden_by_team(
        self,
        organization_id: UUID,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get on-call burden metrics per team/user.

        Calculates:
        - Total on-call hours
        - Number of pages received
        - Incidents handled
        - Escalations received
        """
        start_date = datetime.utcnow() - timedelta(days=days)

        # Get on-call shifts and incidents per user
        query = select(
            User.id,
            User.full_name,
            User.email,
            func.count(Incident.id).label('incidents_handled'),
            func.count(case((Incident.severity == 'critical', 1))).label('critical_incidents'),
            func.avg(
                case(
                    (Incident.resolved_at.isnot(None),
                     extract('epoch', Incident.resolved_at) - extract('epoch', Incident.created_at))
                )
            ).label('avg_resolution_seconds')
        ).outerjoin(
            Incident, and_(
                Incident.assigned_to_id == User.id,
                Incident.created_at >= start_date
            )
        ).where(
            User.organization_id == organization_id
        ).group_by(User.id, User.full_name, User.email)

        result = await self.db.execute(query)
        users = result.all()

        # Get on-call shift hours per user (for one-time shifts with datetime)
        shift_query = select(
            OnCallShift.user_id,
            func.sum(
                extract('epoch', OnCallShift.end_datetime) - extract('epoch', OnCallShift.start_datetime)
            ).label('total_seconds')
        ).join(
            OnCallSchedule, OnCallShift.schedule_id == OnCallSchedule.id
        ).where(
            and_(
                OnCallSchedule.organization_id == organization_id,
                OnCallShift.start_datetime.isnot(None),
                OnCallShift.start_datetime >= start_date
            )
        ).group_by(OnCallShift.user_id)

        shift_result = await self.db.execute(shift_query)
        shift_hours = {str(row[0]): row[1] / 3600 if row[1] else 0 for row in shift_result}

        burden_data = []
        for row in users:
            user_id = str(row[0])
            oncall_hours = round(shift_hours.get(user_id, 0), 1)
            incidents = row[3]

            # Calculate burden score (weighted metric)
            # Weight: each critical incident = 3 points, regular = 1 point
            # Plus 0.5 points per hour on-call
            burden_score = (row[4] * 3) + incidents + (oncall_hours * 0.5)

            burden_data.append({
                "user_id": user_id,
                "name": row[1],
                "email": row[2],
                "oncall_hours": oncall_hours,
                "incidents_handled": incidents,
                "critical_incidents": row[4],
                "avg_resolution_minutes": round(row[5] / 60, 1) if row[5] else None,
                "burden_score": round(burden_score, 1)
            })

        # Sort by burden score descending
        burden_data.sort(key=lambda x: x["burden_score"], reverse=True)
        return burden_data

    async def get_noise_analysis(
        self,
        organization_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze alert noise.

        Identifies:
        - Auto-resolved alerts ratio
        - Duplicate/flapping alerts
        - Alerts that never became incidents
        - Noisiest services
        """
        start_date = datetime.utcnow() - timedelta(days=days)

        # Total alerts
        total_query = select(func.count(Alert.id)).where(
            and_(
                Alert.organization_id == organization_id,
                Alert.created_at >= start_date
            )
        )
        total_result = await self.db.execute(total_query)
        total_alerts = total_result.scalar() or 0

        # Alerts that became incidents
        with_incident_query = select(func.count(Alert.id)).where(
            and_(
                Alert.organization_id == organization_id,
                Alert.created_at >= start_date,
                Alert.incident_id.isnot(None)
            )
        )
        with_incident_result = await self.db.execute(with_incident_query)
        alerts_with_incidents = with_incident_result.scalar() or 0

        # Auto-resolved alerts (resolved within 5 minutes without ack)
        auto_resolved_query = select(func.count(Alert.id)).where(
            and_(
                Alert.organization_id == organization_id,
                Alert.created_at >= start_date,
                Alert.status == 'resolved',
                Alert.incident_id.is_(None),
                # Resolved quickly - likely auto-resolved
                (extract('epoch', Alert.ended_at) - extract('epoch', Alert.started_at)) < 300
            )
        )
        auto_resolved_result = await self.db.execute(auto_resolved_query)
        auto_resolved = auto_resolved_result.scalar() or 0

        # Flapping detection - same fingerprint multiple times
        flapping_query = select(
            Alert.fingerprint,
            func.count(Alert.id).label('count')
        ).where(
            and_(
                Alert.organization_id == organization_id,
                Alert.created_at >= start_date,
                Alert.fingerprint.isnot(None)
            )
        ).group_by(Alert.fingerprint).having(func.count(Alert.id) > 3)

        flapping_result = await self.db.execute(flapping_query)
        flapping_fingerprints = flapping_result.all()
        flapping_count = sum(row[1] for row in flapping_fingerprints)

        # Noisiest services (most non-incident alerts)
        noisy_services_query = select(
            Alert.service_name,
            func.count(Alert.id).label('total'),
            func.count(case((Alert.incident_id.is_(None), 1))).label('non_incident')
        ).where(
            and_(
                Alert.organization_id == organization_id,
                Alert.created_at >= start_date,
                Alert.service_name.isnot(None)
            )
        ).group_by(Alert.service_name).order_by(func.count(case((Alert.incident_id.is_(None), 1))).desc()).limit(10)

        noisy_result = await self.db.execute(noisy_services_query)
        noisy_services = [{
            "service": row[0],
            "total_alerts": row[1],
            "non_incident_alerts": row[2],
            "noise_ratio": round((row[2] / row[1]) * 100, 1) if row[1] > 0 else 0
        } for row in noisy_result]

        # Calculate overall noise metrics
        noise_alerts = total_alerts - alerts_with_incidents
        noise_ratio = round((noise_alerts / total_alerts) * 100, 1) if total_alerts > 0 else 0

        return {
            "total_alerts": total_alerts,
            "alerts_became_incidents": alerts_with_incidents,
            "noise_alerts": noise_alerts,
            "noise_ratio_percent": noise_ratio,
            "auto_resolved_count": auto_resolved,
            "auto_resolved_percent": round((auto_resolved / total_alerts) * 100, 1) if total_alerts > 0 else 0,
            "flapping_alert_count": flapping_count,
            "flapping_fingerprints": len(flapping_fingerprints),
            "noisiest_services": noisy_services,
            "period_days": days,
            "recommendation": self._get_noise_recommendation(noise_ratio, auto_resolved, flapping_count)
        }

    def _get_noise_recommendation(
        self,
        noise_ratio: float,
        auto_resolved: int,
        flapping: int
    ) -> str:
        """Generate recommendation based on noise analysis"""
        recommendations = []

        if noise_ratio > 50:
            recommendations.append(
                "High alert noise detected. Consider reviewing alert thresholds and adding suppression rules."
            )
        elif noise_ratio > 30:
            recommendations.append(
                "Moderate alert noise. Review top noisy services and adjust sensitivity."
            )

        if auto_resolved > 100:
            recommendations.append(
                f"{auto_resolved} auto-resolved alerts. Consider increasing check intervals or adding delays."
            )

        if flapping > 50:
            recommendations.append(
                f"{flapping} flapping alerts detected. Add hysteresis or increase evaluation windows."
            )

        if not recommendations:
            return "Alert configuration looks healthy. Continue monitoring for trends."

        return " ".join(recommendations)

    async def get_cost_attribution(
        self,
        organization_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get comprehensive cost attribution report.

        Shows which services/teams generate the most operational burden:
        - Alert volume by service
        - Incident burden by team
        - On-call load distribution
        - Noise analysis
        """
        return {
            "alerts_by_service": await self.get_alerts_by_service(organization_id, days),
            "alerts_by_team": await self.get_alerts_by_team(organization_id, days),
            "oncall_burden": await self.get_oncall_burden_by_team(organization_id, days),
            "noise_analysis": await self.get_noise_analysis(organization_id, days),
            "top_services": await self.get_top_services(organization_id, days),
            "period_days": days,
            "generated_at": datetime.utcnow().isoformat()
        }
