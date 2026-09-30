from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.database import Base

# Many-to-many table for team members
team_members = Table(
    'team_members',
    Base.metadata,
    Column('team_id', UUID(as_uuid=True), ForeignKey('teams.id'), primary_key=True),
    Column('user_id', UUID(as_uuid=True), ForeignKey('users.id'), primary_key=True),
    Column('role', String(50), default='member'),
    Column('joined_at', DateTime(timezone=True), server_default=func.now())
)

class Team(Base):
    __tablename__ = "teams"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    
    name = Column(String(255), nullable=False)
    description = Column(String(500))
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization", back_populates="teams")
    members = relationship("User", secondary=team_members, back_populates="teams")
    on_call_schedules = relationship("OnCallSchedule", back_populates="team")
    services = relationship("Service", back_populates="team")