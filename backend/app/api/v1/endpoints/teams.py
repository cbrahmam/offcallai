import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.models.user import User
from app.schemas.team import (
    TeamCreate, TeamUpdate, TeamResponse, TeamMemberResponse
)
from app.core.auth import get_current_user
from app.services.team_service import TeamService

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=TeamResponse)
async def create_team(
    team_data: TeamCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Create a new team"""
    
    try:
        service = TeamService(db)
        
        team = await service.create_team(
            team_data=team_data,
            organization_id=str(current_user.organization_id),
            created_by_id=str(current_user.id)
        )
        
        logger.info(f"Team created: {team.name} by user {current_user.email}")
        
        return team
        
    except Exception as e:
        logger.error(f"Error creating team: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create team: {str(e)}")

@router.get("/", response_model=List[TeamResponse])
async def list_teams(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """List all teams in organization"""
    
    try:
        service = TeamService(db)
        
        teams = await service.list_teams(str(current_user.organization_id))
        
        return teams
        
    except Exception as e:
        logger.error(f"Error listing teams: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list teams: {str(e)}")

@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Get team details"""
    
    try:
        service = TeamService(db)
        
        team = await service.get_team(
            team_id=team_id,
            organization_id=str(current_user.organization_id)
        )
        
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        
        return team
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting team {team_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get team: {str(e)}")

@router.patch("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: str,
    team_update: TeamUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Update team"""
    
    try:
        service = TeamService(db)
        
        team = await service.update_team(
            team_id=team_id,
            organization_id=str(current_user.organization_id),
            team_update=team_update
        )
        
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        
        logger.info(f"Team {team_id} updated by user {current_user.email}")
        
        return team
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating team {team_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update team: {str(e)}")

@router.post("/{team_id}/members/{user_id}")
async def add_team_member(
    team_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Add member to team"""
    
    try:
        service = TeamService(db)
        
        success = await service.add_team_member(
            team_id=team_id,
            user_id=user_id,
            organization_id=str(current_user.organization_id)
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Team or user not found")
        
        return {"success": True, "message": "Member added to team"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding team member: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add team member: {str(e)}")

@router.delete("/{team_id}/members/{user_id}")
async def remove_team_member(
    team_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Remove member from team"""
    
    try:
        service = TeamService(db)
        
        success = await service.remove_team_member(
            team_id=team_id,
            user_id=user_id,
            organization_id=str(current_user.organization_id)
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Team or user not found")
        
        return {"success": True, "message": "Member removed from team"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing team member: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove team member: {str(e)}")