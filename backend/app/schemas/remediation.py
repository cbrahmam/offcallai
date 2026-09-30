# backend/app/schemas/remediation.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


# Enums
class RemediationActionType(str, Enum):
    RUNBOOK_EXECUTION = "runbook_execution"
    SCRIPT_EXECUTION = "script_execution"
    WEBHOOK_CALL = "webhook_call"
    RESTART_SERVICE = "restart_service"
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    RESTART_POD = "restart_pod"
    DRAIN_NODE = "drain_node"
    ROLLBACK_DEPLOYMENT = "rollback_deployment"
    CLEAR_CACHE = "clear_cache"
    ROTATE_CREDENTIALS = "rotate_credentials"
    NOTIFY_TEAM = "notify_team"
    CREATE_TICKET = "create_ticket"
    CUSTOM = "custom"


class RemediationTriggerType(str, Enum):
    ALERT = "alert"
    ANOMALY = "anomaly"
    INCIDENT = "incident"
    THRESHOLD = "threshold"
    SCHEDULE = "schedule"
    MANUAL = "manual"
    API = "api"


class RemediationStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    APPROVAL_REQUIRED = "approval_required"
    APPROVED = "approved"
    REJECTED = "rejected"


# ==================== Remediation Rule Schemas ====================

class RemediationRuleBase(BaseModel):
    name: str
    description: Optional[str] = None
    enabled: bool = True
    priority: int = 50
    trigger_type: str
    trigger_conditions: Dict[str, Any] = Field(default_factory=dict)
    scope_type: Optional[str] = None
    scope_filter: Dict[str, Any] = Field(default_factory=dict)
    action_type: str
    action_config: Dict[str, Any] = Field(default_factory=dict)
    require_approval: bool = False
    approval_timeout_minutes: int = 30
    max_executions_per_hour: int = 5
    cooldown_minutes: int = 15
    timeout_seconds: int = 300
    retry_count: int = 0
    retry_delay_seconds: int = 60
    dry_run: bool = False
    require_confirmation: bool = False
    stop_on_failure: bool = True
    rollback_on_failure: bool = False
    working_hours_only: bool = False
    working_hours_start: Optional[str] = None
    working_hours_end: Optional[str] = None
    working_days: List[int] = Field(default_factory=list)
    notify_on_execution: bool = True
    notify_on_failure: bool = True
    notification_channels: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    labels: Dict[str, str] = Field(default_factory=dict)


class RemediationRuleCreate(RemediationRuleBase):
    pass


class RemediationRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    trigger_type: Optional[str] = None
    trigger_conditions: Optional[Dict[str, Any]] = None
    scope_type: Optional[str] = None
    scope_filter: Optional[Dict[str, Any]] = None
    action_type: Optional[str] = None
    action_config: Optional[Dict[str, Any]] = None
    require_approval: Optional[bool] = None
    approval_timeout_minutes: Optional[int] = None
    max_executions_per_hour: Optional[int] = None
    cooldown_minutes: Optional[int] = None
    timeout_seconds: Optional[int] = None
    retry_count: Optional[int] = None
    retry_delay_seconds: Optional[int] = None
    dry_run: Optional[bool] = None
    require_confirmation: Optional[bool] = None
    stop_on_failure: Optional[bool] = None
    rollback_on_failure: Optional[bool] = None
    working_hours_only: Optional[bool] = None
    working_hours_start: Optional[str] = None
    working_hours_end: Optional[str] = None
    working_days: Optional[List[int]] = None
    notify_on_execution: Optional[bool] = None
    notify_on_failure: Optional[bool] = None
    notification_channels: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    labels: Optional[Dict[str, str]] = None


class RemediationRuleResponse(RemediationRuleBase):
    id: UUID
    organization_id: UUID
    execution_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_executed_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RemediationRuleList(BaseModel):
    items: List[RemediationRuleResponse]
    total: int
    page: int
    page_size: int


# ==================== Remediation Execution Schemas ====================

