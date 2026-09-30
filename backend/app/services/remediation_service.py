# backend/app/services/remediation_service.py
import uuid
import asyncio
import httpx
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import selectinload

from ..models.remediation import (
    RemediationRule, RemediationExecution, RemediationTemplate,
    RemediationPlaybook, PlaybookExecution
)
from ..schemas.remediation import (
    RemediationRuleCreate, RemediationRuleUpdate,
    RemediationExecutionCreate, ExecutionApproval,
    RemediationTemplateCreate, RemediationTemplateUpdate,
    RemediationPlaybookCreate, RemediationPlaybookUpdate,
    PlaybookExecutionCreate, ManualRemediationTrigger, ManualPlaybookTrigger,
    RemediationStats
)


class RemediationService:
    """Service for managing auto-remediation rules and executions"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================== Remediation Rules ====================

    async def create_rule(
        self,
        organization_id: uuid.UUID,
        data: RemediationRuleCreate,
        created_by: Optional[uuid.UUID] = None
    ) -> RemediationRule:
        """Create a new remediation rule"""
        rule = RemediationRule(
            id=uuid.uuid4(),
            organization_id=organization_id,
            created_by=created_by,
            **data.model_dump()
        )
        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    async def get_rule(
        self,
        organization_id: uuid.UUID,
        rule_id: uuid.UUID
    ) -> Optional[RemediationRule]:
        """Get a remediation rule by ID"""
        result = await self.db.execute(
            select(RemediationRule).where(
                and_(
                    RemediationRule.organization_id == organization_id,
                    RemediationRule.id == rule_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_rules(
        self,
        organization_id: uuid.UUID,
        enabled: Optional[bool] = None,
        trigger_type: Optional[str] = None,
        action_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Tuple[List[RemediationRule], int]:
        """List remediation rules with filters"""
        query = select(RemediationRule).where(
            RemediationRule.organization_id == organization_id
        )

        if enabled is not None:
            query = query.where(RemediationRule.enabled == enabled)
        if trigger_type:
            query = query.where(RemediationRule.trigger_type == trigger_type)
        if action_type:
            query = query.where(RemediationRule.action_type == action_type)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar()

        # Apply pagination and ordering
        query = query.order_by(desc(RemediationRule.priority), RemediationRule.name)
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def update_rule(
        self,
        organization_id: uuid.UUID,
        rule_id: uuid.UUID,
        data: RemediationRuleUpdate
    ) -> Optional[RemediationRule]:
        """Update a remediation rule"""
        rule = await self.get_rule(organization_id, rule_id)
        if not rule:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(rule, key, value)

        rule.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    async def delete_rule(
        self,
        organization_id: uuid.UUID,
        rule_id: uuid.UUID
    ) -> bool:
        """Delete a remediation rule"""
        rule = await self.get_rule(organization_id, rule_id)
        if not rule:
            return False

        await self.db.delete(rule)
        await self.db.commit()
        return True

    async def toggle_rule(
        self,
        organization_id: uuid.UUID,
        rule_id: uuid.UUID,
        enabled: bool
    ) -> Optional[RemediationRule]:
        """Enable or disable a rule"""
        rule = await self.get_rule(organization_id, rule_id)
        if not rule:
            return None

        rule.enabled = enabled
        rule.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    # ==================== Remediation Executions ====================

    async def create_execution(
        self,
        organization_id: uuid.UUID,
        data: RemediationExecutionCreate,
        initiated_by: Optional[uuid.UUID] = None
    ) -> RemediationExecution:
        """Create a new remediation execution"""
        # Get execution number for the rule if applicable
        execution_number = None
        if data.rule_id:
            count_result = await self.db.execute(
                select(func.count()).where(
                    RemediationExecution.rule_id == data.rule_id
                )
            )
            execution_number = count_result.scalar() + 1

        execution = RemediationExecution(
            id=uuid.uuid4(),
            organization_id=organization_id,
            execution_number=execution_number,
            status="pending",
            initiated_by=initiated_by,
            is_manual=initiated_by is not None,
            **data.model_dump()
        )
        self.db.add(execution)
        await self.db.commit()
        await self.db.refresh(execution)
        return execution

    async def get_execution(
        self,
        organization_id: uuid.UUID,
        execution_id: uuid.UUID
    ) -> Optional[RemediationExecution]:
        """Get a remediation execution by ID"""
        result = await self.db.execute(
            select(RemediationExecution).where(
                and_(
                    RemediationExecution.organization_id == organization_id,
                    RemediationExecution.id == execution_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_executions(
        self,
        organization_id: uuid.UUID,
        rule_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        trigger_type: Optional[str] = None,
        incident_id: Optional[uuid.UUID] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Tuple[List[RemediationExecution], int]:
        """List remediation executions with filters"""
        query = select(RemediationExecution).where(
            RemediationExecution.organization_id == organization_id
        )

        if rule_id:
            query = query.where(RemediationExecution.rule_id == rule_id)
        if status:
            query = query.where(RemediationExecution.status == status)
        if trigger_type:
            query = query.where(RemediationExecution.trigger_type == trigger_type)
        if incident_id:
            query = query.where(RemediationExecution.incident_id == incident_id)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar()

        # Apply pagination and ordering
        query = query.order_by(desc(RemediationExecution.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def update_execution_status(
        self,
        organization_id: uuid.UUID,
        execution_id: uuid.UUID,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        output_log: Optional[str] = None
    ) -> Optional[RemediationExecution]:
        """Update execution status and results"""
        execution = await self.get_execution(organization_id, execution_id)
        if not execution:
            return None

        execution.status = status
        execution.updated_at = datetime.utcnow()

        if status == "running" and not execution.started_at:
            execution.started_at = datetime.utcnow()
        elif status in ["success", "failed", "cancelled", "timeout"]:
            execution.completed_at = datetime.utcnow()
            if execution.started_at:
                execution.duration_seconds = (
                    execution.completed_at - execution.started_at
                ).total_seconds()

        if result:
            execution.result = result
        if error_message:
            execution.error_message = error_message
        if output_log:
            execution.output_log = output_log

        # Update rule statistics
        if execution.rule_id:
            rule = await self.get_rule(organization_id, execution.rule_id)
            if rule:
                rule.execution_count += 1
                rule.last_executed_at = datetime.utcnow()
                if status == "success":
                    rule.success_count += 1
                    rule.last_success_at = datetime.utcnow()
                elif status == "failed":
                    rule.failure_count += 1
                    rule.last_failure_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(execution)
        return execution

    async def approve_execution(
        self,
        organization_id: uuid.UUID,
        execution_id: uuid.UUID,
        approval: ExecutionApproval,
        user_id: uuid.UUID
    ) -> Optional[RemediationExecution]:
        """Approve or reject a pending execution"""
        execution = await self.get_execution(organization_id, execution_id)
        if not execution or execution.status != "approval_required":
            return None

        if approval.approved:
            execution.status = "approved"
            execution.approved_by = user_id
            execution.approved_at = datetime.utcnow()
            execution.approval_notes = approval.notes
        else:
            execution.status = "rejected"
            execution.rejected_by = user_id
            execution.rejected_at = datetime.utcnow()
            execution.rejection_reason = approval.notes

        execution.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(execution)
        return execution

    async def cancel_execution(
        self,
        organization_id: uuid.UUID,
        execution_id: uuid.UUID
    ) -> Optional[RemediationExecution]:
        """Cancel a pending or running execution"""
        execution = await self.get_execution(organization_id, execution_id)
        if not execution or execution.status not in ["pending", "queued", "running", "approval_required"]:
            return None

        execution.status = "cancelled"
        execution.completed_at = datetime.utcnow()
        execution.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(execution)
        return execution

    # ==================== Trigger Remediation ====================

    async def trigger_manual_remediation(
        self,
        organization_id: uuid.UUID,
        trigger: ManualRemediationTrigger,
        user_id: uuid.UUID
    ) -> RemediationExecution:
        """Manually trigger a remediation action"""
        execution_data = RemediationExecutionCreate(
            rule_id=trigger.rule_id,
            trigger_type="manual",
            trigger_source="user",
            trigger_data={"reason": trigger.reason} if trigger.reason else {},
            target_type=trigger.target_type,
            target_id=trigger.target_id,
            target_name=trigger.target_name,
            action_type=trigger.action_type,
            action_config=trigger.action_config,
            action_parameters=trigger.parameters,
            is_dry_run=trigger.is_dry_run,
            incident_id=trigger.incident_id
        )

        execution = await self.create_execution(organization_id, execution_data, user_id)

        # Queue for execution (in production, this would go to a task queue)
        execution.status = "queued"
        execution.queued_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(execution)

        return execution

    async def evaluate_rules_for_trigger(
        self,
        organization_id: uuid.UUID,
        trigger_type: str,
        trigger_data: Dict[str, Any]
    ) -> List[RemediationRule]:
        """Find matching rules for a trigger event"""
        rules, _ = await self.list_rules(
            organization_id,
            enabled=True,
            trigger_type=trigger_type,
            page_size=100
        )

        matching_rules = []
        for rule in rules:
            if self._matches_conditions(rule.trigger_conditions, trigger_data):
                # Check cooldown
                if rule.last_executed_at:
                    cooldown_end = rule.last_executed_at + timedelta(minutes=rule.cooldown_minutes)
                    if datetime.utcnow() < cooldown_end:
                        continue

                # Check rate limit
                recent_executions = await self._count_recent_executions(rule.id, hours=1)
                if recent_executions >= rule.max_executions_per_hour:
                    continue

                matching_rules.append(rule)

        # Sort by priority
        matching_rules.sort(key=lambda r: r.priority, reverse=True)
        return matching_rules

    def _matches_conditions(
        self,
        conditions: Dict[str, Any],
        data: Dict[str, Any]
    ) -> bool:
        """Check if data matches the rule conditions"""
        for key, expected in conditions.items():
            actual = data.get(key)
            if actual is None:
                return False

            if isinstance(expected, list):
                if actual not in expected:
                    return False
            elif isinstance(expected, dict):
                # Handle operators like $gt, $lt, $contains
                for op, val in expected.items():
                    if op == "$gt" and not (actual > val):
                        return False
                    elif op == "$gte" and not (actual >= val):
                        return False
                    elif op == "$lt" and not (actual < val):
                        return False
                    elif op == "$lte" and not (actual <= val):
                        return False
                    elif op == "$contains" and val not in str(actual):
                        return False
                    elif op == "$regex":
                        import re
                        if not re.search(val, str(actual)):
                            return False
            else:
                if actual != expected:
                    return False

        return True

    async def _count_recent_executions(
        self,
        rule_id: uuid.UUID,
        hours: int = 1
    ) -> int:
        """Count executions of a rule in the last N hours"""
        since = datetime.utcnow() - timedelta(hours=hours)
        result = await self.db.execute(
            select(func.count()).where(
                and_(
                    RemediationExecution.rule_id == rule_id,
                    RemediationExecution.created_at >= since
                )
            )
        )
        return result.scalar()

    # ==================== Templates ====================

    async def create_template(
        self,
        organization_id: uuid.UUID,
        data: RemediationTemplateCreate,
        created_by: Optional[uuid.UUID] = None
    ) -> RemediationTemplate:
        """Create a new remediation template"""
        template = RemediationTemplate(
            id=uuid.uuid4(),
            organization_id=organization_id,
            created_by=created_by,
            **data.model_dump()
        )
        self.db.add(template)
        await self.db.commit()
        await self.db.refresh(template)
        return template

    async def get_template(
        self,
        organization_id: uuid.UUID,
        template_id: uuid.UUID
    ) -> Optional[RemediationTemplate]:
        """Get a template by ID"""
        result = await self.db.execute(
            select(RemediationTemplate).where(
                and_(
                    RemediationTemplate.organization_id == organization_id,
                    RemediationTemplate.id == template_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_templates(
        self,
        organization_id: uuid.UUID,
        category: Optional[str] = None,
        action_type: Optional[str] = None,
        include_system: bool = True
    ) -> Tuple[List[RemediationTemplate], int]:
        """List templates"""
        conditions = [
            or_(
                RemediationTemplate.organization_id == organization_id,
                and_(RemediationTemplate.is_system_template == True, include_system),
                RemediationTemplate.is_public == True
            )
        ]

        if category:
            conditions.append(RemediationTemplate.category == category)
        if action_type:
            conditions.append(RemediationTemplate.action_type == action_type)

        query = select(RemediationTemplate).where(and_(*conditions))
        query = query.order_by(RemediationTemplate.category, RemediationTemplate.name)

        result = await self.db.execute(query)
        templates = result.scalars().all()
        return templates, len(templates)

    async def update_template(
        self,
        organization_id: uuid.UUID,
        template_id: uuid.UUID,
        data: RemediationTemplateUpdate
    ) -> Optional[RemediationTemplate]:
        """Update a template"""
        template = await self.get_template(organization_id, template_id)
        if not template or template.is_system_template:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(template, key, value)

        template.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(template)
        return template

    async def delete_template(
        self,
        organization_id: uuid.UUID,
        template_id: uuid.UUID
    ) -> bool:
        """Delete a template"""
        template = await self.get_template(organization_id, template_id)
        if not template or template.is_system_template:
            return False

        await self.db.delete(template)
        await self.db.commit()
        return True

    # ==================== Playbooks ====================

    async def create_playbook(
        self,
        organization_id: uuid.UUID,
        data: RemediationPlaybookCreate,
        created_by: Optional[uuid.UUID] = None
    ) -> RemediationPlaybook:
        """Create a new playbook"""
        playbook = RemediationPlaybook(
            id=uuid.uuid4(),
            organization_id=organization_id,
            created_by=created_by,
            steps=[step.model_dump() for step in data.steps],
            name=data.name,
            description=data.description,
            category=data.category,
            stop_on_first_failure=data.stop_on_first_failure,
            max_duration_minutes=data.max_duration_minutes,
            require_approval=data.require_approval,
            tags=data.tags
        )
        self.db.add(playbook)
        await self.db.commit()
        await self.db.refresh(playbook)
        return playbook

    async def get_playbook(
        self,
        organization_id: uuid.UUID,
        playbook_id: uuid.UUID
    ) -> Optional[RemediationPlaybook]:
        """Get a playbook by ID"""
        result = await self.db.execute(
            select(RemediationPlaybook).where(
                and_(
                    RemediationPlaybook.organization_id == organization_id,
                    RemediationPlaybook.id == playbook_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_playbooks(
        self,
        organization_id: uuid.UUID,
        category: Optional[str] = None,
        enabled: Optional[bool] = None
    ) -> Tuple[List[RemediationPlaybook], int]:
        """List playbooks"""
        query = select(RemediationPlaybook).where(
            RemediationPlaybook.organization_id == organization_id
        )

        if category:
            query = query.where(RemediationPlaybook.category == category)
        if enabled is not None:
            query = query.where(RemediationPlaybook.enabled == enabled)

        query = query.order_by(RemediationPlaybook.name)
        result = await self.db.execute(query)
        playbooks = result.scalars().all()
        return playbooks, len(playbooks)

    async def update_playbook(
        self,
        organization_id: uuid.UUID,
        playbook_id: uuid.UUID,
        data: RemediationPlaybookUpdate
    ) -> Optional[RemediationPlaybook]:
        """Update a playbook"""
        playbook = await self.get_playbook(organization_id, playbook_id)
        if not playbook or playbook.is_system_playbook:
            return None

        update_data = data.model_dump(exclude_unset=True)
        if "steps" in update_data and update_data["steps"]:
            update_data["steps"] = [step.model_dump() if hasattr(step, 'model_dump') else step for step in update_data["steps"]]

        for key, value in update_data.items():
            setattr(playbook, key, value)

        playbook.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(playbook)
        return playbook

    async def delete_playbook(
        self,
        organization_id: uuid.UUID,
        playbook_id: uuid.UUID
    ) -> bool:
        """Delete a playbook"""
        playbook = await self.get_playbook(organization_id, playbook_id)
        if not playbook or playbook.is_system_playbook:
            return False

        await self.db.delete(playbook)
        await self.db.commit()
        return True

    # ==================== Playbook Executions ====================

    async def trigger_playbook(
        self,
        organization_id: uuid.UUID,
        trigger: ManualPlaybookTrigger,
        user_id: uuid.UUID
    ) -> PlaybookExecution:
        """Trigger a playbook execution"""
        playbook = await self.get_playbook(organization_id, trigger.playbook_id)
        if not playbook:
            raise ValueError("Playbook not found")

        execution = PlaybookExecution(
            id=uuid.uuid4(),
            organization_id=organization_id,
            playbook_id=trigger.playbook_id,
            status="pending",
            trigger_type="manual",
            trigger_data={"reason": trigger.reason, "parameters": trigger.parameters},
            target_type=trigger.target_type,
            target_id=trigger.target_id,
            target_name=trigger.target_name,
            incident_id=trigger.incident_id,
            initiated_by=user_id,
            step_results=[]
        )
        self.db.add(execution)

        # Update playbook stats
        playbook.execution_count += 1
        playbook.last_executed_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(execution)
        return execution

    async def get_playbook_execution(
        self,
        organization_id: uuid.UUID,
        execution_id: uuid.UUID
    ) -> Optional[PlaybookExecution]:
        """Get a playbook execution by ID"""
        result = await self.db.execute(
            select(PlaybookExecution).where(
                and_(
                    PlaybookExecution.organization_id == organization_id,
                    PlaybookExecution.id == execution_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_playbook_executions(
        self,
        organization_id: uuid.UUID,
        playbook_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Tuple[List[PlaybookExecution], int]:
        """List playbook executions"""
        query = select(PlaybookExecution).where(
            PlaybookExecution.organization_id == organization_id
        )

        if playbook_id:
            query = query.where(PlaybookExecution.playbook_id == playbook_id)
        if status:
            query = query.where(PlaybookExecution.status == status)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar()

        query = query.order_by(desc(PlaybookExecution.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        return result.scalars().all(), total

    # ==================== Statistics ====================

    async def get_stats(self, organization_id: uuid.UUID) -> RemediationStats:
        """Get remediation statistics"""
        # Count rules
        rules_result = await self.db.execute(
            select(func.count()).where(RemediationRule.organization_id == organization_id)
        )
        total_rules = rules_result.scalar()

        active_result = await self.db.execute(
            select(func.count()).where(
                and_(
                    RemediationRule.organization_id == organization_id,
                    RemediationRule.enabled == True
                )
            )
        )
        active_rules = active_result.scalar()

        # Count executions
        exec_result = await self.db.execute(
            select(func.count()).where(RemediationExecution.organization_id == organization_id)
        )
        total_executions = exec_result.scalar()

        success_result = await self.db.execute(
            select(func.count()).where(
                and_(
                    RemediationExecution.organization_id == organization_id,
                    RemediationExecution.status == "success"
                )
            )
        )
        successful_executions = success_result.scalar()

        failed_result = await self.db.execute(
            select(func.count()).where(
                and_(
                    RemediationExecution.organization_id == organization_id,
                    RemediationExecution.status == "failed"
                )
            )
        )
        failed_executions = failed_result.scalar()

        # Pending approvals
        pending_result = await self.db.execute(
            select(func.count()).where(
                and_(
                    RemediationExecution.organization_id == organization_id,
                    RemediationExecution.status == "approval_required"
                )
            )
        )
        pending_approvals = pending_result.scalar()

        # Average execution time
        avg_result = await self.db.execute(
            select(func.avg(RemediationExecution.duration_seconds)).where(
                and_(
                    RemediationExecution.organization_id == organization_id,
                    RemediationExecution.duration_seconds.isnot(None)
                )
            )
        )
        avg_execution_time = avg_result.scalar() or 0

        # Recent executions
        now = datetime.utcnow()
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)

        day_result = await self.db.execute(
            select(func.count()).where(
                and_(
                    RemediationExecution.organization_id == organization_id,
                    RemediationExecution.created_at >= day_ago
                )
            )
        )
        executions_last_24h = day_result.scalar()

        week_result = await self.db.execute(
            select(func.count()).where(
                and_(
                    RemediationExecution.organization_id == organization_id,
                    RemediationExecution.created_at >= week_ago
                )
            )
        )
        executions_last_7d = week_result.scalar()

        return RemediationStats(
            total_rules=total_rules,
            active_rules=active_rules,
            total_executions=total_executions,
            successful_executions=successful_executions,
            failed_executions=failed_executions,
            pending_approvals=pending_approvals,
            avg_execution_time_seconds=float(avg_execution_time),
            executions_last_24h=executions_last_24h,
            executions_last_7d=executions_last_7d,
            top_triggered_rules=[],
            recent_failures=[]
        )
