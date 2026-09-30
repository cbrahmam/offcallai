# backend/app/api/v1/endpoints/runbooks.py
"""
API endpoints for runbook management and execution.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_async_session
from app.core.security import get_current_user
from app.models.user import User
from app.models.runbook_execution import RunbookExecutionStatus
from app.services.runbook_service import runbook_service
from app.services.runbook_parser import runbook_parser
from app.schemas.runbook import (
    RunbookCreate, RunbookUpdate, RunbookResponse, RunbookListResponse,
    RunbookExecuteRequest, RunbookExecutionResponse, RunbookExecutionListResponse,
    RunbookSuggestionsResponse
)
from typing import Optional, List, Dict, Any
import uuid
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Runbook CRUD Endpoints
# ============================================================================

@router.get("/", response_model=RunbookListResponse)
async def list_runbooks(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    service_name: Optional[str] = Query(None, description="Filter by service name"),
    search: Optional[str] = Query(None, description="Search in title and description"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get paginated list of runbooks for organization."""
    try:
        tags_list = tags.split(",") if tags else None

        runbooks, total = await runbook_service.list_runbooks(
            organization_id=current_user.organization_id,
            db=db,
            page=page,
            per_page=per_page,
            is_active=is_active,
            tags=tags_list,
            service_name=service_name,
            search=search
        )

        total_pages = (total + per_page - 1) // per_page

        return RunbookListResponse(
            runbooks=[_runbook_to_response(r) for r in runbooks],
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )

    except Exception as e:
        logger.error(f"Error listing runbooks: {e}")
        raise HTTPException(status_code=500, detail=f"Error listing runbooks: {str(e)}")


