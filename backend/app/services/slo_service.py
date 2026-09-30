# backend/app/services/slo_service.py
"""SLO/SLI Tracking service"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from sqlalchemy.orm import selectinload
import logging

from app.models.service_catalog import SLO, SLIRecord, Service

logger = logging.getLogger(__name__)


class SLOService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_slo(
        self,
        organization_id: UUID,
        name: str,
        slo_type: str,
        target_percentage: int,
        service_id: UUID = None,
        description: str = None,
        target_value: int = None,
        measurement_window: str = "30d",
        error_budget_policy: str = None,
        alert_threshold_warning: int = 5000,
        alert_threshold_critical: int = 8000
    ) -> SLO:
        """Create a new SLO"""
        slo = SLO(
            organization_id=organization_id,
            service_id=service_id,
            name=name,
            description=description,
            slo_type=slo_type,
            target_percentage=target_percentage,
            target_value=target_value,
            measurement_window=measurement_window,
            error_budget_policy=error_budget_policy,
            alert_threshold_warning=alert_threshold_warning,
            alert_threshold_critical=alert_threshold_critical,
            error_budget_remaining=10000,  # 100% remaining initially
            current_percentage=target_percentage  # Assume meeting target initially
        )

        self.db.add(slo)
        await self.db.commit()
        await self.db.refresh(slo)

        logger.info(f"Created SLO: {name} ({slo.id})")
        return slo

    async def get_slo(
        self,
        slo_id: UUID,
        organization_id: UUID
    ) -> Optional[SLO]:
        """Get an SLO by ID"""
        result = await self.db.execute(
            select(SLO)
            .options(selectinload(SLO.service))
            .where(
                and_(
                    SLO.id == slo_id,
                    SLO.organization_id == organization_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_slos(
        self,
        organization_id: UUID,
        service_id: UUID = None,
        slo_type: str = None,
        is_active: bool = True,
        is_breached: bool = None,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[SLO], int]:
        """List SLOs with filters"""
        query = select(SLO).where(SLO.organization_id == organization_id)

        if is_active is not None:
            query = query.where(SLO.is_active == is_active)
        if service_id:
            query = query.where(SLO.service_id == service_id)
        if slo_type:
            query = query.where(SLO.slo_type == slo_type)
        if is_breached is not None:
            query = query.where(SLO.is_breached == is_breached)

        # Count
        count_query = select(func.count(SLO.id)).where(SLO.organization_id == organization_id)
        if is_active is not None:
            count_query = count_query.where(SLO.is_active == is_active)
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # Get SLOs
        query = query.options(selectinload(SLO.service)).order_by(
            SLO.is_breached.desc(), SLO.error_budget_remaining.asc()
        ).offset(skip).limit(limit)

        result = await self.db.execute(query)
        slos = list(result.scalars().all())

        return slos, total

    async def update_slo(
        self,
        slo_id: UUID,
        organization_id: UUID,
        **kwargs
    ) -> Optional[SLO]:
        """Update an SLO"""
        slo = await self.get_slo(slo_id, organization_id)
        if not slo:
            return None

        for key, value in kwargs.items():
            if hasattr(slo, key) and value is not None:
                setattr(slo, key, value)

        slo.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(slo)

        return slo

    async def delete_slo(
        self,
        slo_id: UUID,
        organization_id: UUID
    ) -> bool:
        """Delete an SLO"""
        slo = await self.get_slo(slo_id, organization_id)
        if not slo:
            return False

        await self.db.delete(slo)
        await self.db.commit()

        return True

    async def record_sli(
        self,
        slo_id: UUID,
        total_requests: int,
        good_requests: int,
        period: str = "1h",
        timestamp: datetime = None,
        p50_latency_ms: int = None,
        p95_latency_ms: int = None,
        p99_latency_ms: int = None
    ) -> SLIRecord:
        """Record an SLI measurement"""
        bad_requests = total_requests - good_requests
        sli_value = int((good_requests / total_requests) * 10000) if total_requests > 0 else 10000

        record = SLIRecord(
            slo_id=slo_id,
            timestamp=timestamp or datetime.utcnow(),
            period=period,
            total_requests=total_requests,
            good_requests=good_requests,
            bad_requests=bad_requests,
            sli_value=sli_value,
            p50_latency_ms=p50_latency_ms,
            p95_latency_ms=p95_latency_ms,
            p99_latency_ms=p99_latency_ms
        )

        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)

        # Update SLO current status
        await self._recalculate_slo_status(slo_id)

        return record

    async def get_sli_records(
        self,
        slo_id: UUID,
        start_date: datetime = None,
        end_date: datetime = None,
        limit: int = 720  # 30 days of hourly records
    ) -> List[SLIRecord]:
        """Get SLI records for an SLO"""
        query = select(SLIRecord).where(SLIRecord.slo_id == slo_id)

        if start_date:
            query = query.where(SLIRecord.timestamp >= start_date)
        if end_date:
            query = query.where(SLIRecord.timestamp <= end_date)

        query = query.order_by(desc(SLIRecord.timestamp)).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _recalculate_slo_status(self, slo_id: UUID) -> None:
        """Recalculate SLO current status based on recent SLI records"""
        # Get the SLO
        result = await self.db.execute(select(SLO).where(SLO.id == slo_id))
        slo = result.scalar_one_or_none()
        if not slo:
            return

        # Get window in days
        window_days = int(slo.measurement_window.replace('d', ''))
        start_date = datetime.utcnow() - timedelta(days=window_days)

        # Get records in window
        records = await self.get_sli_records(slo_id, start_date=start_date)

        if not records:
            return

        # Calculate aggregate SLI
        total_good = sum(r.good_requests for r in records)
        total_all = sum(r.total_requests for r in records)

        if total_all > 0:
            current_sli = int((total_good / total_all) * 10000)
            slo.current_percentage = current_sli

            # Calculate error budget
            # Error budget = (100% - target%) / 100%
            # e.g., 99.9% target = 0.1% error budget
            target_good_pct = slo.target_percentage / 10000
            allowed_bad_pct = 1 - target_good_pct
            actual_bad_pct = 1 - (current_sli / 10000)

            if allowed_bad_pct > 0:
                budget_consumed_pct = min(actual_bad_pct / allowed_bad_pct, 1.0)
                slo.error_budget_consumed = int(budget_consumed_pct * 10000)
                slo.error_budget_remaining = 10000 - slo.error_budget_consumed
            else:
                slo.error_budget_remaining = 10000 if current_sli >= 10000 else 0

            # Check if breached
            slo.is_breached = current_sli < slo.target_percentage

        slo.last_calculated_at = datetime.utcnow()
        await self.db.commit()

    async def get_slo_summary(
        self,
        organization_id: UUID
    ) -> Dict[str, Any]:
        """Get summary of all SLOs for dashboard"""
        slos, total = await self.list_slos(organization_id)

        breached = sum(1 for s in slos if s.is_breached)
        at_risk = sum(1 for s in slos if not s.is_breached and (s.error_budget_remaining or 10000) < 5000)
        healthy = total - breached - at_risk

        return {
            "total": total,
            "breached": breached,
            "at_risk": at_risk,
            "healthy": healthy,
            "slos": [
                {
                    "id": str(s.id),
                    "name": s.name,
                    "slo_type": s.slo_type,
                    "target": s.target_percentage / 100,
                    "current": (s.current_percentage or 0) / 100,
                    "error_budget_remaining": (s.error_budget_remaining or 0) / 100,
                    "is_breached": s.is_breached,
                    "service_name": s.service.name if s.service else None
                }
                for s in slos
            ]
        }

    async def get_error_budget_burn_rate(
        self,
        slo_id: UUID,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Calculate error budget burn rate over recent period"""
        start_date = datetime.utcnow() - timedelta(hours=hours)
        records = await self.get_sli_records(slo_id, start_date=start_date)

        if len(records) < 2:
            return {"burn_rate": 0, "projected_exhaustion_hours": None}

        # Get SLO
        result = await self.db.execute(select(SLO).where(SLO.id == slo_id))
        slo = result.scalar_one_or_none()
        if not slo:
            return {"burn_rate": 0, "projected_exhaustion_hours": None}

        # Calculate burn rate
        first_record = records[-1]
        last_record = records[0]

        # Calculate error rate change
        first_error_rate = 1 - (first_record.sli_value / 10000)
        last_error_rate = 1 - (last_record.sli_value / 10000)

        hours_elapsed = (last_record.timestamp - first_record.timestamp).total_seconds() / 3600

        if hours_elapsed > 0:
            burn_rate = (last_error_rate - first_error_rate) / hours_elapsed
        else:
            burn_rate = 0

        # Project when budget will be exhausted
        budget_remaining = (slo.error_budget_remaining or 10000) / 10000
        if burn_rate > 0:
            hours_to_exhaustion = budget_remaining / burn_rate
        else:
            hours_to_exhaustion = None

        return {
            "burn_rate": round(burn_rate * 10000, 2),  # Per hour, in basis points
            "projected_exhaustion_hours": round(hours_to_exhaustion, 1) if hours_to_exhaustion else None
        }
