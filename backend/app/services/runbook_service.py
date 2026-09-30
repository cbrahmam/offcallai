# backend/app/services/runbook_service.py
"""
Runbook service for managing runbooks and their executions.
"""

import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from sqlalchemy import select, func, desc, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.runbook import Runbook
from app.models.runbook_execution import RunbookExecution, RunbookExecutionStatus, RunbookTriggerType
from app.models.incident import Incident
from app.models.alert import Alert
from app.models.user import User
from app.models.deployment import Deployment, DeploymentStep, DeploymentStatus, DeploymentType
from app.models.audit_log import AuditLog
from app.services.pattern_matcher import pattern_matcher, RunbookMatch
from app.services.runbook_parser import runbook_parser, ParsedRunbook
from app.schemas.runbook import (
    RunbookCreate, RunbookUpdate, RunbookExecuteRequest,
    RunbookSuggestion, RunbookResponse
)

logger = logging.getLogger(__name__)


class RunbookService:
    """Service for runbook operations."""

    # CRUD Operations

    async def create_runbook(
        self,
        data: RunbookCreate,
        user: User,
        db: AsyncSession
    ) -> Runbook:
        """Create a new runbook."""
        runbook_id = uuid.uuid4()

        # Convert alert_patterns to list of dicts
        alert_patterns = [
            {"field": p.field.value, "operator": p.operator.value, "value": p.value}
            for p in data.alert_patterns
        ]

        runbook = Runbook(
            id=runbook_id,
            organization_id=user.organization_id,
            created_by_id=user.id,
            title=data.title,
            description=data.description,
            content=data.content,
            tags=data.tags,
            service_names=data.service_names,
            alert_patterns=alert_patterns,
            is_active=data.is_active,
            usage_count=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        db.add(runbook)

        # Create audit log
        audit_log = AuditLog(
            id=uuid.uuid4(),
            organization_id=user.organization_id,
            user_id=user.id,
            action="runbook_created",
            description=f"Runbook created: {data.title}",
            details={"runbook_id": str(runbook_id), "title": data.title},
            created_at=datetime.utcnow()
        )
        db.add(audit_log)

        await db.commit()
        await db.refresh(runbook)

        logger.info(f"Created runbook {runbook_id}: {data.title}")
        return runbook

    async def get_runbook(
        self,
        runbook_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[Runbook]:
        """Get a runbook by ID."""
        result = await db.execute(
            select(Runbook)
            .options(selectinload(Runbook.created_by))
            .where(
                Runbook.id == runbook_id,
                Runbook.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_runbooks(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession,
        page: int = 1,
        per_page: int = 20,
        is_active: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        service_name: Optional[str] = None,
        search: Optional[str] = None
    ) -> Tuple[List[Runbook], int]:
        """List runbooks with filtering and pagination."""
        query = select(Runbook).where(
            Runbook.organization_id == organization_id
        ).options(selectinload(Runbook.created_by))

        # Apply filters
        if is_active is not None:
            query = query.where(Runbook.is_active == is_active)

        if tags:
            # Filter by any matching tag
            for tag in tags:
                query = query.where(Runbook.tags.contains([tag]))

        if service_name:
            query = query.where(Runbook.service_names.contains([service_name]))

        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                (Runbook.title.ilike(search_pattern)) |
                (Runbook.description.ilike(search_pattern))
            )

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Apply pagination and ordering
        query = query.order_by(desc(Runbook.updated_at))
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await db.execute(query)
        runbooks = result.scalars().all()

        return list(runbooks), total

    async def update_runbook(
        self,
        runbook_id: uuid.UUID,
        data: RunbookUpdate,
        user: User,
        db: AsyncSession
    ) -> Optional[Runbook]:
        """Update a runbook."""
        runbook = await self.get_runbook(runbook_id, user.organization_id, db)
        if not runbook:
            return None

        # Update fields
        update_data = data.model_dump(exclude_unset=True)

        if "alert_patterns" in update_data and update_data["alert_patterns"] is not None:
            update_data["alert_patterns"] = [
                {"field": p.field.value, "operator": p.operator.value, "value": p.value}
                for p in data.alert_patterns
            ]

        for field, value in update_data.items():
            setattr(runbook, field, value)

        runbook.updated_at = datetime.utcnow()

        # Create audit log
        audit_log = AuditLog(
            id=uuid.uuid4(),
            organization_id=user.organization_id,
            user_id=user.id,
            action="runbook_updated",
            description=f"Runbook updated: {runbook.title}",
            details={"runbook_id": str(runbook_id), "changes": list(update_data.keys())},
            created_at=datetime.utcnow()
        )
        db.add(audit_log)

        await db.commit()
        await db.refresh(runbook)

        logger.info(f"Updated runbook {runbook_id}")
        return runbook

    async def delete_runbook(
        self,
        runbook_id: uuid.UUID,
        user: User,
        db: AsyncSession
    ) -> bool:
        """Delete a runbook."""
        runbook = await self.get_runbook(runbook_id, user.organization_id, db)
        if not runbook:
            return False

        # Create audit log before deletion
        audit_log = AuditLog(
            id=uuid.uuid4(),
            organization_id=user.organization_id,
            user_id=user.id,
            action="runbook_deleted",
            description=f"Runbook deleted: {runbook.title}",
            details={"runbook_id": str(runbook_id), "title": runbook.title},
            created_at=datetime.utcnow()
        )
        db.add(audit_log)

        await db.delete(runbook)
        await db.commit()

        logger.info(f"Deleted runbook {runbook_id}")
        return True

    # Suggestion Methods

    async def get_suggestions_for_incident(
        self,
        incident_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession,
        limit: int = 5
    ) -> List[RunbookSuggestion]:
        """Get runbook suggestions for an incident."""
        # Get incident with alerts
        result = await db.execute(
            select(Incident)
            .options(selectinload(Incident.alerts))
            .where(
                Incident.id == incident_id,
                Incident.organization_id == organization_id
            )
        )
        incident = result.scalar_one_or_none()

        if not incident:
            return []

        # Build alert data from incident and its alerts
        # Handle both enum and string values for severity
        severity_val = incident.severity
        if hasattr(severity_val, 'value'):
            severity_val = severity_val.value
        elif severity_val is None:
            severity_val = "medium"

        alert_data = {
            "title": incident.title,
            "description": incident.description,
            "severity": severity_val,
        }

        # Add alert-level data if available
        if incident.alerts:
            alert = incident.alerts[0]  # Use first alert for matching
            # Handle both enum and string values for source
            source_val = alert.source
            if hasattr(source_val, 'value'):
                source_val = source_val.value

            alert_data.update({
                "service_name": alert.service_name,
                "source": source_val,
                "host": alert.host,
                "environment": alert.environment,
                "labels": alert.labels or {}
            })

        return await self._get_suggestions(alert_data, organization_id, db, limit)

    async def get_suggestions_for_alert(
        self,
        alert_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession,
        limit: int = 5
    ) -> List[RunbookSuggestion]:
        """Get runbook suggestions for an alert."""
        result = await db.execute(
            select(Alert).where(
                Alert.id == alert_id,
                Alert.organization_id == organization_id
            )
        )
        alert = result.scalar_one_or_none()

        if not alert:
            return []

        # Handle both enum and string values
        severity_val = alert.severity
        if hasattr(severity_val, 'value'):
            severity_val = severity_val.value
        elif severity_val is None:
            severity_val = "warning"

        source_val = alert.source
        if hasattr(source_val, 'value'):
            source_val = source_val.value

        alert_data = {
            "title": alert.title,
            "description": alert.description,
            "severity": severity_val,
            "source": source_val,
            "service_name": alert.service_name,
            "host": alert.host,
            "environment": alert.environment,
            "labels": alert.labels or {}
        }

        return await self._get_suggestions(alert_data, organization_id, db, limit)

    async def _get_suggestions(
        self,
        alert_data: Dict[str, Any],
        organization_id: uuid.UUID,
        db: AsyncSession,
        limit: int = 5
    ) -> List[RunbookSuggestion]:
        """Internal method to get runbook suggestions."""
        # Get all active runbooks for the organization
        result = await db.execute(
            select(Runbook)
            .options(selectinload(Runbook.created_by))
            .where(
                Runbook.organization_id == organization_id,
                Runbook.is_active == True
            )
        )
        runbooks = result.scalars().all()

        # Find matching runbooks
        matches = pattern_matcher.find_matching_runbooks(alert_data, runbooks)
        matches = pattern_matcher.rank_by_relevance(matches, alert_data, limit)

        # Convert to suggestions
        suggestions = []
        runbook_map = {str(r.id): r for r in runbooks}

        for match in matches:
            runbook = runbook_map.get(match.runbook_id)
            if runbook:
                suggestions.append(RunbookSuggestion(
                    runbook=self._runbook_to_response(runbook),
                    match_score=match.score,
                    match_reason=match.match_reason,
                    matched_patterns=[str(p) for p in match.matched_patterns]
                ))

        return suggestions

    # Execution Methods

    async def execute_runbook(
        self,
        runbook_id: uuid.UUID,
        request: RunbookExecuteRequest,
        user: User,
        db: AsyncSession,
        trigger_type: RunbookTriggerType = RunbookTriggerType.MANUAL,
        match_score: Optional[float] = None,
        match_reason: Optional[str] = None
    ) -> RunbookExecution:
        """Execute a runbook and create an execution record."""
        runbook = await self.get_runbook(runbook_id, user.organization_id, db)
        if not runbook:
            raise ValueError(f"Runbook {runbook_id} not found")

        # Parse runbook content
        parsed = runbook_parser.parse(runbook.content)

        if not parsed.steps:
            raise ValueError("Runbook has no executable steps")

        # Create execution record
        execution_id = uuid.uuid4()
        incident_id = uuid.UUID(request.incident_id) if request.incident_id else None

        execution = RunbookExecution(
            id=execution_id,
            organization_id=user.organization_id,
            runbook_id=runbook_id,
            incident_id=incident_id,
            triggered_by_id=user.id,
            status=RunbookExecutionStatus.PENDING,
            trigger_type=trigger_type,
            match_score=match_score,
            match_reason=match_reason,
            execution_context=request.execution_context,
            is_dry_run=request.dry_run,
            created_at=datetime.utcnow()
        )

        db.add(execution)

        # If not dry run, create a deployment with steps
        if not request.dry_run:
            deployment = await self._create_deployment_from_runbook(
                execution_id=execution_id,
                runbook=runbook,
                parsed=parsed,
                incident_id=incident_id,
                user=user,
                execution_context=request.execution_context,
                db=db
            )
            execution.deployment_id = deployment.id

        # Update runbook usage
        runbook.usage_count = (runbook.usage_count or 0) + 1
        runbook.last_used_at = datetime.utcnow()

        # Create audit log
        audit_log = AuditLog(
            id=uuid.uuid4(),
            organization_id=user.organization_id,
            user_id=user.id,
            incident_id=incident_id,
            action="runbook_executed",
            description=f"Runbook executed: {runbook.title}" + (" (dry run)" if request.dry_run else ""),
            details={
                "runbook_id": str(runbook_id),
                "execution_id": str(execution_id),
                "dry_run": request.dry_run,
                "trigger_type": trigger_type.value
            },
            created_at=datetime.utcnow()
        )
        db.add(audit_log)

        await db.commit()
        await db.refresh(execution)

        logger.info(f"Created runbook execution {execution_id} for runbook {runbook_id}")
        return execution

    async def _create_deployment_from_runbook(
        self,
        execution_id: uuid.UUID,
        runbook: Runbook,
        parsed: ParsedRunbook,
        incident_id: Optional[uuid.UUID],
        user: User,
        execution_context: Dict[str, Any],
        db: AsyncSession
    ) -> Deployment:
        """Create a deployment from parsed runbook steps."""
        deployment_id = uuid.uuid4()

        # Build deployment script from steps
        commands = []
        for step in parsed.steps:
            # Substitute variables
            command = runbook_parser.substitute_variables(
                step.command,
                parsed.variables,
                execution_context
            )
            commands.append(command)

        deployment = Deployment(
            id=deployment_id,
            organization_id=user.organization_id,
            incident_id=incident_id,
            created_by_id=user.id,
            name=f"Runbook: {runbook.title}",
            description=f"Automated execution of runbook: {runbook.title}",
            deployment_type=DeploymentType.ROUTINE,
            status=DeploymentStatus.PENDING,
            deployment_script="\n".join(commands),
            execution_environment="docker",
            created_at=datetime.utcnow()
        )

        db.add(deployment)

        # Create deployment steps
        for i, step in enumerate(parsed.steps):
            command = runbook_parser.substitute_variables(
                step.command,
                parsed.variables,
                execution_context
            )

            deployment_step = DeploymentStep(
                id=uuid.uuid4(),
                deployment_id=deployment_id,
                step_number=i + 1,
                name=step.name,
                command=command,
                status=DeploymentStatus.PENDING
            )
            db.add(deployment_step)

        return deployment

    async def get_execution(
        self,
        execution_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[RunbookExecution]:
        """Get a runbook execution by ID."""
        result = await db.execute(
            select(RunbookExecution)
            .options(
                selectinload(RunbookExecution.runbook),
                selectinload(RunbookExecution.deployment)
            )
            .where(
                RunbookExecution.id == execution_id,
                RunbookExecution.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_executions(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession,
        runbook_id: Optional[uuid.UUID] = None,
        incident_id: Optional[uuid.UUID] = None,
        status: Optional[RunbookExecutionStatus] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[RunbookExecution], int]:
        """List runbook executions with filtering and pagination."""
        query = select(RunbookExecution).where(
            RunbookExecution.organization_id == organization_id
        ).options(
            selectinload(RunbookExecution.runbook),
            selectinload(RunbookExecution.deployment)
        )

        if runbook_id:
            query = query.where(RunbookExecution.runbook_id == runbook_id)

        if incident_id:
            query = query.where(RunbookExecution.incident_id == incident_id)

        if status:
            query = query.where(RunbookExecution.status == status)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Apply pagination and ordering
        query = query.order_by(desc(RunbookExecution.created_at))
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await db.execute(query)
        executions = result.scalars().all()

        return list(executions), total

    async def cancel_execution(
        self,
        execution_id: uuid.UUID,
        user: User,
        db: AsyncSession
    ) -> bool:
        """Cancel a running runbook execution."""
        execution = await self.get_execution(execution_id, user.organization_id, db)
        if not execution:
            return False

        if execution.status not in [RunbookExecutionStatus.PENDING, RunbookExecutionStatus.RUNNING]:
            raise ValueError(f"Cannot cancel execution in {execution.status} status")

        execution.status = RunbookExecutionStatus.CANCELLED
        execution.completed_at = datetime.utcnow()

        # Also cancel the deployment if exists
        if execution.deployment_id:
            await db.execute(
                update(Deployment)
                .where(Deployment.id == execution.deployment_id)
                .values(status=DeploymentStatus.CANCELLED)
            )

        # Create audit log
        audit_log = AuditLog(
            id=uuid.uuid4(),
            organization_id=user.organization_id,
            user_id=user.id,
            action="runbook_execution_cancelled",
            description=f"Runbook execution cancelled",
            details={"execution_id": str(execution_id)},
            created_at=datetime.utcnow()
        )
        db.add(audit_log)

        await db.commit()

        logger.info(f"Cancelled runbook execution {execution_id}")
        return True

    # Helper Methods

    def _runbook_to_response(self, runbook: Runbook) -> RunbookResponse:
        """Convert Runbook ORM object to response schema."""
        return RunbookResponse(
            id=str(runbook.id),
            organization_id=str(runbook.organization_id),
            title=runbook.title,
            description=runbook.description,
            content=runbook.content,
            tags=runbook.tags or [],
            service_names=runbook.service_names or [],
            alert_patterns=runbook.alert_patterns or [],
            is_active=runbook.is_active,
            usage_count=runbook.usage_count or 0,
            last_used_at=runbook.last_used_at,
            created_at=runbook.created_at,
            updated_at=runbook.updated_at,
            created_by={
                "id": str(runbook.created_by.id),
                "email": runbook.created_by.email,
                "full_name": runbook.created_by.full_name
            } if runbook.created_by else None
        )


# Singleton instance
runbook_service = RunbookService()
