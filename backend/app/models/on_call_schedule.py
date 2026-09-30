from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.database import Base


class OnCallSchedule(Base):
    """On-call schedule definition for a team or organization."""
    __tablename__ = "on_call_schedules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=True)

    # Schedule details
    name = Column(String(255), nullable=False)
    description = Column(Text)
    timezone = Column(String(50), default="UTC", nullable=False)
    is_active = Column(Boolean, default=True)

    # Optional escalation policy
    escalation_policy_id = Column(UUID(as_uuid=True), ForeignKey("escalation_policies.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="on_call_schedules")
    team = relationship("Team", back_populates="on_call_schedules")
    shifts = relationship("OnCallShift", back_populates="schedule", cascade="all, delete-orphan")
    escalation_policy = relationship("EscalationPolicy", back_populates="on_call_schedules")
    created_by = relationship("User", foreign_keys=[created_by_id])
