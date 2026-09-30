# backend/app/models/ai_chat.py
from sqlalchemy import Column, String, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database import Base

class AIChatSession(Base):
    __tablename__ = "ai_chat_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey('incidents.id'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False)
    title = Column(String(255), nullable=True)
    is_encrypted = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    messages = relationship("AIChatMessage", back_populates="session", cascade="all, delete-orphan")
    incident = relationship("Incident")
    user = relationship("User")

class AIChatMessage(Base):
    __tablename__ = "ai_chat_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey('ai_chat_sessions.id', ondelete='CASCADE'), nullable=False)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    provider = Column(String(20), nullable=True)  # 'claude', 'gemini', 'both'
    attachments = Column(JSONB, nullable=True)  # For images/files
    message_metadata = Column(JSONB, nullable=True)  # Renamed from metadata to avoid SQLAlchemy conflicts
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    session = relationship("AIChatSession", back_populates="messages")