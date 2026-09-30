from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from app.database import Base


class DeploymentStatus(str, enum.Enum):
    """Status of a deployment."""
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"


class DeploymentEvent(Base):
    """
    Track deployments from CI/CD systems.

    Enables:
    - CI/CD webhook integration
    - "3 incidents occurred within 30 min of this deploy" correlation
    - Deployment timeline visualization
    - Change correlation for root cause analysis
    """
    __tablename__ = "deployment_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )

    # Core deployment info
    service_name = Column(String(255), nullable=False)
    version = Column(String(100), nullable=False)
    environment = Column(String(50), nullable=False, default="production")
    deployed_by = Column(String(255))  # User email or CI system name
    deployed_at = Column(DateTime(timezone=True), server_default=func.now())

    # Source control info
    commit_sha = Column(String(40))
    commit_message = Column(Text)
    branch = Column(String(100))
    repository = Column(String(500))
    pull_request_url = Column(String(500))
    pull_request_number = Column(Integer)

    # Deployment status
    status = Column(
        Enum(DeploymentStatus),
        nullable=False,
        default=DeploymentStatus.SUCCESS
    )
    duration_seconds = Column(Integer)
    rollback_of = Column(UUID(as_uuid=True))  # Reference to deployment being rolled back

    # Correlation data (populated by correlation service)
    incidents_within_30min = Column(Integer, default=0)
    alerts_within_30min = Column(Integer, default=0)
    correlated_incident_ids = Column(ARRAY(UUID(as_uuid=True)))
    correlated_alert_ids = Column(ARRAY(UUID(as_uuid=True)))

    # Metadata
    tags = Column(JSONB, default=dict)
    extra_data = Column(JSONB, default=dict)  # CI/CD specific data (build URL, etc.)
    description = Column(Text)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", backref="deployment_events")
