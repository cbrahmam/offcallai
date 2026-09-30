# backend/app/models/agent_api_key.py
"""
Ingest credentials used by the Go agent and the error/RUM SDKs.

Distinct from APIKey in api_keys.py, which stores an organization's *outbound*
AI provider keys. These are inbound: the agent, the error SDKs and the
Sentry-compatible endpoint all authenticate with one of these keys, and only
its SHA-256 hash is stored.

Access goes through raw SQL in host_service.py, errors.py and sentry_ingest.py;
this model exists so the table is created by migrations.
"""
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid

from app.database import Base


class AgentAPIKey(Base):
    __tablename__ = "agent_api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # SHA-256 of the key; the plaintext is shown once at creation and never stored.
    key_hash = Column(String(64), nullable=False, unique=True, index=True)
    key_prefix = Column(String(16), nullable=False)

    tags = Column(JSONB, default=dict)

    is_active = Column(Boolean, default=True, nullable=False, server_default="true")
    use_count = Column(Integer, default=0, nullable=False, server_default="0")
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<AgentAPIKey(name='{self.name}', prefix='{self.key_prefix}')>"
