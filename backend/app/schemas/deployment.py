# backend/app/schemas/deployment.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from uuid import UUID


class DeploymentStatus(str, Enum):
    """Status of a deployment."""
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"


# Request schemas
class DeploymentNotify(BaseModel):
    """
    CI/CD webhook payload to notify of a deployment.
    Called by CI/CD systems (GitHub Actions, Jenkins, etc.)
    """
    service_name: str = Field(..., min_length=1, max_length=255, description="Name of the deployed service")
    version: str = Field(..., min_length=1, max_length=100, description="Version or tag being deployed")
    environment: str = Field(default="production", max_length=50, description="Target environment")
    deployed_by: Optional[str] = Field(None, max_length=255, description="User email or CI system name")

    # Source control info
    commit_sha: Optional[str] = Field(None, max_length=40, description="Git commit SHA")
    commit_message: Optional[str] = Field(None, description="Git commit message")
    branch: Optional[str] = Field(None, max_length=100, description="Git branch name")
    repository: Optional[str] = Field(None, max_length=500, description="Repository URL or name")
    pull_request_url: Optional[str] = Field(None, max_length=500, description="PR URL if applicable")
    pull_request_number: Optional[int] = Field(None, description="PR number if applicable")

    # Deployment info
    status: DeploymentStatus = Field(default=DeploymentStatus.SUCCESS, description="Deployment status")
    duration_seconds: Optional[int] = Field(None, ge=0, description="Time taken to deploy")
    description: Optional[str] = Field(None, description="Deployment description/notes")

    # Metadata
    tags: Optional[Dict[str, str]] = Field(default_factory=dict, description="Key-value tags")
    extra_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="CI/CD specific metadata")


class DeploymentUpdate(BaseModel):
    """Update deployment status (e.g., mark as failed or rolled back)."""
    status: Optional[DeploymentStatus] = None
    duration_seconds: Optional[int] = Field(None, ge=0)
    description: Optional[str] = None
    rollback_of: Optional[UUID] = Field(None, description="ID of deployment being rolled back")
    extra_data: Optional[Dict[str, Any]] = None


# Response schemas
class DeploymentResponse(BaseModel):
    """Full deployment event response."""
    id: UUID
    organization_id: UUID
    service_name: str
    version: str
    environment: str
    deployed_by: Optional[str] = None
    deployed_at: datetime

    # Source control
    commit_sha: Optional[str] = None
    commit_message: Optional[str] = None
    branch: Optional[str] = None
    repository: Optional[str] = None
    pull_request_url: Optional[str] = None
    pull_request_number: Optional[int] = None

    # Status
    status: DeploymentStatus
    duration_seconds: Optional[int] = None
    rollback_of: Optional[UUID] = None

    # Correlation data
    incidents_within_30min: int = 0
    alerts_within_30min: int = 0
    correlated_incident_ids: List[UUID] = []
    correlated_alert_ids: List[UUID] = []

    # Metadata
    tags: Dict[str, Any] = {}
    extra_data: Dict[str, Any] = {}
    description: Optional[str] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeploymentSummary(BaseModel):
    """Lightweight deployment summary for lists and timelines."""
    id: UUID
    service_name: str
    version: str
    environment: str
    deployed_by: Optional[str] = None
    deployed_at: datetime
    status: DeploymentStatus
    commit_sha: Optional[str] = None
    branch: Optional[str] = None
    incidents_within_30min: int = 0
    alerts_within_30min: int = 0

    class Config:
        from_attributes = True


class DeploymentListResponse(BaseModel):
    """Paginated list of deployments."""
    deployments: List[DeploymentSummary]
    total: int
    page: int
    per_page: int
    total_pages: int


class DeploymentCorrelation(BaseModel):
    """Deployment correlation with incidents/alerts."""
    deployment: DeploymentResponse
    correlated_incidents: List[Dict[str, Any]] = []  # Summary of correlated incidents
    correlated_alerts: List[Dict[str, Any]] = []  # Summary of correlated alerts
    correlation_window_minutes: int = 30


class DeploymentTimelineItem(BaseModel):
    """Item in deployment timeline view."""
    id: UUID
    service_name: str
    version: str
    environment: str
    deployed_at: datetime
    status: DeploymentStatus
    deployed_by: Optional[str] = None
    commit_sha: Optional[str] = None
    incidents_within_30min: int = 0
    alerts_within_30min: int = 0
    has_issues: bool = False  # True if any incidents/alerts correlated


class DeploymentTimeline(BaseModel):
    """Timeline of deployments with incident markers."""
    items: List[DeploymentTimelineItem]
    time_range_hours: int
    total_deployments: int
    deployments_with_issues: int


# Filter schemas
class DeploymentFilters(BaseModel):
    """Filters for deployment queries."""
    service_name: Optional[str] = None
    environment: Optional[str] = None
    status: Optional[DeploymentStatus] = None
    branch: Optional[str] = None
    deployed_by: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    has_incidents: Optional[bool] = None  # Filter by whether deployment caused incidents
