# backend/app/models/api_keys.py - FIXED VERSION
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base
import uuid
from datetime import datetime

class APIKey(Base):
    __tablename__ = "api_keys"
    
    # FIXED: Use UUID type to match other tables
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Key details
    provider = Column(String, nullable=False)  # "gemini", "claude", "openai", "azure"
    key_name = Column(String, nullable=False)  # User-friendly name
    encrypted_key = Column(Text, nullable=False)  # Encrypted API key
    
    # Validation and status
    is_valid = Column(Boolean, default=False)
    last_validated = Column(DateTime, nullable=True)
    validation_error = Column(Text, nullable=True)
    
    # Usage tracking
    total_requests = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    last_used = Column(DateTime, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    organization = relationship("Organization", back_populates="api_keys")
    user = relationship("User")