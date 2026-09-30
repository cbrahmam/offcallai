# backend/app/api/v1/endpoints/nl_query.py
"""API endpoints for Natural Language Queries."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.nl_query import (
    NLQueryRequest,
    NLQueryResponse,
    NLQuerySummary,
    QueryFeedback,
    SuggestedQuery,
)
from app.services.nl_query_service import NLQueryService

router = APIRouter()


@router.post(
    "/query",
    response_model=NLQueryResponse,
)
async def process_natural_language_query(
    request: NLQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Process a natural language query.

    Examples:
    - "Show me hosts with high memory usage"
    - "What incidents happened yesterday?"
    - "Find error logs from the API service"
    - "Show me slow traces over 500ms"
    - "What alerts fired this week?"
    - "What was deployed today?"

    The system will:
    1. Detect the intent of your query
    2. Extract relevant parameters (time range, filters, etc.)
    3. Execute the appropriate search
    4. Return formatted results
    """
    service = NLQueryService(db)
    return await service.process_query(
        request=request,
        organization_id=current_user.organization_id,
        user_id=current_user.id
    )


@router.get(
    "/query/history",
    response_model=List[NLQuerySummary],
)
async def get_query_history(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get recent query history for the current user.
    """
    service = NLQueryService(db)
    queries = await service.get_query_history(
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        limit=limit
    )

    return [
        NLQuerySummary(
            id=q.id,
            query_text=q.query_text,
            intent=q.intent,
            result_count=q.result_count or 0,
            status=q.status,
            created_at=q.created_at
        )
        for q in queries
    ]


@router.get(
    "/query/{query_id}",
    response_model=NLQueryResponse,
)
async def get_query_details(
    query_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get details of a specific query by ID.
    """
    from sqlalchemy import select
    from app.models.nl_query import NLQueryHistory

    query = select(NLQueryHistory).where(
        NLQueryHistory.id == query_id,
        NLQueryHistory.organization_id == current_user.organization_id
    )
    result = await db.execute(query)
    query_record = result.scalar_one_or_none()

    if not query_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query not found"
        )

    return NLQueryResponse(
        id=query_record.id,
        query_text=query_record.query_text,
        intent=query_record.intent,
        confidence=query_record.confidence or 0.0,
        status=query_record.status,
        result_count=query_record.result_count or 0,
        result_summary=query_record.result_summary,
        result_data=query_record.result_data,
        execution_time_ms=query_record.execution_time_ms,
        generated_query=query_record.query_parameters,
        provider=query_record.provider,
        model=query_record.model,
        error_message=query_record.error_message,
        feedback_helpful=query_record.feedback_helpful,
        created_at=query_record.created_at
    )


@router.post(
    "/query/{query_id}/feedback",
    response_model=NLQueryResponse,
)
async def submit_query_feedback(
    query_id: UUID,
    feedback: QueryFeedback,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit feedback on a query result.

    This helps improve future query understanding and results.
    """
    service = NLQueryService(db)
    query_record = await service.submit_feedback(
        query_id=query_id,
        organization_id=current_user.organization_id,
        helpful=feedback.helpful,
        comment=feedback.comment
    )

    if not query_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query not found"
        )

    return NLQueryResponse(
        id=query_record.id,
        query_text=query_record.query_text,
        intent=query_record.intent,
        confidence=query_record.confidence or 0.0,
        status=query_record.status,
        result_count=query_record.result_count or 0,
        result_summary=query_record.result_summary,
        result_data=query_record.result_data,
        execution_time_ms=query_record.execution_time_ms,
        generated_query=query_record.query_parameters,
        provider=query_record.provider,
        model=query_record.model,
        error_message=query_record.error_message,
        feedback_helpful=query_record.feedback_helpful,
        created_at=query_record.created_at
    )


@router.get(
    "/query/suggestions",
    response_model=List[SuggestedQuery],
)
async def get_suggested_queries(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get suggested queries to help users get started.
    """
    service = NLQueryService(db)
    suggestions = service.get_suggested_queries()

    return [
        SuggestedQuery(
            query=s["query"],
            description=s["description"],
            intent=s["intent"]
        )
        for s in suggestions
    ]
