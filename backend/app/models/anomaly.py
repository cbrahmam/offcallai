# backend/app/models/anomaly.py
"""
Anomaly Detection models for AI-powered pattern detection.
"""

from sqlalchemy import Column, String, Text, DateTime, Float, Integer, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
import enum
from app.database import Base


class AnomalyType(str, enum.Enum):
    SPIKE = "spike"  # Sudden increase
    DROP = "drop"  # Sudden decrease
    TREND = "trend"  # Gradual change
    SEASONALITY = "seasonality"  # Missing expected pattern
    OUTLIER = "outlier"  # Single point anomaly
    LEVEL_SHIFT = "level_shift"  # Permanent change in baseline


class AnomalySeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyStatus(str, enum.Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class AnomalyDetector(Base):
    """
    Configuration for anomaly detection on specific metrics.
    """
    __tablename__ = "anomaly_detectors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Detector configuration
    name = Column(String(255), nullable=False)
    description = Column(Text)
    metric_name = Column(String(255), nullable=False, index=True)

    # Scope
    host_ids = Column(JSONB, default=list)  # Empty = all hosts
    service_names = Column(JSONB, default=list)  # Empty = all services

    # Detection algorithm settings
    algorithm = Column(String(50), default="zscore")  # zscore, iqr, isolation_forest, prophet
    sensitivity = Column(Float, default=2.0)  # Lower = more sensitive
    min_data_points = Column(Integer, default=30)  # Minimum points needed for detection
    window_size = Column(Integer, default=60)  # Minutes of data to analyze
    seasonality = Column(String(20))  # null, hourly, daily, weekly

    # Detection settings
    detect_spikes = Column(String(10), default="true")
    detect_drops = Column(String(10), default="true")
    detect_trends = Column(String(10), default="true")

    # Alerting
    alert_on_anomaly = Column(String(10), default="true")
    create_incident = Column(String(10), default="false")
    severity_threshold = Column(String(20), default="medium")  # Only alert if severity >= this

    # Status
    enabled = Column(String(10), default="true", index=True)
    last_run = Column(DateTime(timezone=True))
    last_anomaly = Column(DateTime(timezone=True))

    # Training data
    baseline_mean = Column(Float)
    baseline_std = Column(Float)
    baseline_min = Column(Float)
    baseline_max = Column(Float)
    trained_at = Column(DateTime(timezone=True))

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('ix_anomaly_detectors_org_metric', 'organization_id', 'metric_name'),
    )

    def __repr__(self):
        return f"<AnomalyDetector(name='{self.name}', metric='{self.metric_name}')>"


class Anomaly(Base):
    """
    Detected anomaly event.
    """
    __tablename__ = "anomalies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    detector_id = Column(UUID(as_uuid=True), ForeignKey("anomaly_detectors.id", ondelete="CASCADE"), nullable=False, index=True)

    # Anomaly details
    anomaly_type = Column(String(30), nullable=False, index=True)
    severity = Column(String(20), default="medium", index=True)
    status = Column(String(20), default="active", index=True)

    # Metric context
    metric_name = Column(String(255), nullable=False, index=True)
    host_id = Column(UUID(as_uuid=True), index=True)
    service_name = Column(String(255))

    # Detection details
    detected_at = Column(DateTime(timezone=True), nullable=False, index=True)
    resolved_at = Column(DateTime(timezone=True))
    duration_minutes = Column(Integer)

    # Values
    anomaly_value = Column(Float, nullable=False)
    expected_value = Column(Float)
    expected_min = Column(Float)
    expected_max = Column(Float)
    deviation_score = Column(Float)  # How many std devs from normal

    # Context
    context = Column(JSONB, default=dict)  # Additional data points, related events

    # AI analysis
    ai_description = Column(Text)
    ai_possible_causes = Column(JSONB, default=list)
    ai_recommended_actions = Column(JSONB, default=list)

    # Related entities
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL"))
    acknowledged_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    acknowledged_at = Column(DateTime(timezone=True))

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('ix_anomalies_org_detected', 'organization_id', 'detected_at'),
        Index('ix_anomalies_org_status', 'organization_id', 'status'),
        Index('ix_anomalies_detector_detected', 'detector_id', 'detected_at'),
    )

    def __repr__(self):
        return f"<Anomaly(type='{self.anomaly_type}', metric='{self.metric_name}', severity='{self.severity}')>"


class AnomalyFeedback(Base):
    """
    User feedback on detected anomalies to improve detection.
    """
    __tablename__ = "anomaly_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    anomaly_id = Column(UUID(as_uuid=True), ForeignKey("anomalies.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    # Feedback
    is_true_anomaly = Column(String(10), nullable=False)  # true, false
    feedback_type = Column(String(30))  # false_positive, false_negative, severity_too_high, severity_too_low
    comment = Column(Text)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<AnomalyFeedback(anomaly_id='{self.anomaly_id}', is_true='{self.is_true_anomaly}')>"
