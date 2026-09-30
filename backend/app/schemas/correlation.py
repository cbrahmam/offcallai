# backend/app/schemas/correlation.py
"""Schemas for AI-powered incident-telemetry correlation."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class CorrelatedTrace(BaseModel):
    """A trace correlated to an incident."""
    trace_id: str
    service_name: str
    operation_name: Optional[str] = None
    duration_ms: float
    status_code: str
    error_message: Optional[str] = None
    timestamp: datetime
    relevance_score: float = Field(ge=0.0, le=1.0, description="AI-assigned relevance score")
    relevance_reason: Optional[str] = None


class CorrelatedLog(BaseModel):
    """A log entry correlated to an incident."""
    timestamp: datetime
    service: str
    level: str
    message: str
    relevance_score: float = Field(ge=0.0, le=1.0, description="AI-assigned relevance score")
    relevance_reason: Optional[str] = None
    host_id: Optional[str] = None


class AICorrelationResult(BaseModel):
    """Result from AI correlation analysis."""
    root_cause_hypothesis: str
    confidence: float = Field(ge=0.0, le=1.0)
    related_trace_ids: List[str]
    related_log_timestamps: List[str]
    analysis_summary: str
    recommended_actions: Optional[List[str]] = None


class CorrelatedTelemetryResponse(BaseModel):
    """Full response for correlated telemetry endpoint."""
    incident_id: UUID
    incident_title: str
    incident_time: datetime

    # AI Analysis
    ai_analysis: AICorrelationResult

    # Correlated data
    traces: List[CorrelatedTrace]
    logs: List[CorrelatedLog]

    # Metadata
    analysis_time_ms: float
    telemetry_window_hours: float = 1.0
    total_traces_analyzed: int
    total_logs_analyzed: int

    class Config:
        from_attributes = True


class TelemetrySummary(BaseModel):
    """Summary of telemetry for an incident (lightweight)."""
    incident_id: UUID
    has_correlated_traces: bool
    has_correlated_logs: bool
    trace_count: int
    log_count: int
    top_services: List[str]
    has_errors: bool
