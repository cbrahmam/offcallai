# backend/app/models/post_mortem.py
from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, Integer, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from app.database import Base


class PostMortemStatus(str, enum.Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class PostMortem(Base):
    """Post-mortem analysis for incidents"""
    __tablename__ = "post_mortems"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False)

    # Basic info
    title = Column(String(255), nullable=False)
    status = Column(Enum(PostMortemStatus, values_callable=lambda x: [e.value for e in x]), default=PostMortemStatus.DRAFT, nullable=False)

    # Content sections (markdown supported)
    summary = Column(Text)  # Executive summary of what happened
    impact = Column(Text)  # Business/user impact description
    root_cause = Column(Text)  # Root cause analysis
    resolution = Column(Text)  # How the incident was resolved
    lessons_learned = Column(Text)  # Key takeaways

    # Timeline events stored as JSON array
    # [{"time": "2024-01-01T10:00:00Z", "description": "Alert triggered", "actor": "System"}]
    timeline = Column(JSONB, default=list)

    # Action items stored as JSON array
    # [{"id": "uuid", "description": "Add monitoring", "assignee_id": "uuid", "due_date": "2024-01-15", "status": "open"}]
    action_items = Column(JSONB, default=list)

    # Metrics
    detection_time_minutes = Column(Integer)  # Time to detect
    response_time_minutes = Column(Integer)  # Time to respond
    resolution_time_minutes = Column(Integer)  # Time to resolve
    total_downtime_minutes = Column(Integer)  # Total downtime

    # Severity assessment (may differ from incident severity after analysis)
    assessed_severity = Column(String(20))  # low, medium, high, critical
    customer_impact_score = Column(Integer)  # 1-10 scale

    # Tags for categorization
    tags = Column(JSONB, default=list)  # ["database", "outage", "human-error"]
    contributing_factors = Column(JSONB, default=list)  # ["lack of monitoring", "missing runbook"]

    # Review workflow
    reviewed_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    reviewed_at = Column(DateTime(timezone=True))
    published_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    published_at = Column(DateTime(timezone=True))

    # Audit
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="post_mortems")
    incident = relationship("Incident", back_populates="post_mortem")
    created_by = relationship("User", foreign_keys=[created_by_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])
    published_by = relationship("User", foreign_keys=[published_by_id])

    def __repr__(self):
        return f"<PostMortem(title='{self.title}', status='{self.status}')>"


class PostMortemComment(Base):
    """Comments on post-mortems for collaboration"""
    __tablename__ = "post_mortem_comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_mortem_id = Column(UUID(as_uuid=True), ForeignKey("post_mortems.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    content = Column(Text, nullable=False)
    section = Column(String(50))  # Which section the comment is about: summary, root_cause, etc.

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    post_mortem = relationship("PostMortem", backref="comments")
    user = relationship("User")

    def __repr__(self):
        return f"<PostMortemComment(post_mortem_id='{self.post_mortem_id}')>"
