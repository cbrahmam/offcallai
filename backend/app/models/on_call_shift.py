from sqlalchemy import Column, String, Integer, DateTime, Time, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.database import Base


class OnCallShift(Base):
    """Individual shift within an on-call schedule."""
    __tablename__ = "on_call_shifts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schedule_id = Column(UUID(as_uuid=True), ForeignKey("on_call_schedules.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Shift type: "recurring" (weekly pattern) or "one_time" (specific dates)
    shift_type = Column(String(20), default="recurring", nullable=False)

    # For recurring shifts (weekly pattern)
    # 0=Monday, 1=Tuesday, ..., 6=Sunday
    day_of_week = Column(Integer, nullable=True)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)

    # For one-time shifts (specific datetime range)
    start_datetime = Column(DateTime(timezone=True), nullable=True)
    end_datetime = Column(DateTime(timezone=True), nullable=True)

    # Notification preferences (can override user defaults)
    # ["email", "sms", "slack", "push"]
    notify_channels = Column(JSONB, default=list)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    schedule = relationship("OnCallSchedule", back_populates="shifts")
    user = relationship("User", back_populates="on_call_shifts")