class RemediationExecutionBase(BaseModel):
    trigger_type: str
    trigger_source: Optional[str] = None
    trigger_id: Optional[UUID] = None
    trigger_data: Dict[str, Any] = Field(default_factory=dict)
    target_type: Optional[str] = None
    target_id: Optional[UUID] = None
    target_name: Optional[str] = None
    target_details: Dict[str, Any] = Field(default_factory=dict)
    action_type: str
    action_config: Dict[str, Any] = Field(default_factory=dict)
    action_parameters: Dict[str, Any] = Field(default_factory=dict)
    is_dry_run: bool = False
    is_manual: bool = False


class RemediationExecutionCreate(BaseModel):
    rule_id: Optional[UUID] = None
    trigger_type: str = "manual"
    trigger_source: Optional[str] = None
    trigger_id: Optional[UUID] = None
    trigger_data: Dict[str, Any] = Field(default_factory=dict)
    target_type: Optional[str] = None
    target_id: Optional[UUID] = None
    target_name: Optional[str] = None
    action_type: str
    action_config: Dict[str, Any] = Field(default_factory=dict)
    action_parameters: Dict[str, Any] = Field(default_factory=dict)
    is_dry_run: bool = False
    incident_id: Optional[UUID] = None


class RemediationExecutionResponse(BaseModel):
    id: UUID
    organization_id: UUID
    rule_id: Optional[UUID] = None
    execution_number: Optional[int] = None
    status: str
    trigger_type: str
    trigger_source: Optional[str] = None
    trigger_id: Optional[UUID] = None
    trigger_data: Dict[str, Any] = Field(default_factory=dict)
    target_type: Optional[str] = None
    target_id: Optional[UUID] = None
    target_name: Optional[str] = None
    target_details: Dict[str, Any] = Field(default_factory=dict)
    action_type: str
    action_config: Dict[str, Any] = Field(default_factory=dict)
    action_parameters: Dict[str, Any] = Field(default_factory=dict)
    is_dry_run: bool = False
    is_manual: bool = False
    retry_attempt: int = 0
    requires_approval: bool = False
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    approval_notes: Optional[str] = None
    rejected_by: Optional[UUID] = None
    rejected_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    result: Dict[str, Any] = Field(default_factory=dict)
    output_log: Optional[str] = None
    error_message: Optional[str] = None
    error_details: Dict[str, Any] = Field(default_factory=dict)
    rolled_back: bool = False
    incident_id: Optional[UUID] = None
    alert_id: Optional[UUID] = None
    initiated_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RemediationExecutionList(BaseModel):
    items: List[RemediationExecutionResponse]
    total: int
    page: int
    page_size: int


class ExecutionApproval(BaseModel):
    approved: bool
    notes: Optional[str] = None


# ==================== Remediation Template Schemas ====================

