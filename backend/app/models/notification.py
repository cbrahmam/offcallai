# backend/app/models/notification.py - COMPLETE FIXED VERSION
from sqlalchemy import Column, String, DateTime, Boolean, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
import uuid
from app.database import Base

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    
    # Content
    type = Column(String(50), nullable=False)  # incident, alert, system, success, warning, error
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(String(20), nullable=True)  # critical, high, medium, low
    
    # Links
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=True)
    action_url = Column(String(500), nullable=True)
    
    # FIXED: Changed from 'metadata' to 'extra_data' to avoid SQLAlchemy reserved word
    extra_data = Column(JSON, default=dict, nullable=True)
    
    # Status
    read = Column(Boolean, default=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships - ALL PROPERLY DEFINED
    user = relationship("User", back_populates="notifications")
    organization = relationship("Organization", back_populates="notifications")
    incident = relationship("Incident", back_populates="notifications")

    def __repr__(self):
        return f"<Notification(id='{self.id}', type='{self.type}', user_id='{self.user_id}')>"