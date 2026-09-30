from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field, validator
from enum import Enum

class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning" 
    ERROR = "error"
    HIGH = "high"  # For compatibility
    CRITICAL = "critical"

class AlertStatus(str, Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"
    ACKNOWLEDGED = "acknowledged"  # New status

class AlertSource(str, Enum):
    DATADOG = "datadog"
    GRAFANA = "grafana"
    AWS_CLOUDWATCH = "aws_cloudwatch"
    NEW_RELIC = "new_relic"
    PROMETHEUS = "prometheus"
    PAGERDUTY = "pagerduty"
    PINGDOM = "pingdom"
    GENERIC = "generic"

# Result of processing an alert
class AlertProcessingResult(BaseModel):
    success: bool
    message: str
    incident_id: Optional[str] = None
    incident_created: bool = False
    incident_updated: bool = False
    alert_fingerprint: str
    
class AlertResponse(BaseModel):
    id: str
    external_id: str
    fingerprint: str
    title: str
    description: Optional[str] = None
    severity: AlertSeverity
    status: AlertStatus
    source: AlertSource
    service_name: Optional[str] = None
    environment: Optional[str] = None
    host: Optional[str] = None
    incident_id: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    labels: Optional[Dict[str, Any]] = None
    raw_data: Optional[Dict[str, Any]] = None

# Generic webhook payload that works with any monitoring tool
class GenericAlertPayload(BaseModel):
    alert_id: str = Field(..., description="Unique alert identifier")
    title: str = Field(..., description="Alert title/summary")
    description: Optional[str] = Field(None, description="Detailed alert description")
    severity: AlertSeverity = Field(AlertSeverity.WARNING, description="Alert severity")
    status: AlertStatus = Field(AlertStatus.ACTIVE, description="Alert status")
    source: AlertSource = Field(AlertSource.GENERIC, description="Monitoring tool source")
    
    # Metadata
    service: Optional[str] = Field(None, description="Affected service")
    environment: Optional[str] = Field(None, description="Environment (prod, staging, etc)")
    region: Optional[str] = Field(None, description="Geographic region")
    host: Optional[str] = Field(None, description="Affected host/server")
    tags: Optional[List[str]] = Field(default_factory=list, description="Alert tags")
    
    # Timing
    started_at: Optional[datetime] = Field(None, description="When alert started firing")
    resolved_at: Optional[datetime] = Field(None, description="When alert was resolved")
    
    # URLs and context
    alert_url: Optional[str] = Field(None, description="Link to alert in monitoring tool")
    runbook_url: Optional[str] = Field(None, description="Link to runbook/documentation")
    dashboard_url: Optional[str] = Field(None, description="Link to relevant dashboard")
    
    # Raw payload for debugging
    raw_payload: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Original webhook payload")

    @validator('severity', pre=True)
    def normalize_severity(cls, v):
        """Normalize severity from various formats"""
        if isinstance(v, str):
            v = v.lower()
            # Handle common variations
            if v in ['high', 'error']:
                return AlertSeverity.ERROR
            elif v in ['medium', 'warn', 'warning']:
                return AlertSeverity.WARNING
            elif v in ['low', 'info']:
                return AlertSeverity.INFO
            elif v in ['critical', 'crit']:
                return AlertSeverity.CRITICAL
        return v

# Datadog-specific webhook payload
class DatadogAlertPayload(BaseModel):
    """Datadog webhook payload format"""
    alert_id: Optional[str] = Field(None, alias="id")
    alert_type: Optional[str] = None
    title: str
    body: Optional[str] = None
    priority: Optional[str] = None
    last_updated: Optional[str] = None
    event_type: str = "triggered"  # "triggered" or "resolved" 
    link: Optional[str] = None
    tags: Optional[List[str]] = Field(default_factory=list)
    aggreg_key: Optional[str] = None
    source_type_name: Optional[str] = None
    date: Optional[int] = None  # Unix timestamp
    org_id: Optional[int] = None
    
    def to_generic(self) -> GenericAlertPayload:
        """Convert Datadog payload to generic format"""
        severity_map = {
            "P1": AlertSeverity.CRITICAL,
            "P2": AlertSeverity.ERROR,
            "P3": AlertSeverity.WARNING,
            "P4": AlertSeverity.INFO,
            "P5": AlertSeverity.INFO,
            "critical": AlertSeverity.CRITICAL,
            "error": AlertSeverity.ERROR,
            "warning": AlertSeverity.WARNING,
            "info": AlertSeverity.INFO
        }
        
        status_map = {
            "triggered": AlertStatus.ACTIVE,
            "resolved": AlertStatus.RESOLVED,
            "recovery": AlertStatus.RESOLVED
        }
        
        # Extract service and environment from tags
        service = None
        environment = None
        region = None
        
        for tag in (self.tags or []):
            if tag.startswith("service:"):
                service = tag.split(":", 1)[1]
            elif tag.startswith("env:"):
                environment = tag.split(":", 1)[1]
            elif tag.startswith("region:"):
                region = tag.split(":", 1)[1]
        
        return GenericAlertPayload(
            alert_id=self.alert_id or self.aggreg_key or "unknown",
            title=self.title,
            description=self.body,
            severity=severity_map.get(
                (self.priority or "").lower(), 
                AlertSeverity.WARNING
            ),
            status=status_map.get(self.event_type, AlertStatus.ACTIVE),
            source=AlertSource.DATADOG,
            service=service,
            environment=environment,
            region=region,
            tags=self.tags or [],
            alert_url=self.link,
            started_at=datetime.fromtimestamp(self.date) if self.date else None,
            raw_payload=self.dict()
        )

# Grafana-specific webhook payload
class GrafanaAlertPayload(BaseModel):
    """Grafana webhook payload format (supports both legacy and new alerting)"""
    # Common fields
    title: Optional[str] = None
    state: str = "alerting"  # "alerting", "ok", "no_data"
    message: Optional[str] = None
    
    # Legacy format fields
    ruleId: Optional[int] = None
    ruleName: Optional[str] = None  
    ruleUrl: Optional[str] = None
    evalMatches: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    tags: Optional[Dict[str, str]] = Field(default_factory=dict)
    
    # New format fields (Grafana v8+)
    alerts: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    groupLabels: Optional[Dict[str, str]] = Field(default_factory=dict)
    commonLabels: Optional[Dict[str, str]] = Field(default_factory=dict)
    commonAnnotations: Optional[Dict[str, str]] = Field(default_factory=dict)
    externalURL: Optional[str] = None
    version: Optional[str] = None
    groupKey: Optional[str] = None
    truncatedAlerts: Optional[int] = None
    
    # Single alert fields (when processing individual alerts)
    labels: Optional[Dict[str, str]] = Field(default_factory=dict)
    annotations: Optional[Dict[str, str]] = Field(default_factory=dict)
    startsAt: Optional[str] = None
    endsAt: Optional[str] = None
    generatorURL: Optional[str] = None
    fingerprint: Optional[str] = None
    
    def to_generic(self) -> GenericAlertPayload:
        """Convert Grafana payload to generic format"""
        status_map = {
            "alerting": AlertStatus.ACTIVE,
            "ok": AlertStatus.RESOLVED,
            "no_data": AlertStatus.ACTIVE,
            "pending": AlertStatus.ACTIVE
        }
        
        # Determine severity from labels/tags
        severity = AlertSeverity.WARNING
        labels = self.labels or {}
        tags = self.tags or {}
        
        if labels.get("severity") or tags.get("severity"):
            severity_str = (labels.get("severity") or tags.get("severity", "")).lower()
            if severity_str in ["critical", "crit"]:
                severity = AlertSeverity.CRITICAL
            elif severity_str in ["error", "high"]:
                severity = AlertSeverity.ERROR
            elif severity_str in ["warning", "warn", "medium"]:
                severity = AlertSeverity.WARNING
            elif severity_str in ["info", "low"]:
                severity = AlertSeverity.INFO
        
        # Get service and environment from labels
        service = labels.get("service") or tags.get("service")
        environment = labels.get("environment") or labels.get("env") or tags.get("env")
        region = labels.get("region") or tags.get("region")
        
        # Build description
        description_parts = []
        if self.message:
            description_parts.append(self.message)
        if self.annotations and self.annotations.get("description"):
            description_parts.append(self.annotations["description"])
        
        # Parse timestamps
        started_at = None
        resolved_at = None
        if self.startsAt:
            try:
                started_at = datetime.fromisoformat(self.startsAt.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass
        if self.endsAt:
            try:
                resolved_at = datetime.fromisoformat(self.endsAt.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass
        
        return GenericAlertPayload(
            alert_id=self.fingerprint or str(self.ruleId) or "unknown",
            title=self.title or self.ruleName or labels.get("alertname", "Grafana Alert"),
            description="\n".join(description_parts) if description_parts else None,
            severity=severity,
            status=status_map.get(self.state, AlertStatus.ACTIVE),
            source=AlertSource.GRAFANA,
            service=service,
            environment=environment,
            region=region,
            tags=[f"{k}:{v}" for k, v in {**labels, **tags}.items()],
            alert_url=self.ruleUrl or self.generatorURL or self.externalURL,
            runbook_url=self.annotations.get("runbook_url") if self.annotations else None,
            dashboard_url=self.annotations.get("dashboard_url") if self.annotations else None,
            started_at=started_at,
            resolved_at=resolved_at,
            raw_payload=self.dict()
        )

# AWS CloudWatch-specific payload (via SNS)
class CloudWatchAlertPayload(BaseModel):
    """AWS CloudWatch alarm payload (typically via SNS)"""
    Type: Optional[str] = None  # "Notification"
    MessageId: Optional[str] = None
    TopicArn: Optional[str] = None
    Subject: Optional[str] = None
    Message: Union[str, Dict[str, Any]]  # Can be JSON string or dict
    Timestamp: Optional[str] = None
    SignatureVersion: Optional[str] = None
    Signature: Optional[str] = None
    
    # Direct alarm fields (when not via SNS)
    AlarmName: Optional[str] = None
    AlarmDescription: Optional[str] = None
    NewStateValue: Optional[str] = None  # "ALARM", "OK", "INSUFFICIENT_DATA"
    NewStateReason: Optional[str] = None
    StateChangeTime: Optional[str] = None
    Region: Optional[str] = None
    Namespace: Optional[str] = None
    MetricName: Optional[str] = None
    
    def to_generic(self) -> GenericAlertPayload:
        """Convert CloudWatch payload to generic format"""
        # Parse message if it's a string
        message_data = self.Message
        if isinstance(self.Message, str):
            try:
                import json
                message_data = json.loads(self.Message)
            except (json.JSONDecodeError, TypeError):
                message_data = {}
        
        # Get alarm info from message or direct fields
        alarm_name = message_data.get("AlarmName") or self.AlarmName or "CloudWatch Alert"
        alarm_desc = message_data.get("AlarmDescription") or self.AlarmDescription or self.Subject or ""
        state = message_data.get("NewStateValue") or self.NewStateValue or "ALARM"
        region = message_data.get("Region") or self.Region
        namespace = message_data.get("Namespace") or self.Namespace
        
        # Map state to status
        status_map = {
            "ALARM": AlertStatus.ACTIVE,
            "OK": AlertStatus.RESOLVED,
            "INSUFFICIENT_DATA": AlertStatus.ACTIVE
        }
        
        # Determine severity based on alarm
        severity = AlertSeverity.WARNING
        if "critical" in alarm_name.lower() or "critical" in alarm_desc.lower():
            severity = AlertSeverity.CRITICAL
        elif "error" in alarm_name.lower() or "high" in alarm_name.lower():
            severity = AlertSeverity.ERROR
        
        # Parse timestamp
        timestamp = None
        timestamp_str = message_data.get("StateChangeTime") or self.StateChangeTime or self.Timestamp
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass
        
        return GenericAlertPayload(
            alert_id=self.MessageId or alarm_name,
            title=alarm_name,
            description=alarm_desc,
            severity=severity,
            status=status_map.get(state, AlertStatus.ACTIVE),
            source=AlertSource.AWS_CLOUDWATCH,
            service=namespace,
            region=region,
            started_at=timestamp if state == "ALARM" else None,
            resolved_at=timestamp if state == "OK" else None,
            alert_url=f"https://console.aws.amazon.com/cloudwatch/home?region={region or 'us-east-1'}#alarmsV2:alarm/{alarm_name}" if alarm_name else None,
            raw_payload=self.dict()
        )

# New Relic-specific payload
class NewRelicAlertPayload(BaseModel):
    """New Relic webhook payload format"""
    account_id: Optional[int] = None
    account_name: Optional[str] = None
    condition_id: Optional[int] = None
    condition_name: Optional[str] = None
    current_state: Optional[str] = None  # "open", "acknowledged", "closed"
    details: Optional[str] = None
    event_type: Optional[str] = None
    incident_acknowledge_url: Optional[str] = None
    incident_api_url: Optional[str] = None
    incident_id: Optional[int] = None
    incident_url: Optional[str] = None
    owner: Optional[str] = None
    policy_name: Optional[str] = None
    policy_url: Optional[str] = None
    runbook_url: Optional[str] = None
    severity: Optional[str] = None  # "critical", "warning", "info"
    targets: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    timestamp: Optional[int] = None
    version: Optional[str] = None
    
    def to_generic(self) -> GenericAlertPayload:
        """Convert New Relic payload to generic format"""
        severity_map = {
            "critical": AlertSeverity.CRITICAL,
            "warning": AlertSeverity.WARNING,
            "info": AlertSeverity.INFO
        }
        
        status_map = {
            "open": AlertStatus.ACTIVE,
            "acknowledged": AlertStatus.ACKNOWLEDGED,
            "closed": AlertStatus.RESOLVED
        }
        
        # Extract environment from targets
        environment = None
        if self.targets:
            for target in self.targets:
                labels = target.get("labels", {})
                if labels.get("environment"):
                    environment = labels["environment"]
                    break
        
        return GenericAlertPayload(
            alert_id=str(self.incident_id) if self.incident_id else "unknown",
            title=self.condition_name or "New Relic Alert",
            description=self.details or "",
            severity=severity_map.get(
                (self.severity or "").lower(), 
                AlertSeverity.WARNING
            ),
            status=status_map.get(
                (self.current_state or "").lower(),
                AlertStatus.ACTIVE
            ),
            source=AlertSource.NEW_RELIC,
            service=self.policy_name,
            environment=environment,
            started_at=datetime.fromtimestamp(self.timestamp) if self.timestamp else None,
            alert_url=self.incident_url,
            runbook_url=self.runbook_url,
            raw_payload=self.dict()
        )

# Prometheus Alertmanager payload  
class PrometheusAlertPayload(BaseModel):
    """Prometheus Alertmanager webhook payload"""
    receiver: Optional[str] = None
    status: str = "firing"  # "firing" or "resolved"
    alerts: List[Dict[str, Any]] = Field(default_factory=list)
    groupLabels: Optional[Dict[str, str]] = Field(default_factory=dict)
    commonLabels: Optional[Dict[str, str]] = Field(default_factory=dict)
    commonAnnotations: Optional[Dict[str, str]] = Field(default_factory=dict)
    externalURL: Optional[str] = None
    version: Optional[str] = None
    groupKey: Optional[str] = None
    truncatedAlerts: Optional[int] = None
    
    def to_generic_alerts(self) -> List[GenericAlertPayload]:
        """Convert Prometheus payload to list of generic alerts"""
        generic_alerts = []
        
        for alert in self.alerts:
            labels = alert.get("labels", {})
            annotations = alert.get("annotations", {})
            
            # Map severity
            severity_map = {
                "critical": AlertSeverity.CRITICAL,
                "warning": AlertSeverity.WARNING, 
                "info": AlertSeverity.INFO,
                "error": AlertSeverity.ERROR
            }
            
            status_map = {
                "firing": AlertStatus.ACTIVE,
                "resolved": AlertStatus.RESOLVED
            }
            
            # Parse timestamps
            started_at = None
            resolved_at = None
            if alert.get("startsAt"):
                try:
                    started_at = datetime.fromisoformat(alert["startsAt"].replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    pass
            if alert.get("endsAt"):
                try:
                    resolved_at = datetime.fromisoformat(alert["endsAt"].replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    pass
            
            generic_alert = GenericAlertPayload(
                alert_id=alert.get("fingerprint", "unknown"),
                title=labels.get("alertname", "Prometheus Alert"),
                description=annotations.get("description") or annotations.get("summary", ""),
                severity=severity_map.get(
                    labels.get("severity", "warning").lower(),
                    AlertSeverity.WARNING
                ),
                status=status_map.get(alert.get("status", self.status), AlertStatus.ACTIVE),
                source=AlertSource.PROMETHEUS,
                service=labels.get("service") or labels.get("job"),
                environment=labels.get("environment") or labels.get("env"),
                region=labels.get("region"),
                host=labels.get("instance"),
                tags=[f"{k}:{v}" for k, v in labels.items()],
                alert_url=alert.get("generatorURL") or self.externalURL,
                runbook_url=annotations.get("runbook_url"),
                dashboard_url=annotations.get("dashboard_url"),
                started_at=started_at,
                resolved_at=resolved_at,
                raw_payload=alert
            )
            
            generic_alerts.append(generic_alert)
        
        return generic_alerts

# PagerDuty webhook payload (for users migrating from PagerDuty)
class PagerDutyWebhookPayload(BaseModel):
    """PagerDuty webhook payload format"""
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    
    def to_generic_alerts(self) -> List[GenericAlertPayload]:
        """Convert PagerDuty messages to generic alerts"""
        generic_alerts = []
        
        for message in self.messages:
            incident = message.get("incident", {})
            
            # Map PagerDuty urgency/priority to severity
            urgency = incident.get("urgency", "low")
            priority = incident.get("priority", {})
            
            severity = AlertSeverity.WARNING
            if urgency == "high":
                severity = AlertSeverity.CRITICAL
            elif priority and priority.get("name") == "P1":
                severity = AlertSeverity.CRITICAL
            elif priority and priority.get("name") == "P2":
                severity = AlertSeverity.ERROR
            
            # Map status
            status_map = {
                "triggered": AlertStatus.ACTIVE,
                "acknowledged": AlertStatus.ACKNOWLEDGED,
                "resolved": AlertStatus.RESOLVED
            }
            
            service = incident.get("service", {})
            
            generic_alert = GenericAlertPayload(
                alert_id=incident.get("id", "unknown"),
                title=incident.get("title", "PagerDuty Incident"),
                description=incident.get("description", ""),
                severity=severity,
                status=status_map.get(incident.get("status"), AlertStatus.ACTIVE),
                source=AlertSource.PAGERDUTY,
                service=service.get("name") if service else None,
                alert_url=incident.get("html_url"),
                started_at=datetime.fromisoformat(incident["created_at"].replace('Z', '+00:00')) if incident.get("created_at") else None,
                raw_payload=message
            )
            
            generic_alerts.append(generic_alert)
        
        return generic_alerts

# Create/Update alert schemas for API
class AlertCreate(BaseModel):
    external_id: str
    title: str
    description: Optional[str] = None
    severity: AlertSeverity
    status: AlertStatus = AlertStatus.ACTIVE
    source: AlertSource
    service_name: Optional[str] = None
    environment: Optional[str] = None
    host: Optional[str] = None
    started_at: Optional[datetime] = None
    labels: Optional[Dict[str, Any]] = None
    raw_data: Optional[Dict[str, Any]] = None

class AlertUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[AlertSeverity] = None
    status: Optional[AlertStatus] = None
    service_name: Optional[str] = None
    environment: Optional[str] = None
    host: Optional[str] = None
    ended_at: Optional[datetime] = None
    labels: Optional[Dict[str, Any]] = None

class AlertListResponse(BaseModel):
    alerts: List[AlertResponse]
    total: int
    page: int
    per_page: int