class RemediationTemplateBase(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    action_type: str
    action_config: Dict[str, Any] = Field(default_factory=dict)
    parameters_schema: Dict[str, Any] = Field(default_factory=dict)
    default_parameters: Dict[str, Any] = Field(default_factory=dict)
    required_integrations: List[str] = Field(default_factory=list)
    required_permissions: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class RemediationTemplateCreate(RemediationTemplateBase):
    pass


class RemediationTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    action_type: Optional[str] = None
    action_config: Optional[Dict[str, Any]] = None
    parameters_schema: Optional[Dict[str, Any]] = None
    default_parameters: Optional[Dict[str, Any]] = None
    required_integrations: Optional[List[str]] = None
    required_permissions: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class RemediationTemplateResponse(RemediationTemplateBase):
    id: UUID
    organization_id: UUID
    is_system_template: bool = False
    is_public: bool = False
    usage_count: int = 0
    last_used_at: Optional[datetime] = None
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RemediationTemplateList(BaseModel):
    items: List[RemediationTemplateResponse]
    total: int


# ==================== Remediation Playbook Schemas ====================

class PlaybookStep(BaseModel):
    id: str
    name: str
    action_type: str
    action_config: Dict[str, Any] = Field(default_factory=dict)
    condition: Optional[Dict[str, Any]] = None
    on_failure: str = "stop"  # stop, continue, goto:step-x
    wait_after_seconds: int = 0


class RemediationPlaybookBase(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    steps: List[PlaybookStep] = Field(default_factory=list)
    stop_on_first_failure: bool = True
    max_duration_minutes: int = 60
    require_approval: bool = False
    tags: List[str] = Field(default_factory=list)


class RemediationPlaybookCreate(RemediationPlaybookBase):
    pass


class RemediationPlaybookUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    steps: Optional[List[PlaybookStep]] = None
    stop_on_first_failure: Optional[bool] = None
    max_duration_minutes: Optional[int] = None
    require_approval: Optional[bool] = None
    enabled: Optional[bool] = None
    tags: Optional[List[str]] = None


class RemediationPlaybookResponse(RemediationPlaybookBase):
    id: UUID
    organization_id: UUID
    enabled: bool = True
    is_system_playbook: bool = False
    execution_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_executed_at: Optional[datetime] = None
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RemediationPlaybookList(BaseModel):
    items: List[RemediationPlaybookResponse]
    total: int


# ==================== Playbook Execution Schemas ====================

class PlaybookExecutionCreate(BaseModel):
    playbook_id: UUID
    trigger_type: str = "manual"
    trigger_id: Optional[UUID] = None
    trigger_data: Dict[str, Any] = Field(default_factory=dict)
    target_type: Optional[str] = None
    target_id: Optional[UUID] = None
    target_name: Optional[str] = None
    incident_id: Optional[UUID] = None


class StepResultSchema(BaseModel):
    step_id: str
    step_name: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    result: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class PlaybookExecutionResponse(BaseModel):
    id: UUID
    organization_id: UUID
    playbook_id: Optional[UUID] = None
    status: str
    current_step: Optional[str] = None
    current_step_index: int = 0
    trigger_type: Optional[str] = None
    trigger_id: Optional[UUID] = None
    trigger_data: Dict[str, Any] = Field(default_factory=dict)
    target_type: Optional[str] = None
    target_id: Optional[UUID] = None
    target_name: Optional[str] = None
    step_results: List[StepResultSchema] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    overall_result: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    incident_id: Optional[UUID] = None
    initiated_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PlaybookExecutionList(BaseModel):
    items: List[PlaybookExecutionResponse]
    total: int
    page: int
    page_size: int


# ==================== Manual Trigger Schemas ====================

class ManualRemediationTrigger(BaseModel):
    """Schema for manually triggering a remediation"""
    rule_id: Optional[UUID] = None
    action_type: str
    action_config: Dict[str, Any] = Field(default_factory=dict)
    target_type: Optional[str] = None
    target_id: Optional[UUID] = None
    target_name: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    is_dry_run: bool = False
    incident_id: Optional[UUID] = None
    reason: Optional[str] = None


class ManualPlaybookTrigger(BaseModel):
    """Schema for manually triggering a playbook"""
    playbook_id: UUID
    target_type: Optional[str] = None
    target_id: Optional[UUID] = None
    target_name: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    incident_id: Optional[UUID] = None
    reason: Optional[str] = None


# ==================== Statistics Schemas ====================

class RemediationStats(BaseModel):
    total_rules: int
    active_rules: int
    total_executions: int
    successful_executions: int
    failed_executions: int
    pending_approvals: int
    avg_execution_time_seconds: float
    executions_last_24h: int
    executions_last_7d: int
    top_triggered_rules: List[Dict[str, Any]] = Field(default_factory=list)
    recent_failures: List[Dict[str, Any]] = Field(default_factory=list)


class RemediationOverview(BaseModel):
    stats: RemediationStats
    recent_executions: List[RemediationExecutionResponse] = Field(default_factory=list)
    pending_approvals: List[RemediationExecutionResponse] = Field(default_factory=list)
    active_playbook_executions: List[PlaybookExecutionResponse] = Field(default_factory=list)
