# backend/app/schemas/post_mortem.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


class PostMortemStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class TimelineEvent(BaseModel):
    """A single event in the incident timeline"""
    time: datetime
    description: str
    actor: Optional[str] = None  # Who/what performed the action


class ActionItem(BaseModel):
    """A follow-up action item"""
    id: Optional[str] = None
    description: str
    assignee_id: Optional[UUID] = None
    assignee_name: Optional[str] = None
    due_date: Optional[datetime] = None
    status: str = "open"  # open, in_progress, completed
    priority: str = "medium"  # low, medium, high


class PostMortemCreate(BaseModel):
    """Schema for creating a post-mortem"""
    incident_id: UUID
    title: str = Field(..., min_length=1, max_length=255)
    summary: Optional[str] = None
    impact: Optional[str] = None
    root_cause: Optional[str] = None
    resolution: Optional[str] = None
    lessons_learned: Optional[str] = None
    timeline: List[TimelineEvent] = Field(default_factory=list)
    action_items: List[ActionItem] = Field(default_factory=list)
    detection_time_minutes: Optional[int] = None
    response_time_minutes: Optional[int] = None
    resolution_time_minutes: Optional[int] = None
    total_downtime_minutes: Optional[int] = None
    assessed_severity: Optional[str] = None
    customer_impact_score: Optional[int] = Field(None, ge=1, le=10)
    tags: List[str] = Field(default_factory=list)
    contributing_factors: List[str] = Field(default_factory=list)


class PostMortemUpdate(BaseModel):
    """Schema for updating a post-mortem"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    status: Optional[PostMortemStatus] = None
    summary: Optional[str] = None
    impact: Optional[str] = None
    root_cause: Optional[str] = None
    resolution: Optional[str] = None
    lessons_learned: Optional[str] = None
    timeline: Optional[List[TimelineEvent]] = None
    action_items: Optional[List[ActionItem]] = None
    detection_time_minutes: Optional[int] = None
    response_time_minutes: Optional[int] = None
    resolution_time_minutes: Optional[int] = None
    total_downtime_minutes: Optional[int] = None
    assessed_severity: Optional[str] = None
    customer_impact_score: Optional[int] = Field(None, ge=1, le=10)
    tags: Optional[List[str]] = None
    contributing_factors: Optional[List[str]] = None


class PostMortemResponse(BaseModel):
    """Schema for post-mortem response"""
    id: UUID
    organization_id: UUID
    incident_id: UUID
    title: str
    status: PostMortemStatus
    summary: Optional[str]
    impact: Optional[str]
    root_cause: Optional[str]
    resolution: Optional[str]
    lessons_learned: Optional[str]
    timeline: List[Dict[str, Any]]
    action_items: List[Dict[str, Any]]
    detection_time_minutes: Optional[int]
    response_time_minutes: Optional[int]
    resolution_time_minutes: Optional[int]
    total_downtime_minutes: Optional[int]
    assessed_severity: Optional[str]
    customer_impact_score: Optional[int]
    tags: List[str]
    contributing_factors: List[str]
    created_by_id: UUID
    created_by_name: Optional[str] = None
    reviewed_by_id: Optional[UUID]
    reviewed_by_name: Optional[str] = None
    reviewed_at: Optional[datetime]
    published_by_id: Optional[UUID]
    published_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    # Include incident info
    incident_title: Optional[str] = None
    incident_severity: Optional[str] = None

    class Config:
        from_attributes = True


class PostMortemListResponse(BaseModel):
    """Schema for paginated post-mortem list"""
    post_mortems: List[PostMortemResponse]
    total: int
    page: int
    per_page: int


class PostMortemCommentCreate(BaseModel):
    """Schema for creating a comment"""
    content: str = Field(..., min_length=1)
    section: Optional[str] = None  # summary, root_cause, impact, etc.


class PostMortemCommentResponse(BaseModel):
    """Schema for comment response"""
    id: UUID
    post_mortem_id: UUID
    user_id: UUID
    user_name: Optional[str] = None
    content: str
    section: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class GeneratePostMortemRequest(BaseModel):
    """Request to generate post-mortem content using AI"""
    incident_id: UUID
    sections: List[str] = Field(
        default=["summary", "timeline", "root_cause", "impact", "resolution"],
        description="Sections to generate"
    )
