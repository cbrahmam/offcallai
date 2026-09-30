# backend/app/services/anomaly_service.py
"""
Anomaly Detection Service with statistical algorithms.
"""

import uuid
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
import statistics

from sqlalchemy import select, func, and_, desc, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.anomaly import AnomalyDetector, Anomaly, AnomalyFeedback
from app.schemas.anomaly import (
    DetectorCreate, DetectorUpdate, DetectorResponse, DetectorListResponse,
    AnomalyResponse, AnomalyListResponse, AnomalySummary, DetectionResult, MetricBaseline
)

logger = logging.getLogger(__name__)


class AnomalyService:
    """Service for anomaly detection operations."""

    # ============================================
    # Detector CRUD
    # ============================================

    async def create_detector(
        self,
        data: DetectorCreate,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> DetectorResponse:
        """Create a new anomaly detector."""
        detector = AnomalyDetector(
            organization_id=organization_id,
            name=data.name,
            description=data.description,
            metric_name=data.metric_name,
            host_ids=data.host_ids or [],
            service_names=data.service_names or [],
            algorithm=data.algorithm.value,
            sensitivity=data.sensitivity,
            min_data_points=data.min_data_points,
            window_size=data.window_size,
            seasonality=data.seasonality,
            detect_spikes="true" if data.detect_spikes else "false",
            detect_drops="true" if data.detect_drops else "false",
            detect_trends="true" if data.detect_trends else "false",
            alert_on_anomaly="true" if data.alert_on_anomaly else "false",
            create_incident="true" if data.create_incident else "false",
            severity_threshold=data.severity_threshold.value,
            enabled="true" if data.enabled else "false"
        )
        db.add(detector)
        await db.commit()
        await db.refresh(detector)

        # Train baseline
        await self._train_baseline(detector, organization_id, db)

        return self._detector_to_response(detector)

    async def get_detector(
        self,
        detector_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[DetectorResponse]:
        """Get a detector by ID."""
        result = await db.execute(
            select(AnomalyDetector).where(
                AnomalyDetector.id == detector_id,
                AnomalyDetector.organization_id == organization_id
            )
        )
        detector = result.scalar_one_or_none()
        return self._detector_to_response(detector) if detector else None

    async def list_detectors(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession,
        enabled_only: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> DetectorListResponse:
        """List all detectors."""
        stmt = select(AnomalyDetector).where(
            AnomalyDetector.organization_id == organization_id
        )

        if enabled_only:
            stmt = stmt.where(AnomalyDetector.enabled == "true")

        # Count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar()

        # Get detectors
        stmt = stmt.order_by(desc(AnomalyDetector.updated_at)).offset(offset).limit(limit)
        result = await db.execute(stmt)
        detectors = result.scalars().all()

        return DetectorListResponse(
            detectors=[self._detector_to_response(d) for d in detectors],
            total=total
        )

    async def update_detector(
        self,
        detector_id: uuid.UUID,
        data: DetectorUpdate,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[DetectorResponse]:
        """Update a detector."""
        result = await db.execute(
            select(AnomalyDetector).where(
                AnomalyDetector.id == detector_id,
                AnomalyDetector.organization_id == organization_id
            )
        )
        detector = result.scalar_one_or_none()
        if not detector:
            return None

        # Update fields
        if data.name is not None:
            detector.name = data.name
        if data.description is not None:
            detector.description = data.description
        if data.host_ids is not None:
            detector.host_ids = data.host_ids
        if data.service_names is not None:
            detector.service_names = data.service_names
        if data.algorithm is not None:
            detector.algorithm = data.algorithm.value
        if data.sensitivity is not None:
            detector.sensitivity = data.sensitivity
        if data.min_data_points is not None:
            detector.min_data_points = data.min_data_points
        if data.window_size is not None:
            detector.window_size = data.window_size
        if data.seasonality is not None:
            detector.seasonality = data.seasonality
        if data.detect_spikes is not None:
            detector.detect_spikes = "true" if data.detect_spikes else "false"
        if data.detect_drops is not None:
            detector.detect_drops = "true" if data.detect_drops else "false"
        if data.detect_trends is not None:
            detector.detect_trends = "true" if data.detect_trends else "false"
        if data.alert_on_anomaly is not None:
            detector.alert_on_anomaly = "true" if data.alert_on_anomaly else "false"
        if data.create_incident is not None:
            detector.create_incident = "true" if data.create_incident else "false"
        if data.severity_threshold is not None:
            detector.severity_threshold = data.severity_threshold.value
        if data.enabled is not None:
            detector.enabled = "true" if data.enabled else "false"

        await db.commit()
        return await self.get_detector(detector_id, organization_id, db)

    async def delete_detector(
        self,
        detector_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> bool:
        """Delete a detector."""
        result = await db.execute(
            select(AnomalyDetector).where(
                AnomalyDetector.id == detector_id,
                AnomalyDetector.organization_id == organization_id
            )
        )
        detector = result.scalar_one_or_none()
        if not detector:
            return False

        await db.delete(detector)
        await db.commit()
        return True

    # ============================================
    # Anomaly Detection
    # ============================================

    async def run_detection(
        self,
        detector_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> DetectionResult:
        """Run anomaly detection for a specific detector."""
        start_run = time.time()

        result = await db.execute(
            select(AnomalyDetector).where(
                AnomalyDetector.id == detector_id,
                AnomalyDetector.organization_id == organization_id
            )
        )
        detector = result.scalar_one_or_none()
        if not detector:
            raise ValueError("Detector not found")

        # Default time range
        if not end_time:
            end_time = datetime.utcnow()
        if not start_time:
            start_time = end_time - timedelta(minutes=detector.window_size)

        # Fetch metric data
        data_points = await self._fetch_metric_data(
            detector.metric_name,
            detector.host_ids,
            organization_id,
            start_time,
            end_time,
            db
        )

        anomalies_found = []

        if len(data_points) >= detector.min_data_points:
            # Run detection algorithm
            if detector.algorithm == "zscore":
                anomalies_found = await self._detect_zscore(
                    detector, data_points, organization_id, db
                )
            elif detector.algorithm == "iqr":
                anomalies_found = await self._detect_iqr(
                    detector, data_points, organization_id, db
                )
            elif detector.algorithm == "moving_average":
                anomalies_found = await self._detect_moving_average(
                    detector, data_points, organization_id, db
                )
            else:
                # Default to zscore
                anomalies_found = await self._detect_zscore(
                    detector, data_points, organization_id, db
                )

        # Update detector last run
        detector.last_run = datetime.utcnow()
        if anomalies_found:
            detector.last_anomaly = datetime.utcnow()
        await db.commit()

        run_duration = (time.time() - start_run) * 1000

        return DetectionResult(
            detector_id=str(detector.id),
            detector_name=detector.name,
            metric_name=detector.metric_name,
            data_points_analyzed=len(data_points),
            anomalies_found=len(anomalies_found),
            anomalies=[self._anomaly_to_response(a) for a in anomalies_found],
            baseline_stats={
                "mean": detector.baseline_mean or 0,
                "std": detector.baseline_std or 0,
                "min": detector.baseline_min or 0,
                "max": detector.baseline_max or 0
            },
            run_duration_ms=run_duration
        )

    async def run_all_detectors(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> List[DetectionResult]:
        """Run all enabled detectors for an organization."""
        result = await db.execute(
            select(AnomalyDetector).where(
                AnomalyDetector.organization_id == organization_id,
                AnomalyDetector.enabled == "true"
            )
        )
        detectors = result.scalars().all()

        results = []
        for detector in detectors:
            try:
                detection_result = await self.run_detection(
                    detector.id, organization_id, db
                )
                results.append(detection_result)
            except Exception as e:
                logger.error(f"Error running detector {detector.id}: {e}")

        return results

    async def _detect_zscore(
        self,
        detector: AnomalyDetector,
        data_points: List[Dict[str, Any]],
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> List[Anomaly]:
        """Z-score based anomaly detection."""
        if not data_points:
            return []

        values = [dp["value"] for dp in data_points]
        mean = detector.baseline_mean or statistics.mean(values)
        std = detector.baseline_std or statistics.stdev(values) if len(values) > 1 else 0

        if std == 0:
            return []

        anomalies = []
        threshold = detector.sensitivity

        for dp in data_points:
            zscore = (dp["value"] - mean) / std
            abs_zscore = abs(zscore)

            if abs_zscore > threshold:
                # Determine anomaly type
                if zscore > threshold and detector.detect_spikes == "true":
                    anomaly_type = "spike"
                elif zscore < -threshold and detector.detect_drops == "true":
                    anomaly_type = "drop"
                else:
                    continue

                # Determine severity
                severity = self._calculate_severity(abs_zscore, threshold)

                # Check severity threshold
                severity_levels = ["low", "medium", "high", "critical"]
                if severity_levels.index(severity) < severity_levels.index(detector.severity_threshold):
                    continue

                # Create anomaly
                anomaly = Anomaly(
                    organization_id=organization_id,
                    detector_id=detector.id,
                    anomaly_type=anomaly_type,
                    severity=severity,
                    status="active",
                    metric_name=detector.metric_name,
                    host_id=dp.get("host_id"),
                    detected_at=dp["timestamp"],
                    anomaly_value=dp["value"],
                    expected_value=mean,
                    expected_min=mean - (std * threshold),
                    expected_max=mean + (std * threshold),
                    deviation_score=abs_zscore,
                    context={
                        "zscore": zscore,
                        "threshold": threshold,
                        "algorithm": "zscore"
                    }
                )
                db.add(anomaly)
                anomalies.append(anomaly)

        if anomalies:
            await db.commit()

        return anomalies

    async def _detect_iqr(
        self,
        detector: AnomalyDetector,
        data_points: List[Dict[str, Any]],
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> List[Anomaly]:
        """Interquartile Range based anomaly detection."""
        if len(data_points) < 4:
            return []

        values = sorted([dp["value"] for dp in data_points])
        n = len(values)
        q1 = values[n // 4]
        q3 = values[3 * n // 4]
        iqr = q3 - q1

        lower_bound = q1 - (detector.sensitivity * iqr)
        upper_bound = q3 + (detector.sensitivity * iqr)

        anomalies = []

        for dp in data_points:
            if dp["value"] < lower_bound or dp["value"] > upper_bound:
                if dp["value"] > upper_bound and detector.detect_spikes != "true":
                    continue
                if dp["value"] < lower_bound and detector.detect_drops != "true":
                    continue

                anomaly_type = "spike" if dp["value"] > upper_bound else "drop"
                deviation = abs(dp["value"] - (q1 + iqr / 2)) / (iqr if iqr > 0 else 1)
                severity = self._calculate_severity(deviation, detector.sensitivity)

                anomaly = Anomaly(
                    organization_id=organization_id,
                    detector_id=detector.id,
                    anomaly_type=anomaly_type,
                    severity=severity,
                    status="active",
                    metric_name=detector.metric_name,
                    host_id=dp.get("host_id"),
                    detected_at=dp["timestamp"],
                    anomaly_value=dp["value"],
                    expected_value=(q1 + q3) / 2,
                    expected_min=lower_bound,
                    expected_max=upper_bound,
                    deviation_score=deviation,
                    context={
                        "q1": q1,
                        "q3": q3,
                        "iqr": iqr,
                        "algorithm": "iqr"
                    }
                )
                db.add(anomaly)
                anomalies.append(anomaly)

        if anomalies:
            await db.commit()

        return anomalies

    async def _detect_moving_average(
        self,
        detector: AnomalyDetector,
        data_points: List[Dict[str, Any]],
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> List[Anomaly]:
        """Moving average based anomaly detection."""
        window_size = min(10, len(data_points) // 3)
        if window_size < 3:
            return []

        values = [dp["value"] for dp in data_points]
        anomalies = []

        for i in range(window_size, len(data_points)):
            window = values[i - window_size:i]
            ma = statistics.mean(window)
            window_std = statistics.stdev(window) if len(window) > 1 else 0

            if window_std == 0:
                continue

            current = values[i]
            deviation = abs(current - ma) / window_std

            if deviation > detector.sensitivity:
                if current > ma and detector.detect_spikes != "true":
                    continue
                if current < ma and detector.detect_drops != "true":
                    continue

                anomaly_type = "spike" if current > ma else "drop"
                severity = self._calculate_severity(deviation, detector.sensitivity)

                anomaly = Anomaly(
                    organization_id=organization_id,
                    detector_id=detector.id,
                    anomaly_type=anomaly_type,
                    severity=severity,
                    status="active",
                    metric_name=detector.metric_name,
                    host_id=data_points[i].get("host_id"),
                    detected_at=data_points[i]["timestamp"],
                    anomaly_value=current,
                    expected_value=ma,
                    expected_min=ma - (window_std * detector.sensitivity),
                    expected_max=ma + (window_std * detector.sensitivity),
                    deviation_score=deviation,
                    context={
                        "moving_average": ma,
                        "window_std": window_std,
                        "window_size": window_size,
                        "algorithm": "moving_average"
                    }
                )
                db.add(anomaly)
                anomalies.append(anomaly)

        if anomalies:
            await db.commit()

        return anomalies

    def _calculate_severity(self, deviation: float, threshold: float) -> str:
        """Calculate severity based on deviation score."""
        if deviation > threshold * 3:
            return "critical"
        elif deviation > threshold * 2:
            return "high"
        elif deviation > threshold * 1.5:
            return "medium"
        else:
            return "low"

    async def _train_baseline(
        self,
        detector: AnomalyDetector,
        organization_id: uuid.UUID,
        db: AsyncSession
    ):
        """Train baseline statistics for a detector."""
        # Fetch 7 days of historical data
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=7)

        data_points = await self._fetch_metric_data(
            detector.metric_name,
            detector.host_ids,
            organization_id,
            start_time,
            end_time,
            db
        )

        if len(data_points) >= detector.min_data_points:
            values = [dp["value"] for dp in data_points]
            detector.baseline_mean = statistics.mean(values)
            detector.baseline_std = statistics.stdev(values) if len(values) > 1 else 0
            detector.baseline_min = min(values)
            detector.baseline_max = max(values)
            detector.trained_at = datetime.utcnow()
            await db.commit()

    async def _fetch_metric_data(
        self,
        metric_name: str,
        host_ids: List[str],
        organization_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Fetch metric data points."""
        try:
            query = """
                SELECT timestamp, value, host_id
                FROM metric_data_points
                WHERE organization_id = :org_id
                  AND metric_name = :metric_name
                  AND timestamp >= :start_time
                  AND timestamp <= :end_time
            """
            params = {
                "org_id": organization_id,
                "metric_name": metric_name,
                "start_time": start_time,
                "end_time": end_time
            }

            if host_ids:
                query += " AND host_id = ANY(:host_ids)"
                params["host_ids"] = host_ids

            query += " ORDER BY timestamp"

            result = await db.execute(text(query), params)
            rows = result.fetchall()

            return [
                {"timestamp": row[0], "value": float(row[1]), "host_id": str(row[2]) if row[2] else None}
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error fetching metric data: {e}")
            return []

    # ============================================
    # Anomaly Management
    # ============================================

    async def list_anomalies(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        detector_id: Optional[uuid.UUID] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0
    ) -> AnomalyListResponse:
        """List anomalies with filtering."""
        stmt = select(Anomaly).where(Anomaly.organization_id == organization_id)

        if status:
            stmt = stmt.where(Anomaly.status == status)
        if severity:
            stmt = stmt.where(Anomaly.severity == severity)
        if detector_id:
            stmt = stmt.where(Anomaly.detector_id == detector_id)
        if start_time:
            stmt = stmt.where(Anomaly.detected_at >= start_time)
        if end_time:
            stmt = stmt.where(Anomaly.detected_at <= end_time)

        # Count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar()

        # Get anomalies
        stmt = stmt.order_by(desc(Anomaly.detected_at)).offset(offset).limit(limit)
        result = await db.execute(stmt)
        anomalies = result.scalars().all()

        return AnomalyListResponse(
            anomalies=[self._anomaly_to_response(a) for a in anomalies],
            total=total,
            has_more=(offset + len(anomalies)) < total
        )

    async def get_anomaly(
        self,
        anomaly_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[AnomalyResponse]:
        """Get an anomaly by ID."""
        result = await db.execute(
            select(Anomaly).where(
                Anomaly.id == anomaly_id,
                Anomaly.organization_id == organization_id
            )
        )
        anomaly = result.scalar_one_or_none()
        return self._anomaly_to_response(anomaly) if anomaly else None

    async def acknowledge_anomaly(
        self,
        anomaly_id: uuid.UUID,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession,
        comment: Optional[str] = None
    ) -> Optional[AnomalyResponse]:
        """Acknowledge an anomaly."""
        result = await db.execute(
            select(Anomaly).where(
                Anomaly.id == anomaly_id,
                Anomaly.organization_id == organization_id
            )
        )
        anomaly = result.scalar_one_or_none()
        if not anomaly:
            return None

        anomaly.status = "acknowledged"
        anomaly.acknowledged_by = user_id
        anomaly.acknowledged_at = datetime.utcnow()

        await db.commit()
        return self._anomaly_to_response(anomaly)

    async def resolve_anomaly(
        self,
        anomaly_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[AnomalyResponse]:
        """Resolve an anomaly."""
        result = await db.execute(
            select(Anomaly).where(
                Anomaly.id == anomaly_id,
                Anomaly.organization_id == organization_id
            )
        )
        anomaly = result.scalar_one_or_none()
        if not anomaly:
            return None

        anomaly.status = "resolved"
        anomaly.resolved_at = datetime.utcnow()
        if anomaly.detected_at:
            anomaly.duration_minutes = int((anomaly.resolved_at - anomaly.detected_at).total_seconds() / 60)

        await db.commit()
        return self._anomaly_to_response(anomaly)

    async def get_summary(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> AnomalySummary:
        """Get anomaly summary statistics."""
        now = datetime.utcnow()
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)

        # Status counts
        status_result = await db.execute(
            text("""
                SELECT status, COUNT(*) FROM anomalies
                WHERE organization_id = :org_id
                GROUP BY status
            """),
            {"org_id": organization_id}
        )
        status_counts = {row[0]: row[1] for row in status_result.fetchall()}

        # Severity counts
        severity_result = await db.execute(
            text("""
                SELECT severity, COUNT(*) FROM anomalies
                WHERE organization_id = :org_id AND status = 'active'
                GROUP BY severity
            """),
            {"org_id": organization_id}
        )
        severity_counts = {row[0]: row[1] for row in severity_result.fetchall()}

        # Type counts
        type_result = await db.execute(
            text("""
                SELECT anomaly_type, COUNT(*) FROM anomalies
                WHERE organization_id = :org_id AND status = 'active'
                GROUP BY anomaly_type
            """),
            {"org_id": organization_id}
        )
        type_counts = {row[0]: row[1] for row in type_result.fetchall()}

        # Metric counts
        metric_result = await db.execute(
            text("""
                SELECT metric_name, COUNT(*) FROM anomalies
                WHERE organization_id = :org_id AND status = 'active'
                GROUP BY metric_name
                ORDER BY COUNT(*) DESC
                LIMIT 10
            """),
            {"org_id": organization_id}
        )
        metric_counts = {row[0]: row[1] for row in metric_result.fetchall()}

        # Recent counts
        recent_24h = await db.execute(
            text("""
                SELECT COUNT(*) FROM anomalies
                WHERE organization_id = :org_id AND detected_at >= :day_ago
            """),
            {"org_id": organization_id, "day_ago": day_ago}
        )

        recent_7d = await db.execute(
            text("""
                SELECT COUNT(*) FROM anomalies
                WHERE organization_id = :org_id AND detected_at >= :week_ago
            """),
            {"org_id": organization_id, "week_ago": week_ago}
        )

        return AnomalySummary(
            total_active=status_counts.get("active", 0),
            total_acknowledged=status_counts.get("acknowledged", 0),
            total_resolved=status_counts.get("resolved", 0),
            by_severity=severity_counts,
            by_type=type_counts,
            by_metric=metric_counts,
            recent_24h=recent_24h.scalar() or 0,
            recent_7d=recent_7d.scalar() or 0
        )

    # ============================================
    # Helpers
    # ============================================

    def _detector_to_response(self, detector: AnomalyDetector) -> DetectorResponse:
        """Convert detector model to response."""
        return DetectorResponse(
            id=str(detector.id),
            organization_id=str(detector.organization_id),
            name=detector.name,
            description=detector.description,
            metric_name=detector.metric_name,
            host_ids=detector.host_ids or [],
            service_names=detector.service_names or [],
            algorithm=detector.algorithm,
            sensitivity=detector.sensitivity,
            min_data_points=detector.min_data_points,
            window_size=detector.window_size,
            seasonality=detector.seasonality,
            detect_spikes=detector.detect_spikes == "true",
            detect_drops=detector.detect_drops == "true",
            detect_trends=detector.detect_trends == "true",
            alert_on_anomaly=detector.alert_on_anomaly == "true",
            create_incident=detector.create_incident == "true",
            severity_threshold=detector.severity_threshold,
            enabled=detector.enabled == "true",
            last_run=detector.last_run,
            last_anomaly=detector.last_anomaly,
            baseline_mean=detector.baseline_mean,
            baseline_std=detector.baseline_std,
            trained_at=detector.trained_at,
            created_at=detector.created_at,
            updated_at=detector.updated_at
        )

    def _anomaly_to_response(self, anomaly: Anomaly) -> AnomalyResponse:
        """Convert anomaly model to response."""
        return AnomalyResponse(
            id=str(anomaly.id),
            organization_id=str(anomaly.organization_id),
            detector_id=str(anomaly.detector_id),
            anomaly_type=anomaly.anomaly_type,
            severity=anomaly.severity,
            status=anomaly.status,
            metric_name=anomaly.metric_name,
            host_id=str(anomaly.host_id) if anomaly.host_id else None,
            service_name=anomaly.service_name,
            detected_at=anomaly.detected_at,
            resolved_at=anomaly.resolved_at,
            duration_minutes=anomaly.duration_minutes,
            anomaly_value=anomaly.anomaly_value,
            expected_value=anomaly.expected_value,
            expected_min=anomaly.expected_min,
            expected_max=anomaly.expected_max,
            deviation_score=anomaly.deviation_score,
            context=anomaly.context or {},
            ai_description=anomaly.ai_description,
            ai_possible_causes=anomaly.ai_possible_causes or [],
            ai_recommended_actions=anomaly.ai_recommended_actions or [],
            incident_id=str(anomaly.incident_id) if anomaly.incident_id else None,
            acknowledged_by=str(anomaly.acknowledged_by) if anomaly.acknowledged_by else None,
            acknowledged_at=anomaly.acknowledged_at,
            created_at=anomaly.created_at
        )


# Singleton instance
anomaly_service = AnomalyService()
