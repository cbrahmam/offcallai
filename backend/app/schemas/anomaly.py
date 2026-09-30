# backend/app/schemas/anomaly.py
"""
Pydantic schemas for Anomaly Detection API.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from uuid import UUID


class AnomalyType(str, Enum):
    SPIKE = "spike"
    DROP = "drop"
    TREND = "trend"
    SEASONALITY = "seasonality"
    OUTLIER = "outlier"
    LEVEL_SHIFT = "level_shift"


class AnomalySeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyStatus(str, Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class DetectorAlgorithm(str, Enum):
    ZSCORE = "zscore"  # Standard deviation based
    IQR = "iqr"  # Interquartile range
    MOVING_AVERAGE = "moving_average"  # Moving average deviation
    EXPONENTIAL = "exponential"  # Exponential smoothing


# ============================================
# Detector Schemas
# ============================================

class DetectorCreate(BaseModel):
    """Schema for creating an anomaly detector."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    metric_name: str = Field(..., min_length=1, max_length=255)
    host_ids: Optional[List[str]] = None
    service_names: Optional[List[str]] = None
    algorithm: DetectorAlgorithm = DetectorAlgorithm.ZSCORE
    sensitivity: float = Field(2.0, ge=0.5, le=5.0)
    min_data_points: int = Field(30, ge=10, le=1000)
    window_size: int = Field(60, ge=5, le=1440)  # 5 min to 24 hours
    seasonality: Optional[str] = None
    detect_spikes: bool = True
    detect_drops: bool = True
    detect_trends: bool = True
    alert_on_anomaly: bool = True
    create_incident: bool = False
    severity_threshold: AnomalySeverity = AnomalySeverity.MEDIUM
    enabled: bool = True


class DetectorUpdate(BaseModel):
    """Schema for updating an anomaly detector."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    host_ids: Optional[List[str]] = None
    service_names: Optional[List[str]] = None
    algorithm: Optional[DetectorAlgorithm] = None
    sensitivity: Optional[float] = Field(None, ge=0.5, le=5.0)
    min_data_points: Optional[int] = Field(None, ge=10, le=1000)
    window_size: Optional[int] = Field(None, ge=5, le=1440)
    seasonality: Optional[str] = None
    detect_spikes: Optional[bool] = None
    detect_drops: Optional[bool] = None
    detect_trends: Optional[bool] = None
    alert_on_anomaly: Optional[bool] = None
    create_incident: Optional[bool] = None
    severity_threshold: Optional[AnomalySeverity] = None
    enabled: Optional[bool] = None


class DetectorResponse(BaseModel):
    """Schema for detector response."""
    id: str
    organization_id: str
    name: str
    description: Optional[str]
    metric_name: str
    host_ids: List[str]
    service_names: List[str]
    algorithm: str
    sensitivity: float
    min_data_points: int
    window_size: int
    seasonality: Optional[str]
    detect_spikes: bool
    detect_drops: bool
    detect_trends: bool
    alert_on_anomaly: bool
    create_incident: bool
    severity_threshold: str
    enabled: bool
    last_run: Optional[datetime]
    last_anomaly: Optional[datetime]
    baseline_mean: Optional[float]
    baseline_std: Optional[float]
    trained_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DetectorListResponse(BaseModel):
    """Response for detector list."""
    detectors: List[DetectorResponse]
    total: int


# ============================================
# Anomaly Schemas
# ============================================

class AnomalyResponse(BaseModel):
    """Schema for anomaly response."""
    id: str
    organization_id: str
    detector_id: str
    anomaly_type: str
    severity: str
    status: str
    metric_name: str
    host_id: Optional[str]
    service_name: Optional[str]
    detected_at: datetime
    resolved_at: Optional[datetime]
    duration_minutes: Optional[int]
    anomaly_value: float
    expected_value: Optional[float]
    expected_min: Optional[float]
    expected_max: Optional[float]
    deviation_score: Optional[float]
    context: Dict[str, Any]
    ai_description: Optional[str]
    ai_possible_causes: List[str]
    ai_recommended_actions: List[str]
    incident_id: Optional[str]
    acknowledged_by: Optional[str]
    acknowledged_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class AnomalyListResponse(BaseModel):
    """Response for anomaly list."""
    anomalies: List[AnomalyResponse]
    total: int
    has_more: bool


class AnomalyAcknowledge(BaseModel):
    """Schema for acknowledging an anomaly."""
    comment: Optional[str] = None


class AnomalyResolve(BaseModel):
    """Schema for resolving an anomaly."""
    resolution_note: Optional[str] = None


class AnomalyFeedbackCreate(BaseModel):
    """Schema for submitting anomaly feedback."""
    is_true_anomaly: bool
    feedback_type: Optional[str] = None  # false_positive, false_negative, etc.
    comment: Optional[str] = None


# ============================================
# Detection & Analysis Schemas
# ============================================

class DetectionRun(BaseModel):
    """Request to run detection for a specific detector."""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class DetectionResult(BaseModel):
    """Result of a detection run."""
    detector_id: str
    detector_name: str
    metric_name: str
    data_points_analyzed: int
    anomalies_found: int
    anomalies: List[AnomalyResponse]
    baseline_stats: Dict[str, float]
    run_duration_ms: float


class AnomalySummary(BaseModel):
    """Summary of anomaly statistics."""
    total_active: int
    total_acknowledged: int
    total_resolved: int
    by_severity: Dict[str, int]
    by_type: Dict[str, int]
    by_metric: Dict[str, int]
    recent_24h: int
    recent_7d: int


class MetricBaseline(BaseModel):
    """Baseline statistics for a metric."""
    metric_name: str
    mean: float
    std: float
    min: float
    max: float
    p50: float
    p95: float
    p99: float
    sample_count: int
    calculated_at: datetime