@router.post("/", response_model=RunbookResponse, status_code=status.HTTP_201_CREATED)
async def create_runbook(
    data: RunbookCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Create a new runbook."""
    try:
        # Validate runbook content
        validation = runbook_parser.validate_runbook(data.content)
        if not validation["valid"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid runbook content: {', '.join(validation['errors'])}"
            )

        runbook = await runbook_service.create_runbook(data, current_user, db)
        return _runbook_to_response(runbook)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating runbook: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating runbook: {str(e)}")


@router.get("/{runbook_id}", response_model=RunbookResponse)
async def get_runbook(
    runbook_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get a runbook by ID."""
    try:
        runbook = await runbook_service.get_runbook(
            uuid.UUID(runbook_id),
            current_user.organization_id,
            db
        )

        if not runbook:
            raise HTTPException(status_code=404, detail="Runbook not found")

        return _runbook_to_response(runbook)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting runbook: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting runbook: {str(e)}")


@router.patch("/{runbook_id}", response_model=RunbookResponse)
async def update_runbook(
    runbook_id: str,
    data: RunbookUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update a runbook."""
    try:
        # Validate content if provided
        if data.content:
            validation = runbook_parser.validate_runbook(data.content)
            if not validation["valid"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid runbook content: {', '.join(validation['errors'])}"
                )

        runbook = await runbook_service.update_runbook(
            uuid.UUID(runbook_id),
            data,
            current_user,
            db
        )

        if not runbook:
            raise HTTPException(status_code=404, detail="Runbook not found")

        return _runbook_to_response(runbook)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating runbook: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating runbook: {str(e)}")


@router.delete("/{runbook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_runbook(
    runbook_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Delete a runbook."""
    try:
        success = await runbook_service.delete_runbook(
            uuid.UUID(runbook_id),
            current_user,
            db
        )

        if not success:
            raise HTTPException(status_code=404, detail="Runbook not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting runbook: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting runbook: {str(e)}")


# ============================================================================
# Runbook Execution Endpoints
# ============================================================================

@router.post("/{runbook_id}/execute", response_model=RunbookExecutionResponse)
async def execute_runbook(
    runbook_id: str,
    request: RunbookExecuteRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Execute a runbook."""
    try:
        execution = await runbook_service.execute_runbook(
            uuid.UUID(runbook_id),
            request,
            current_user,
            db
        )

        return _execution_to_response(execution)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error executing runbook: {e}")
        raise HTTPException(status_code=500, detail=f"Error executing runbook: {str(e)}")


@router.get("/{runbook_id}/executions", response_model=RunbookExecutionListResponse)
async def list_runbook_executions(
    runbook_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """List executions for a specific runbook."""
    try:
        status_enum = RunbookExecutionStatus(status) if status else None

        executions, total = await runbook_service.list_executions(
            organization_id=current_user.organization_id,
            db=db,
            runbook_id=uuid.UUID(runbook_id),
            status=status_enum,
            page=page,
            per_page=per_page
        )

        total_pages = (total + per_page - 1) // per_page

        return RunbookExecutionListResponse(
            executions=[_execution_to_response(e) for e in executions],
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )

    except Exception as e:
        logger.error(f"Error listing executions: {e}")
        raise HTTPException(status_code=500, detail=f"Error listing executions: {str(e)}")


@router.get("/{runbook_id}/validate")
async def validate_runbook_content(
    runbook_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Validate a runbook's content and return parsing results."""
    try:
        runbook = await runbook_service.get_runbook(
            uuid.UUID(runbook_id),
            current_user.organization_id,
            db
        )

        if not runbook:
            raise HTTPException(status_code=404, detail="Runbook not found")

        validation = runbook_parser.validate_runbook(runbook.content)
        parsed = runbook_parser.parse(runbook.content)

        return {
            **validation,
            "parsed_steps": [
                {"name": s.name, "command": s.command[:100] + "..." if len(s.command) > 100 else s.command}
                for s in parsed.steps
            ],
            "variables_defined": list(parsed.variables.keys())
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating runbook: {e}")
        raise HTTPException(status_code=500, detail=f"Error validating runbook: {str(e)}")


# ============================================================================
# Execution Management Endpoints
# ============================================================================

@router.get("/executions/{execution_id}", response_model=RunbookExecutionResponse)
async def get_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get a runbook execution by ID."""
    try:
        execution = await runbook_service.get_execution(
            uuid.UUID(execution_id),
            current_user.organization_id,
            db
        )

        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")

        return _execution_to_response(execution)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting execution: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting execution: {str(e)}")


@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Cancel a running runbook execution."""
    try:
        success = await runbook_service.cancel_execution(
            uuid.UUID(execution_id),
            current_user,
            db
        )

        if not success:
            raise HTTPException(status_code=404, detail="Execution not found")

        return {"message": "Execution cancelled successfully"}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling execution: {e}")
        raise HTTPException(status_code=500, detail=f"Error cancelling execution: {str(e)}")


# ============================================================================
# Suggestion Endpoints
# ============================================================================

@router.get("/suggestions/incident/{incident_id}", response_model=RunbookSuggestionsResponse)
async def get_suggestions_for_incident(
    incident_id: str,
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get runbook suggestions for an incident."""
    try:
        suggestions = await runbook_service.get_suggestions_for_incident(
            uuid.UUID(incident_id),
            current_user.organization_id,
            db,
            limit=limit
        )

        return RunbookSuggestionsResponse(
            suggestions=suggestions,
            total=len(suggestions)
        )

    except Exception as e:
        logger.error(f"Error getting suggestions: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting suggestions: {str(e)}")


@router.get("/suggestions/alert/{alert_id}", response_model=RunbookSuggestionsResponse)
async def get_suggestions_for_alert(
    alert_id: str,
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get runbook suggestions for an alert."""
    try:
        suggestions = await runbook_service.get_suggestions_for_alert(
            uuid.UUID(alert_id),
            current_user.organization_id,
            db,
            limit=limit
        )

        return RunbookSuggestionsResponse(
            suggestions=suggestions,
            total=len(suggestions)
        )

    except Exception as e:
        logger.error(f"Error getting suggestions: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting suggestions: {str(e)}")


# ============================================================================
# Helper Functions
# ============================================================================

def _runbook_to_response(runbook) -> RunbookResponse:
    """Convert Runbook ORM object to response schema."""
    created_by = None
    if runbook.created_by:
        created_by = {
            "id": str(runbook.created_by.id),
            "email": runbook.created_by.email,
            "full_name": runbook.created_by.full_name
        }

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
        created_by=created_by
    )


def _execution_to_response(execution) -> RunbookExecutionResponse:
    """Convert RunbookExecution ORM object to response schema."""
    deployment = None
    if execution.deployment:
        deployment = {
            "id": str(execution.deployment.id),
            "status": execution.deployment.status.value if execution.deployment.status else "pending",
            "started_at": execution.deployment.started_at,
            "completed_at": execution.deployment.completed_at
        }

    runbook = None
    if execution.runbook:
        runbook = _runbook_to_response(execution.runbook)

    return RunbookExecutionResponse(
        id=str(execution.id),
        organization_id=str(execution.organization_id),
        runbook_id=str(execution.runbook_id),
        incident_id=str(execution.incident_id) if execution.incident_id else None,
        status=execution.status.value if execution.status else "pending",
        trigger_type=execution.trigger_type.value if execution.trigger_type else "manual",
        match_score=execution.match_score,
        match_reason=execution.match_reason,
        matched_patterns=execution.matched_patterns or [],
        execution_context=execution.execution_context or {},
        is_dry_run=execution.is_dry_run or False,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        error_message=execution.error_message,
        output_summary=execution.output_summary,
        created_at=execution.created_at,
        deployment=deployment,
        runbook=runbook
    )
