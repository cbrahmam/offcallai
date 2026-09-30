# backend/app/models/remediation.py
import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class RemediationActionType(str, enum.Enum):
    """Types of remediation actions"""
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


class RemediationTriggerType(str, enum.Enum):
    """What triggers a remediation"""
    ALERT = "alert"
    ANOMALY = "anomaly"
    INCIDENT = "incident"
    THRESHOLD = "threshold"
    SCHEDULE = "schedule"
    MANUAL = "manual"
    API = "api"


class RemediationStatus(str, enum.Enum):
    """Status of a remediation execution"""
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


class RemediationRule(Base):
    """Rules that define when and how to auto-remediate"""
    __tablename__ = "remediation_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Rule identification
    name = Column(String(255), nullable=False)
    description = Column(Text)
    enabled = Column(Boolean, default=True, index=True)
    priority = Column(Integer, default=50)  # Higher = higher priority

    # Trigger conditions
    trigger_type = Column(String(30), nullable=False, index=True)
    trigger_conditions = Column(JSONB, default=dict)  # Conditions that must match
    # Example: {"alert_type": "cpu_high", "severity": ["critical", "high"], "service": "api-server"}

    # Scope - what resources this rule applies to
    scope_type = Column(String(50))  # service, host, cluster, database, all
    scope_filter = Column(JSONB, default=dict)  # Filter conditions for scope

    # Action configuration
    action_type = Column(String(50), nullable=False)
    action_config = Column(JSONB, default=dict)
    # Example for runbook: {"runbook_id": "uuid", "parameters": {...}}
    # Example for webhook: {"url": "...", "method": "POST", "headers": {...}, "body": {...}}
    # Example for scale: {"target_replicas": 5, "max_replicas": 10}

    # Execution settings
    require_approval = Column(Boolean, default=False)
    approval_timeout_minutes = Column(Integer, default=30)
    max_executions_per_hour = Column(Integer, default=5)
    cooldown_minutes = Column(Integer, default=15)  # Wait between executions
    timeout_seconds = Column(Integer, default=300)
    retry_count = Column(Integer, default=0)
    retry_delay_seconds = Column(Integer, default=60)

    # Safety settings
    dry_run = Column(Boolean, default=False)  # Test without executing
    require_confirmation = Column(Boolean, default=False)
    stop_on_failure = Column(Boolean, default=True)
    rollback_on_failure = Column(Boolean, default=False)

    # Working hours (optional)
    working_hours_only = Column(Boolean, default=False)
    working_hours_start = Column(String(5))  # "09:00"
    working_hours_end = Column(String(5))    # "18:00"
    working_days = Column(JSONB, default=list)  # [1,2,3,4,5] = Mon-Fri

    # Notification settings
    notify_on_execution = Column(Boolean, default=True)
    notify_on_failure = Column(Boolean, default=True)
    notification_channels = Column(JSONB, default=list)  # ["slack", "email"]

    # Statistics
    execution_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    last_executed_at = Column(DateTime(timezone=True))
    last_success_at = Column(DateTime(timezone=True))
    last_failure_at = Column(DateTime(timezone=True))

    # Metadata
    tags = Column(JSONB, default=list)
    labels = Column(JSONB, default=dict)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", backref="remediation_rules")
    executions = relationship("RemediationExecution", back_populates="rule", cascade="all, delete-orphan")


