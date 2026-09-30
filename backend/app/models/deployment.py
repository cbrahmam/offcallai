# backend/app/models/deployment.py - COMPLETE FIXED VERSION
from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, Integer, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from app.database import Base

class DeploymentStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

class DeploymentType(str, enum.Enum):
    HOTFIX = "hotfix"
    ROLLBACK = "rollback"
    ROUTINE = "routine"
    EMERGENCY = "emergency"

class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Deployment details
    name = Column(String(255), nullable=False)
    description = Column(Text)
    deployment_type = Column(Enum(DeploymentType), default=DeploymentType.ROUTINE)
    status = Column(Enum(DeploymentStatus), default=DeploymentStatus.PENDING)
    
    # Source control
    repository_url = Column(String(500))
    branch = Column(String(100))
    commit_hash = Column(String(40))
    
    # Execution details
    deployment_script = Column(Text)  # Commands to run
    completed_steps = Column(Integer, default=0)
    failed_steps = Column(Integer, default=0)
    
    # Execution metadata
    execution_environment = Column(String(100))  # docker, kubernetes, local
    container_id = Column(String(255))  # Docker container ID
    resource_limits = Column(JSONB)  # CPU, memory limits
    
    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Duration in seconds
    total_duration = Column(Integer)  
    estimated_duration = Column(Integer)
    
    # Error handling
    error_message = Column(Text)
    rollback_deployment_id = Column(UUID(as_uuid=True), ForeignKey("deployments.id"))
    
    # Security and compliance
    approval_required = Column(Boolean, default=False)
    approved_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    approved_at = Column(DateTime(timezone=True))
    
    # Relationships
    incident = relationship("Incident", back_populates="deployments")
    organization = relationship("Organization")
    created_by = relationship("User", foreign_keys=[created_by_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    steps = relationship("DeploymentStep", back_populates="deployment", cascade="all, delete-orphan")
    rollback_of = relationship("Deployment", remote_side=[id])

    def __repr__(self):
        return f"<Deployment(id={self.id}, incident_id={self.incident_id}, status={self.status})>"

class DeploymentStep(Base):
    __tablename__ = "deployment_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deployment_id = Column(UUID(as_uuid=True), ForeignKey("deployments.id"), nullable=False)
    
    # Step details
    step_number = Column(Integer, nullable=False)
    name = Column(String(255), nullable=False)
    command = Column(Text, nullable=False)
    status = Column(Enum(DeploymentStatus), default=DeploymentStatus.PENDING)
    
    # Output and timing
    output = Column(Text)
    error_output = Column(Text)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    duration = Column(Integer)  # seconds
    
    # Relationships
    deployment = relationship("Deployment", back_populates="steps")

    def __repr__(self):
        return f"<DeploymentStep(id={self.id}, deployment_id={self.deployment_id}, step={self.step_number})>"