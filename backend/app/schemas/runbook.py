# backend/app/schemas/runbook.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# Enums
class PatternOperator(str, Enum):
    CONTAINS = "contains"
    EQUALS = "equals"
    REGEX = "regex"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"


class PatternField(str, Enum):
    TITLE = "title"
    DESCRIPTION = "description"
    SERVICE_NAME = "service_name"
    SEVERITY = "severity"
    SOURCE = "source"
    HOST = "host"
    ENVIRONMENT = "environment"


class RunbookExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunbookTriggerType(str, Enum):
    MANUAL = "manual"
    SUGGESTED = "suggested"
    AUTO = "auto"


# Alert Pattern Schema
class AlertPattern(BaseModel):
    field: PatternField = Field(..., description="Field to match against")
    operator: PatternOperator = Field(..., description="Match operator")
    value: str = Field(..., min_length=1, description="Value to match")

    class Config:
        from_attributes = True


# Request Schemas
class RunbookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Runbook title")
    description: Optional[str] = Field(None, description="Runbook description")
    content: str = Field(..., min_length=1, description="Markdown content with optional YAML frontmatter")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    service_names: List[str] = Field(default_factory=list, description="Services this runbook applies to")
    alert_patterns: List[AlertPattern] = Field(default_factory=list, description="Patterns that trigger this runbook")
    is_active: bool = Field(default=True, description="Whether runbook is active")


class RunbookUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    content: Optional[str] = Field(None, min_length=1)
    tags: Optional[List[str]] = None
    service_names: Optional[List[str]] = None
    alert_patterns: Optional[List[AlertPattern]] = None
    is_active: Optional[bool] = None


class RunbookExecuteRequest(BaseModel):
    incident_id: Optional[str] = Field(None, description="Associated incident ID")
    execution_context: Dict[str, Any] = Field(default_factory=dict, description="Variables passed to runbook")
    dry_run: bool = Field(default=False, description="Preview steps without executing")


# Response Schemas
class UserSummary(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None

    class Config:
        from_attributes = True


class RunbookResponse(BaseModel):
    id: str
    organization_id: str
    title: str
    description: Optional[str] = None
    content: str
    tags: List[str] = []
    service_names: List[str] = []
    alert_patterns: List[Dict[str, Any]] = []
    is_active: bool
    usage_count: int = 0
    last_used_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UserSummary] = None

    class Config:
        from_attributes = True


class RunbookListResponse(BaseModel):
    runbooks: List[RunbookResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class DeploymentSummary(BaseModel):
    id: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RunbookExecutionResponse(BaseModel):
    id: str
    organization_id: str
    runbook_id: str
    incident_id: Optional[str] = None
    status: str
    trigger_type: str
    match_score: Optional[float] = None
    match_reason: Optional[str] = None
    matched_patterns: List[Dict[str, Any]] = []
    execution_context: Dict[str, Any] = {}
    is_dry_run: bool = False
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    output_summary: Optional[str] = None
    created_at: datetime
    deployment: Optional[DeploymentSummary] = None
    runbook: Optional[RunbookResponse] = None

    class Config:
        from_attributes = True


class RunbookExecutionListResponse(BaseModel):
    executions: List[RunbookExecutionResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class RunbookSuggestion(BaseModel):
    runbook: RunbookResponse
    match_score: float = Field(..., ge=0.0, le=1.0, description="Match score (0-1)")
    match_reason: str = Field(..., description="Why this runbook was suggested")
    matched_patterns: List[str] = Field(default_factory=list, description="Patterns that matched")

    class Config:
        from_attributes = True


class RunbookSuggestionsResponse(BaseModel):
    suggestions: List[RunbookSuggestion]
    total: int


# Parsed Runbook Step (for parser service)
class ParsedStep(BaseModel):
    name: str
    command: str
    requires_approval: bool = False
    timeout: int = 300  # seconds


class ParsedRunbook(BaseModel):
    steps: List[ParsedStep] = []
    variables: Dict[str, str] = {}
    description: Optional[str] = None
