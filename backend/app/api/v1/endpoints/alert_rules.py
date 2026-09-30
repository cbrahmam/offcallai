# backend/app/api/v1/endpoints/alert_rules.py
"""
API endpoints for managing alert rules.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_async_session
from app.core.security import get_current_user
from app.models.user import User
from app.services.alert_rule_service import alert_rule_service
from app.schemas.alert_rule import (
    AlertRuleCreate, AlertRuleUpdate, AlertRuleToggle,
    AlertRuleResponse, AlertRuleListResponse, AlertRuleSummary,
    AlertRuleTestRequest, AlertRuleTestResponse,
    AlertRuleHistoryResponse
)
from typing import Optional
import uuid
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================
# CRUD Endpoints
# ============================================

@router.post("/", response_model=AlertRuleResponse, status_code=201)
async def create_alert_rule(
    data: AlertRuleCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new alert rule.

    Alert rules monitor metrics and create incidents when conditions are met.

    Example conditions:
    - CPU usage > 90% for 5 minutes
    - Memory usage >= 85%
    - Disk usage > 80% on production hosts
    """
    try:
        rule = await alert_rule_service.create_rule(
            data, current_user.organization_id, current_user.id, db
        )
        return alert_rule_service._rule_to_response(rule)
    except Exception as e:
        logger.error(f"Error creating alert rule: {e}")
        raise HTTPException(status_code=500, detail="Failed to create alert rule")


@router.get("/", response_model=AlertRuleListResponse)
async def list_alert_rules(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status (enabled, disabled, firing, pending)"),
    metric_name: Optional[str] = Query(None, description="Filter by metric name"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get paginated list of alert rules."""
    try:
        return await alert_rule_service.list_rules(
            organization_id=current_user.organization_id,
            db=db,
            status=status,
            metric_name=metric_name,
            page=page,
            per_page=per_page
        )
    except Exception as e:
        logger.error(f"Error listing alert rules: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve alert rules")


@router.get("/summary", response_model=AlertRuleSummary)
async def get_alert_rules_summary(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get summary statistics for alert rules."""
    try:
        return await alert_rule_service.get_summary(
            current_user.organization_id, db
        )
    except Exception as e:
        logger.error(f"Error getting alert rules summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve summary")


@router.get("/{rule_id}", response_model=AlertRuleResponse)
async def get_alert_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get an alert rule by ID."""
    try:
        rule_uuid = uuid.UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rule ID")

    rule = await alert_rule_service.get_rule(
        rule_uuid, current_user.organization_id, db
    )

    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    return alert_rule_service._rule_to_response(rule)


@router.patch("/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(
    rule_id: str,
    data: AlertRuleUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update an alert rule."""
    try:
        rule_uuid = uuid.UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rule ID")

    rule = await alert_rule_service.update_rule(
        rule_uuid, current_user.organization_id, data, db
    )

    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    return alert_rule_service._rule_to_response(rule)


@router.delete("/{rule_id}")
async def delete_alert_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Delete an alert rule."""
    try:
        rule_uuid = uuid.UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rule ID")

    success = await alert_rule_service.delete_rule(
        rule_uuid, current_user.organization_id, db
    )

    if not success:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    return {"status": "deleted", "rule_id": rule_id}


# ============================================
# Enable/Disable
# ============================================

@router.post("/{rule_id}/toggle", response_model=AlertRuleResponse)
async def toggle_alert_rule(
    rule_id: str,
    data: AlertRuleToggle,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Enable or disable an alert rule."""
    try:
        rule_uuid = uuid.UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rule ID")

    rule = await alert_rule_service.toggle_rule(
        rule_uuid, current_user.organization_id, data.enabled, db
    )

    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    return alert_rule_service._rule_to_response(rule)


# ============================================
# Testing
# ============================================

@router.post("/test", response_model=AlertRuleTestResponse)
async def test_alert_rule(
    data: AlertRuleTestRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Test an alert rule configuration against recent data.

    Use this to validate rule settings before creating/enabling.
    Shows which hosts would trigger and current values.
    """
    try:
        return await alert_rule_service.test_rule(
            data, current_user.organization_id, db
        )
    except Exception as e:
        logger.error(f"Error testing alert rule: {e}")
        raise HTTPException(status_code=500, detail="Failed to test alert rule")


# ============================================
# History
# ============================================

@router.get("/{rule_id}/history", response_model=AlertRuleHistoryResponse)
async def get_alert_rule_history(
    rule_id: str,
    limit: int = Query(50, ge=1, le=200, description="Number of history entries"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get history of state changes for an alert rule."""
    try:
        rule_uuid = uuid.UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rule ID")

    # Verify rule exists
    rule = await alert_rule_service.get_rule(
        rule_uuid, current_user.organization_id, db
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    return await alert_rule_service.get_rule_history(
        rule_uuid, current_user.organization_id, db, limit
    )


# ============================================
# Manual Evaluation (Admin)
# ============================================

@router.post("/evaluate")
async def evaluate_alert_rules(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Manually trigger evaluation of all alert rules.
    Useful for testing. In production, this runs on a schedule.
    """
    try:
        result = await alert_rule_service.evaluate_rules(
            current_user.organization_id, db
        )
        return {
            "status": "completed",
            "organization_id": str(current_user.organization_id),
            **result
        }
    except Exception as e:
        logger.error(f"Error evaluating alert rules: {e}")
        raise HTTPException(status_code=500, detail="Failed to evaluate rules")
