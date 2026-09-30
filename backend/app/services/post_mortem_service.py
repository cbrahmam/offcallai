# backend/app/services/post_mortem_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from typing import List, Optional, Tuple
from datetime import datetime
from uuid import UUID, uuid4
import logging

from app.models.post_mortem import PostMortem, PostMortemComment, PostMortemStatus as ModelPostMortemStatus
from app.models.incident import Incident
from app.models.user import User
from app.schemas.post_mortem import (
    PostMortemCreate,
    PostMortemUpdate,
    PostMortemResponse,
    PostMortemCommentCreate,
    PostMortemCommentResponse,
    PostMortemStatus as SchemaPostMortemStatus
)

logger = logging.getLogger(__name__)


class PostMortemService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_post_mortem(
        self,
        organization_id: UUID,
        user_id: UUID,
        data: PostMortemCreate
    ) -> PostMortem:
        """Create a new post-mortem"""
        # Verify incident exists and belongs to org
        incident = await self.db.execute(
            select(Incident).where(
                and_(
                    Incident.id == data.incident_id,
                    Incident.organization_id == organization_id
                )
            )
        )
        incident = incident.scalar_one_or_none()
        if not incident:
            raise ValueError("Incident not found")

        # Check if post-mortem already exists for this incident
        existing = await self.db.execute(
            select(PostMortem).where(PostMortem.incident_id == data.incident_id)
        )
        if existing.scalar_one_or_none():
            raise ValueError("Post-mortem already exists for this incident")

        # Convert timeline and action items to dicts
        timeline_data = [event.model_dump() for event in data.timeline] if data.timeline else []
        action_items_data = []
        for item in data.action_items or []:
            item_dict = item.model_dump()
            if not item_dict.get('id'):
                item_dict['id'] = str(uuid4())
            action_items_data.append(item_dict)

        post_mortem = PostMortem(
            organization_id=organization_id,
            incident_id=data.incident_id,
            created_by_id=user_id,
            title=data.title,
            status=ModelPostMortemStatus.DRAFT,
            summary=data.summary,
            impact=data.impact,
            root_cause=data.root_cause,
            resolution=data.resolution,
            lessons_learned=data.lessons_learned,
            timeline=timeline_data,
            action_items=action_items_data,
            detection_time_minutes=data.detection_time_minutes,
            response_time_minutes=data.response_time_minutes,
            resolution_time_minutes=data.resolution_time_minutes,
            total_downtime_minutes=data.total_downtime_minutes,
            assessed_severity=data.assessed_severity,
            customer_impact_score=data.customer_impact_score,
            tags=data.tags,
            contributing_factors=data.contributing_factors
        )

        self.db.add(post_mortem)
        await self.db.commit()
        await self.db.refresh(post_mortem)

        logger.info(f"Created post-mortem: {post_mortem.title} ({post_mortem.id})")
        return post_mortem

    async def get_post_mortem(
        self,
        post_mortem_id: UUID,
        organization_id: UUID
    ) -> Optional[PostMortem]:
        """Get a specific post-mortem"""
        result = await self.db.execute(
            select(PostMortem).where(
                and_(
                    PostMortem.id == post_mortem_id,
                    PostMortem.organization_id == organization_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_post_mortem_by_incident(
        self,
        incident_id: UUID,
        organization_id: UUID
    ) -> Optional[PostMortem]:
        """Get post-mortem for a specific incident"""
        result = await self.db.execute(
            select(PostMortem).where(
                and_(
                    PostMortem.incident_id == incident_id,
                    PostMortem.organization_id == organization_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_post_mortems(
        self,
        organization_id: UUID,
        page: int = 1,
        per_page: int = 20,
        status: Optional[ModelPostMortemStatus] = None,
        search: Optional[str] = None
    ) -> Tuple[List[PostMortem], int]:
        """List post-mortems with pagination"""
        query = select(PostMortem).where(
            PostMortem.organization_id == organization_id
        )

        if status:
            query = query.where(PostMortem.status == status)

        if search:
            query = query.where(PostMortem.title.ilike(f"%{search}%"))

        # Count total
        count_query = select(func.count(PostMortem.id)).where(
            PostMortem.organization_id == organization_id
        )
        if status:
            count_query = count_query.where(PostMortem.status == status)
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # Get paginated results
        query = query.order_by(PostMortem.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await self.db.execute(query)
        post_mortems = result.scalars().all()

        return list(post_mortems), total

    async def update_post_mortem(
        self,
        post_mortem_id: UUID,
        organization_id: UUID,
        data: PostMortemUpdate
    ) -> Optional[PostMortem]:
        """Update a post-mortem"""
        post_mortem = await self.get_post_mortem(post_mortem_id, organization_id)
        if not post_mortem:
            return None

        update_data = data.model_dump(exclude_unset=True)

        # Handle timeline conversion
        if 'timeline' in update_data and update_data['timeline']:
            update_data['timeline'] = [
                event.model_dump() if hasattr(event, 'model_dump') else event
                for event in update_data['timeline']
            ]

        # Handle action items conversion
        if 'action_items' in update_data and update_data['action_items']:
            action_items = []
            for item in update_data['action_items']:
                item_dict = item.model_dump() if hasattr(item, 'model_dump') else item
                if not item_dict.get('id'):
                    item_dict['id'] = str(uuid4())
                action_items.append(item_dict)
            update_data['action_items'] = action_items

        for field, value in update_data.items():
            setattr(post_mortem, field, value)

        await self.db.commit()
        await self.db.refresh(post_mortem)

        logger.info(f"Updated post-mortem: {post_mortem.title} ({post_mortem.id})")
        return post_mortem

    async def submit_for_review(
        self,
        post_mortem_id: UUID,
        organization_id: UUID
    ) -> Optional[PostMortem]:
        """Submit post-mortem for review"""
        post_mortem = await self.get_post_mortem(post_mortem_id, organization_id)
        if not post_mortem:
            return None

        post_mortem.status = ModelPostMortemStatus.IN_REVIEW
        await self.db.commit()
        await self.db.refresh(post_mortem)

        logger.info(f"Post-mortem submitted for review: {post_mortem.id}")
        return post_mortem

    async def publish_post_mortem(
        self,
        post_mortem_id: UUID,
        organization_id: UUID,
        user_id: UUID
    ) -> Optional[PostMortem]:
        """Publish a post-mortem"""
        post_mortem = await self.get_post_mortem(post_mortem_id, organization_id)
        if not post_mortem:
            return None

        post_mortem.status = ModelPostMortemStatus.PUBLISHED
        post_mortem.published_by_id = user_id
        post_mortem.published_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(post_mortem)

        logger.info(f"Post-mortem published: {post_mortem.id}")
        return post_mortem

    async def archive_post_mortem(
        self,
        post_mortem_id: UUID,
        organization_id: UUID
    ) -> Optional[PostMortem]:
        """Archive a post-mortem"""
        post_mortem = await self.get_post_mortem(post_mortem_id, organization_id)
        if not post_mortem:
            return None

        post_mortem.status = ModelPostMortemStatus.ARCHIVED
        await self.db.commit()
        await self.db.refresh(post_mortem)

        logger.info(f"Post-mortem archived: {post_mortem.id}")
        return post_mortem

    async def delete_post_mortem(
        self,
        post_mortem_id: UUID,
        organization_id: UUID
    ) -> bool:
        """Delete a post-mortem"""
        post_mortem = await self.get_post_mortem(post_mortem_id, organization_id)
        if not post_mortem:
            return False

        await self.db.delete(post_mortem)
        await self.db.commit()

        logger.info(f"Deleted post-mortem: {post_mortem_id}")
        return True

    async def add_comment(
        self,
        post_mortem_id: UUID,
        organization_id: UUID,
        user_id: UUID,
        data: PostMortemCommentCreate
    ) -> Optional[PostMortemComment]:
        """Add a comment to a post-mortem"""
        post_mortem = await self.get_post_mortem(post_mortem_id, organization_id)
        if not post_mortem:
            return None

        comment = PostMortemComment(
            post_mortem_id=post_mortem_id,
            user_id=user_id,
            content=data.content,
            section=data.section
        )

        self.db.add(comment)
        await self.db.commit()
        await self.db.refresh(comment)

        return comment

    async def get_comments(
        self,
        post_mortem_id: UUID,
        organization_id: UUID
    ) -> List[PostMortemComment]:
        """Get all comments for a post-mortem"""
        # First verify post-mortem belongs to org
        post_mortem = await self.get_post_mortem(post_mortem_id, organization_id)
        if not post_mortem:
            return []

        result = await self.db.execute(
            select(PostMortemComment)
            .where(PostMortemComment.post_mortem_id == post_mortem_id)
            .order_by(PostMortemComment.created_at.asc())
        )

        return list(result.scalars().all())

    async def update_action_item_status(
        self,
        post_mortem_id: UUID,
        organization_id: UUID,
        action_item_id: str,
        status: str
    ) -> Optional[PostMortem]:
        """Update the status of an action item"""
        post_mortem = await self.get_post_mortem(post_mortem_id, organization_id)
        if not post_mortem:
            return None

        action_items = post_mortem.action_items or []
        for item in action_items:
            if item.get('id') == action_item_id:
                item['status'] = status
                break

        post_mortem.action_items = action_items
        await self.db.commit()
        await self.db.refresh(post_mortem)

        return post_mortem

    async def generate_post_mortem_with_ai(
        self,
        incident_id: UUID,
        organization_id: UUID,
        user_id: UUID
    ) -> Optional[PostMortem]:
        """
        Generate a post-mortem using AI based on incident data.
        Creates a draft post-mortem with AI-generated sections.
        """
        # Get incident with related data
        result = await self.db.execute(
            select(Incident).where(
                and_(
                    Incident.id == incident_id,
                    Incident.organization_id == organization_id
                )
            )
        )
        incident = result.scalar_one_or_none()
        if not incident:
            raise ValueError("Incident not found")

        # Check if post-mortem already exists
        existing = await self.get_post_mortem_by_incident(incident_id, organization_id)
        if existing:
            raise ValueError("Post-mortem already exists for this incident")

        # Get incident alerts for more context
        from app.models.alert import Alert
        alerts_result = await self.db.execute(
            select(Alert).where(Alert.incident_id == incident_id)
        )
        alerts = alerts_result.scalars().all()

        # Get audit logs for timeline
        from app.models.audit_log import AuditLog
        audit_result = await self.db.execute(
            select(AuditLog)
            .where(AuditLog.incident_id == incident_id)
            .order_by(AuditLog.created_at.asc())
        )
        audit_logs = audit_result.scalars().all()

        # Build context for AI
        incident_context = {
            "title": incident.title,
            "description": incident.description,
            "severity": incident.severity if isinstance(incident.severity, str) else incident.severity.value,
            "status": incident.status if isinstance(incident.status, str) else incident.status.value,
            "created_at": incident.created_at.isoformat() if incident.created_at else None,
            "acknowledged_at": incident.acknowledged_at.isoformat() if incident.acknowledged_at else None,
            "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
            "tags": incident.tags or [],
            "alerts": [
                {
                    "title": a.title,
                    "description": a.description,
                    "severity": a.severity.value if hasattr(a.severity, 'value') else str(a.severity),
                    "source": a.source,
                    "service_name": a.service_name
                }
                for a in alerts
            ],
            "timeline_events": [
                {
                    "action": log.action,
                    "description": log.description,
                    "timestamp": log.created_at.isoformat() if log.created_at else None
                }
                for log in audit_logs
            ]
        }

        # Generate AI content
        ai_content = await self._generate_ai_post_mortem_content(incident_context, organization_id)

        # Calculate time metrics
        detection_time = None
        response_time = None
        resolution_time = None
        total_downtime = None

        if incident.created_at:
            if incident.acknowledged_at:
                response_time = int((incident.acknowledged_at - incident.created_at).total_seconds() / 60)
            if incident.resolved_at:
                resolution_time = int((incident.resolved_at - incident.created_at).total_seconds() / 60)
                total_downtime = resolution_time

        # Create the post-mortem
        post_mortem = PostMortem(
            organization_id=organization_id,
            incident_id=incident_id,
            created_by_id=user_id,
            title=f"Post-Mortem: {incident.title}",
            status=ModelPostMortemStatus.DRAFT,
            summary=ai_content.get("summary", ""),
            impact=ai_content.get("impact", ""),
            root_cause=ai_content.get("root_cause", ""),
            resolution=ai_content.get("resolution", ""),
            lessons_learned=ai_content.get("lessons_learned", ""),
            timeline=ai_content.get("timeline", []),
            action_items=ai_content.get("action_items", []),
            contributing_factors=ai_content.get("contributing_factors", []),
            detection_time_minutes=detection_time,
            response_time_minutes=response_time,
            resolution_time_minutes=resolution_time,
            total_downtime_minutes=total_downtime,
            assessed_severity=incident.severity if isinstance(incident.severity, str) else incident.severity.value,
            tags=["ai-generated"] + (incident.tags or [])
        )

        self.db.add(post_mortem)
        await self.db.commit()
        await self.db.refresh(post_mortem)

        logger.info(f"Generated AI post-mortem for incident {incident_id}: {post_mortem.id}")
        return post_mortem

    async def _generate_ai_post_mortem_content(
        self,
        incident_context: dict,
        organization_id: UUID
    ) -> dict:
        """
        Use AI to generate post-mortem sections.
        Falls back to template if AI is not available.
        """
        try:
            from app.services.real_ai_service import RealAIService

            ai_service = RealAIService(db=self.db, organization_id=str(organization_id))
            await ai_service.load_user_api_keys()

            prompt = f"""Based on the following incident data, generate a comprehensive post-mortem report.
Return a JSON object with these sections:

1. summary: A 2-3 paragraph executive summary of the incident
2. impact: Description of customer/business impact
3. root_cause: Technical root cause analysis
4. resolution: How the incident was resolved
5. lessons_learned: Key takeaways and learnings
6. timeline: Array of objects with {{timestamp, event, description}}
7. action_items: Array of objects with {{id, title, description, priority, status, assignee}}
8. contributing_factors: Array of strings listing factors that contributed

Incident Data:
{incident_context}

Return ONLY valid JSON, no markdown or explanation."""

            # Try Claude first
            if ai_service.claude_enabled:
                try:
                    import json
                    response = await ai_service._call_claude_api(prompt, max_tokens=4000)
                    if response:
                        # Parse the JSON response
                        content = json.loads(response)
                        return self._validate_ai_response(content)
                except Exception as e:
                    logger.warning(f"Claude AI generation failed: {e}")

            # Try Gemini as fallback
            if ai_service.gemini_enabled:
                try:
                    import json
                    response = await ai_service._call_gemini_api(prompt)
                    if response:
                        content = json.loads(response)
                        return self._validate_ai_response(content)
                except Exception as e:
                    logger.warning(f"Gemini AI generation failed: {e}")

        except Exception as e:
            logger.error(f"AI post-mortem generation error: {e}")

        # Fallback to template-based generation
        return self._generate_template_post_mortem(incident_context)

    def _validate_ai_response(self, content: dict) -> dict:
        """Validate and clean AI response"""
        result = {
            "summary": content.get("summary", ""),
            "impact": content.get("impact", ""),
            "root_cause": content.get("root_cause", ""),
            "resolution": content.get("resolution", ""),
            "lessons_learned": content.get("lessons_learned", ""),
            "timeline": [],
            "action_items": [],
            "contributing_factors": []
        }

        # Validate timeline
        for event in content.get("timeline", []):
            if isinstance(event, dict):
                result["timeline"].append({
                    "timestamp": event.get("timestamp", ""),
                    "event": event.get("event", ""),
                    "description": event.get("description", "")
                })

        # Validate action items
        for i, item in enumerate(content.get("action_items", [])):
            if isinstance(item, dict):
                result["action_items"].append({
                    "id": item.get("id", str(uuid4())),
                    "title": item.get("title", f"Action Item {i+1}"),
                    "description": item.get("description", ""),
                    "priority": item.get("priority", "medium"),
                    "status": item.get("status", "pending"),
                    "assignee": item.get("assignee")
                })

        # Validate contributing factors
        for factor in content.get("contributing_factors", []):
            if isinstance(factor, str):
                result["contributing_factors"].append(factor)

        return result

    def _generate_template_post_mortem(self, incident_context: dict) -> dict:
        """Generate template-based post-mortem when AI is not available"""
        title = incident_context.get("title", "Unknown Incident")
        severity = incident_context.get("severity", "unknown")
        description = incident_context.get("description", "")

        # Build timeline from audit events
        timeline = []
        for event in incident_context.get("timeline_events", []):
            timeline.append({
                "timestamp": event.get("timestamp", ""),
                "event": event.get("action", ""),
                "description": event.get("description", "")
            })

        return {
            "summary": f"This post-mortem documents the {severity} severity incident: {title}.\n\n{description}\n\n[Please review and update this AI-generated summary]",
            "impact": "[Please describe the customer and business impact of this incident]",
            "root_cause": "[Please document the root cause analysis]",
            "resolution": "[Please describe how this incident was resolved]",
            "lessons_learned": "[Please document key learnings from this incident]",
            "timeline": timeline,
            "action_items": [
                {
                    "id": str(uuid4()),
                    "title": "Review and update this post-mortem",
                    "description": "Review the AI-generated content and update with accurate details",
                    "priority": "high",
                    "status": "pending",
                    "assignee": None
                },
                {
                    "id": str(uuid4()),
                    "title": "Identify preventive measures",
                    "description": "Document actions to prevent similar incidents",
                    "priority": "medium",
                    "status": "pending",
                    "assignee": None
                }
            ],
            "contributing_factors": []
        }

    async def to_response(
        self,
        post_mortem: PostMortem,
        include_incident: bool = True
    ) -> PostMortemResponse:
        """Convert model to response schema"""
        # Get creator name
        creator_name = None
        if post_mortem.created_by_id:
            creator = await self.db.execute(
                select(User).where(User.id == post_mortem.created_by_id)
            )
            creator = creator.scalar_one_or_none()
            if creator:
                creator_name = creator.full_name

        # Get reviewer name
        reviewer_name = None
        if post_mortem.reviewed_by_id:
            reviewer = await self.db.execute(
                select(User).where(User.id == post_mortem.reviewed_by_id)
            )
            reviewer = reviewer.scalar_one_or_none()
            if reviewer:
                reviewer_name = reviewer.full_name

        # Get incident info
        incident_title = None
        incident_severity = None
        if include_incident:
            incident = await self.db.execute(
                select(Incident).where(Incident.id == post_mortem.incident_id)
            )
            incident = incident.scalar_one_or_none()
            if incident:
                incident_title = incident.title
                if incident.severity:
                    incident_severity = incident.severity if isinstance(incident.severity, str) else incident.severity.value
                else:
                    incident_severity = None

        # Convert status to schema enum
        status_value = post_mortem.status.value if hasattr(post_mortem.status, 'value') else str(post_mortem.status)
        schema_status = SchemaPostMortemStatus(status_value)

        return PostMortemResponse(
            id=post_mortem.id,
            organization_id=post_mortem.organization_id,
            incident_id=post_mortem.incident_id,
            title=post_mortem.title,
            status=schema_status,
            summary=post_mortem.summary,
            impact=post_mortem.impact,
            root_cause=post_mortem.root_cause,
            resolution=post_mortem.resolution,
            lessons_learned=post_mortem.lessons_learned,
            timeline=post_mortem.timeline or [],
            action_items=post_mortem.action_items or [],
            detection_time_minutes=post_mortem.detection_time_minutes,
            response_time_minutes=post_mortem.response_time_minutes,
            resolution_time_minutes=post_mortem.resolution_time_minutes,
            total_downtime_minutes=post_mortem.total_downtime_minutes,
            assessed_severity=post_mortem.assessed_severity,
            customer_impact_score=post_mortem.customer_impact_score,
            tags=post_mortem.tags or [],
            contributing_factors=post_mortem.contributing_factors or [],
            created_by_id=post_mortem.created_by_id,
            created_by_name=creator_name,
            reviewed_by_id=post_mortem.reviewed_by_id,
            reviewed_by_name=reviewer_name,
            reviewed_at=post_mortem.reviewed_at,
            published_by_id=post_mortem.published_by_id,
            published_at=post_mortem.published_at,
            created_at=post_mortem.created_at,
            updated_at=post_mortem.updated_at,
            incident_title=incident_title,
            incident_severity=incident_severity
        )
