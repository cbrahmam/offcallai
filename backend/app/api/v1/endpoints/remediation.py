# backend/app/api/v1/endpoints/remediation.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID

from app.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.remediation_service import RemediationService
from app.schemas.remediation import (
    RemediationRuleCreate, RemediationRuleUpdate, RemediationRuleResponse, RemediationRuleList,
    RemediationExecutionCreate, RemediationExecutionResponse, RemediationExecutionList,
    ExecutionApproval,
    RemediationTemplateCreate, RemediationTemplateUpdate, RemediationTemplateResponse, RemediationTemplateList,
    RemediationPlaybookCreate, RemediationPlaybookUpdate, RemediationPlaybookResponse, RemediationPlaybookList,
    PlaybookExecutionCreate, PlaybookExecutionResponse, PlaybookExecutionList,
    ManualRemediationTrigger, ManualPlaybookTrigger,
    RemediationStats, RemediationOverview
)

router = APIRouter()


# ==================== Rules Endpoints ====================

@router.post("/rules", response_model=RemediationRuleResponse)
async def create_rule(
    data: RemediationRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new remediation rule"""
    service = RemediationService(db)
    rule = await service.create_rule(
        current_user.organization_id,
        data,
        current_user.id
    )
    return rule


@router.get("/rules", response_model=RemediationRuleList)
async def list_rules(
    enabled: Optional[bool] = None,
    trigger_type: Optional[str] = None,
    action_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List remediation rules"""
    service = RemediationService(db)
    rules, total = await service.list_rules(
        current_user.organization_id,
        enabled=enabled,
        trigger_type=trigger_type,
        action_type=action_type,
        page=page,
        page_size=page_size
    )
    return RemediationRuleList(items=rules, total=total, page=page, page_size=page_size)


@router.get("/rules/{rule_id}", response_model=RemediationRuleResponse)
async def get_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a remediation rule by ID"""
    service = RemediationService(db)
    rule = await service.get_rule(current_user.organization_id, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.put("/rules/{rule_id}", response_model=RemediationRuleResponse)
async def update_rule(
    rule_id: UUID,
    data: RemediationRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a remediation rule"""
    service = RemediationService(db)
    rule = await service.update_rule(current_user.organization_id, rule_id, data)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a remediation rule"""
    service = RemediationService(db)
    deleted = await service.delete_rule(current_user.organization_id, rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"status": "deleted"}


@router.post("/rules/{rule_id}/toggle", response_model=RemediationRuleResponse)
async def toggle_rule(
    rule_id: UUID,
    enabled: bool = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Enable or disable a rule"""
    service = RemediationService(db)
    rule = await service.toggle_rule(current_user.organization_id, rule_id, enabled)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


# ==================== Executions Endpoints ====================

@router.get("/executions", response_model=RemediationExecutionList)
async def list_executions(
    rule_id: Optional[UUID] = None,
    status: Optional[str] = None,
    trigger_type: Optional[str] = None,
    incident_id: Optional[UUID] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List remediation executions"""
    service = RemediationService(db)
    executions, total = await service.list_executions(
        current_user.organization_id,
        rule_id=rule_id,
        status=status,
        trigger_type=trigger_type,
        incident_id=incident_id,
        page=page,
        page_size=page_size
    )
    return RemediationExecutionList(items=executions, total=total, page=page, page_size=page_size)


@router.get("/executions/{execution_id}", response_model=RemediationExecutionResponse)
async def get_execution(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a remediation execution by ID"""
    service = RemediationService(db)
    execution = await service.get_execution(current_user.organization_id, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution


@router.post("/executions/{execution_id}/approve", response_model=RemediationExecutionResponse)
async def approve_execution(
    execution_id: UUID,
    approval: ExecutionApproval,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Approve or reject a pending execution"""
    service = RemediationService(db)
    execution = await service.approve_execution(
        current_user.organization_id,
        execution_id,
        approval,
        current_user.id
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found or not pending approval")
    return execution


@router.post("/executions/{execution_id}/cancel", response_model=RemediationExecutionResponse)
async def cancel_execution(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cancel a pending or running execution"""
    service = RemediationService(db)
    execution = await service.cancel_execution(current_user.organization_id, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found or cannot be cancelled")
    return execution


@router.post("/trigger", response_model=RemediationExecutionResponse)
async def trigger_remediation(
    trigger: ManualRemediationTrigger,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Manually trigger a remediation action"""
    service = RemediationService(db)
    execution = await service.trigger_manual_remediation(
        current_user.organization_id,
        trigger,
        current_user.id
    )
    return execution


# ==================== Templates Endpoints ====================

@router.post("/templates", response_model=RemediationTemplateResponse)
async def create_template(
    data: RemediationTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new remediation template"""
    service = RemediationService(db)
    template = await service.create_template(
        current_user.organization_id,
        data,
        current_user.id
    )
    return template


@router.get("/templates", response_model=RemediationTemplateList)
async def list_templates(
    category: Optional[str] = None,
    action_type: Optional[str] = None,
    include_system: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List remediation templates"""
    service = RemediationService(db)
    templates, total = await service.list_templates(
        current_user.organization_id,
        category=category,
        action_type=action_type,
        include_system=include_system
    )
    return RemediationTemplateList(items=templates, total=total)


@router.get("/templates/{template_id}", response_model=RemediationTemplateResponse)
async def get_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a template by ID"""
    service = RemediationService(db)
    template = await service.get_template(current_user.organization_id, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.put("/templates/{template_id}", response_model=RemediationTemplateResponse)
async def update_template(
    template_id: UUID,
    data: RemediationTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a template"""
    service = RemediationService(db)
    template = await service.update_template(current_user.organization_id, template_id, data)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found or is a system template")
    return template


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a template"""
    service = RemediationService(db)
    deleted = await service.delete_template(current_user.organization_id, template_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Template not found or is a system template")
    return {"status": "deleted"}


# ==================== Playbooks Endpoints ====================

@router.post("/playbooks", response_model=RemediationPlaybookResponse)
async def create_playbook(
    data: RemediationPlaybookCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new playbook"""
    service = RemediationService(db)
    playbook = await service.create_playbook(
        current_user.organization_id,
        data,
        current_user.id
    )
    return playbook


@router.get("/playbooks", response_model=RemediationPlaybookList)
async def list_playbooks(
    category: Optional[str] = None,
    enabled: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List playbooks"""
    service = RemediationService(db)
    playbooks, total = await service.list_playbooks(
        current_user.organization_id,
        category=category,
        enabled=enabled
    )
    return RemediationPlaybookList(items=playbooks, total=total)


@router.get("/playbooks/{playbook_id}", response_model=RemediationPlaybookResponse)
async def get_playbook(
    playbook_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a playbook by ID"""
    service = RemediationService(db)
    playbook = await service.get_playbook(current_user.organization_id, playbook_id)
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return playbook


@router.put("/playbooks/{playbook_id}", response_model=RemediationPlaybookResponse)
async def update_playbook(
    playbook_id: UUID,
    data: RemediationPlaybookUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a playbook"""
    service = RemediationService(db)
    playbook = await service.update_playbook(current_user.organization_id, playbook_id, data)
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found or is a system playbook")
    return playbook


@router.delete("/playbooks/{playbook_id}")
async def delete_playbook(
    playbook_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a playbook"""
    service = RemediationService(db)
    deleted = await service.delete_playbook(current_user.organization_id, playbook_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Playbook not found or is a system playbook")
    return {"status": "deleted"}


@router.post("/playbooks/trigger", response_model=PlaybookExecutionResponse)
async def trigger_playbook(
    trigger: ManualPlaybookTrigger,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Trigger a playbook execution"""
    service = RemediationService(db)
    try:
        execution = await service.trigger_playbook(
            current_user.organization_id,
            trigger,
            current_user.id
        )
        return execution
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/playbooks/executions", response_model=PlaybookExecutionList)
async def list_playbook_executions(
    playbook_id: Optional[UUID] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List playbook executions"""
    service = RemediationService(db)
    executions, total = await service.list_playbook_executions(
        current_user.organization_id,
        playbook_id=playbook_id,
        status=status,
        page=page,
        page_size=page_size
    )
    return PlaybookExecutionList(items=executions, total=total, page=page, page_size=page_size)


@router.get("/playbooks/executions/{execution_id}", response_model=PlaybookExecutionResponse)
async def get_playbook_execution(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a playbook execution by ID"""
    service = RemediationService(db)
    execution = await service.get_playbook_execution(current_user.organization_id, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Playbook execution not found")
    return execution


# ==================== Statistics Endpoints ====================

@router.get("/stats", response_model=RemediationStats)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get remediation statistics"""
    service = RemediationService(db)
    return await service.get_stats(current_user.organization_id)


@router.get("/overview", response_model=RemediationOverview)
async def get_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get remediation overview with recent activity"""
    service = RemediationService(db)
    stats = await service.get_stats(current_user.organization_id)

    # Get recent executions
    recent_executions, _ = await service.list_executions(
        current_user.organization_id,
        page=1,
        page_size=10
    )

    # Get pending approvals
    pending_approvals, _ = await service.list_executions(
        current_user.organization_id,
        status="approval_required",
        page=1,
        page_size=10
    )

    # Get active playbook executions
    active_playbooks, _ = await service.list_playbook_executions(
        current_user.organization_id,
        status="running",
        page=1,
        page_size=10
    )

    return RemediationOverview(
        stats=stats,
        recent_executions=recent_executions,
        pending_approvals=pending_approvals,
        active_playbook_executions=active_playbooks
    )
