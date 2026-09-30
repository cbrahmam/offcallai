from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from app.database import Base

class IntegrationType(str, enum.Enum):
    # Monitoring platforms (data ingestion)
    DATADOG = "datadog"
    PROMETHEUS = "prometheus"
    NEWRELIC = "newrelic"
    SPLUNK = "splunk"
    GRAFANA = "grafana"
    CLOUDWATCH = "cloudwatch"
    AZURE_MONITOR = "azure_monitor"
    PAGERDUTY = "pagerduty"
    OPSGENIE = "opsgenie"
    VICTOROPS = "victorops"
    ZABBIX = "zabbix"
    NAGIOS = "nagios"
    ELASTIC = "elastic"
    SUMOLOGIC = "sumologic"
    DYNATRACE = "dynatrace"

    # Notification channels
    SLACK = "slack"
    TEAMS = "teams"
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"  # Generic webhook for internal use
    DISCORD = "discord"
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"  # WhatsApp Business API

    # CI/CD & DevOps
    GITHUB = "github"
    GITLAB = "gitlab"
    JIRA = "jira"
    CONFLUENCE = "confluence"
    JENKINS = "jenkins"
    CIRCLECI = "circleci"

    # Cloud providers
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"

    # Custom/Other
    CUSTOM = "custom"
class Integration(Base):
    __tablename__ = "integrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    
    # Integration details
    name = Column(String(255), nullable=False)
    type = Column(Enum(IntegrationType), nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Configuration (encrypted)
    config = Column(JSONB, nullable=False)  # API keys, endpoints, etc.
    webhook_url = Column(String(500))  # For incoming webhooks
    webhook_secret = Column(String(255))  # For webhook verification
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_sync_at = Column(DateTime(timezone=True))
    
    # Relationships
    organization = relationship("Organization", back_populates="integrations")
    alerts = relationship("Alert", back_populates="integration")