class RemediationExecution(Base):
    """Record of a remediation execution"""
    __tablename__ = "remediation_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_id = Column(UUID(as_uuid=True), ForeignKey("remediation_rules.id", ondelete="SET NULL"), index=True)

    # Execution identification
    execution_number = Column(Integer)  # Sequential number for this rule
    status = Column(String(30), default="pending", index=True)

    # Trigger information
    trigger_type = Column(String(30), nullable=False)
    trigger_source = Column(String(50))  # alert, anomaly, incident, manual, api
    trigger_id = Column(UUID(as_uuid=True))  # ID of the triggering entity
    trigger_data = Column(JSONB, default=dict)  # Full trigger context

    # Target information
    target_type = Column(String(50))  # service, host, pod, database
    target_id = Column(UUID(as_uuid=True))
    target_name = Column(String(255))
    target_details = Column(JSONB, default=dict)

    # Action details
    action_type = Column(String(50), nullable=False)
    action_config = Column(JSONB, default=dict)  # Resolved config with parameters
    action_parameters = Column(JSONB, default=dict)

    # Execution state
    is_dry_run = Column(Boolean, default=False)
    is_manual = Column(Boolean, default=False)
    retry_attempt = Column(Integer, default=0)

    # Approval workflow
    requires_approval = Column(Boolean, default=False)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    approved_at = Column(DateTime(timezone=True))
    approval_notes = Column(Text)
    rejected_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    rejected_at = Column(DateTime(timezone=True))
    rejection_reason = Column(Text)

    # Timing
    queued_at = Column(DateTime(timezone=True))
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Float)
    timeout_at = Column(DateTime(timezone=True))

    # Results
    result = Column(JSONB, default=dict)  # Output from the action
    output_log = Column(Text)  # Execution logs
    error_message = Column(Text)
    error_details = Column(JSONB, default=dict)

    # Rollback information
    rolled_back = Column(Boolean, default=False)
    rollback_at = Column(DateTime(timezone=True))
    rollback_reason = Column(Text)
    rollback_result = Column(JSONB, default=dict)

    # Related entities
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL"))
    alert_id = Column(UUID(as_uuid=True))
    runbook_execution_id = Column(UUID(as_uuid=True), ForeignKey("runbook_executions.id", ondelete="SET NULL"))

    # Metadata
    initiated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", backref="remediation_executions")
    rule = relationship("RemediationRule", back_populates="executions")
    incident = relationship("Incident", backref="remediation_executions")


class RemediationTemplate(Base):
    """Reusable templates for remediation actions"""
    __tablename__ = "remediation_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Template identification
    name = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(100), index=True)  # Infrastructure, Application, Database, Security

    # Action definition
    action_type = Column(String(50), nullable=False)
    action_config = Column(JSONB, default=dict)

    # Parameters that can be customized when using the template
    parameters_schema = Column(JSONB, default=dict)
    # JSON Schema defining available parameters
    default_parameters = Column(JSONB, default=dict)

    # Requirements
    required_integrations = Column(JSONB, default=list)  # ["kubernetes", "aws"]
    required_permissions = Column(JSONB, default=list)

    # Settings
    is_system_template = Column(Boolean, default=False)  # Built-in templates
    is_public = Column(Boolean, default=False)  # Shared across orgs

    # Usage tracking
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime(timezone=True))

    # Metadata
    tags = Column(JSONB, default=list)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", backref="remediation_templates")


class RemediationPlaybook(Base):
    """Multi-step remediation playbooks"""
    __tablename__ = "remediation_playbooks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Playbook identification
    name = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(100), index=True)

    # Steps definition
    steps = Column(JSONB, default=list)
    # Each step: {
    #   "id": "step-1",
    #   "name": "Restart Service",
    #   "action_type": "restart_service",
    #   "action_config": {...},
    #   "condition": {...},  # Optional condition to execute
    #   "on_failure": "stop|continue|goto:step-x",
    #   "wait_after_seconds": 30
    # }

    # Execution settings
    stop_on_first_failure = Column(Boolean, default=True)
    max_duration_minutes = Column(Integer, default=60)
    require_approval = Column(Boolean, default=False)

    # Settings
    enabled = Column(Boolean, default=True)
    is_system_playbook = Column(Boolean, default=False)

    # Usage tracking
    execution_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    last_executed_at = Column(DateTime(timezone=True))

    # Metadata
    tags = Column(JSONB, default=list)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", backref="remediation_playbooks")


class PlaybookExecution(Base):
    """Record of a playbook execution"""
    __tablename__ = "playbook_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    playbook_id = Column(UUID(as_uuid=True), ForeignKey("remediation_playbooks.id", ondelete="SET NULL"), index=True)

    # Execution status
    status = Column(String(30), default="pending", index=True)
    current_step = Column(String(50))
    current_step_index = Column(Integer, default=0)

    # Trigger information
    trigger_type = Column(String(30))
    trigger_id = Column(UUID(as_uuid=True))
    trigger_data = Column(JSONB, default=dict)

    # Target
    target_type = Column(String(50))
    target_id = Column(UUID(as_uuid=True))
    target_name = Column(String(255))

    # Step results
    step_results = Column(JSONB, default=list)
    # Each: {"step_id": "...", "status": "...", "started_at": "...", "completed_at": "...", "result": {...}}

    # Timing
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Float)

    # Results
    overall_result = Column(JSONB, default=dict)
    error_message = Column(Text)

    # Related entities
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL"))

    # Metadata
    initiated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", backref="playbook_executions")
    playbook = relationship("RemediationPlaybook", backref="executions")
    incident = relationship("Incident", backref="playbook_executions")
