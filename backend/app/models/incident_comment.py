# backend/app/models/incident_comment.py
"""Comments posted on an incident during response."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database import Base


class IncidentComment(Base):
    __tablename__ = "incident_comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    content = Column(Text, nullable=False)

    # Internal comments are for responders only; the distinction matters once a
    # comment stream is surfaced on a public status page.
    is_internal = Column(Boolean, default=False, nullable=False, server_default="false")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    incident = relationship("Incident", backref="comments")
    user = relationship("User")

    def __repr__(self):
        return f"<IncidentComment(incident_id='{self.incident_id}')>"
