from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, insert
from sqlalchemy.orm import selectinload

from app.models.team import Team, team_members
from app.models.user import User
from app.schemas.team import TeamCreate, TeamUpdate

class TeamService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_team_simple(
        self, 
        team_data: TeamCreate, 
        organization_id: str,
        creator_id: str
    ) -> Team:
        """Create a new team (simplified version)"""
        # Create the team first
        team = Team(
            name=team_data.name,
            description=team_data.description,
            organization_id=organization_id
        )
        
        self.db.add(team)
        await self.db.flush()  # Get the team ID
        
        # Add creator to team using raw insert
        await self.db.execute(
            insert(team_members).values(
                team_id=team.id,
                user_id=creator_id,
                role='lead'
            )
        )
        
        await self.db.commit()
        await self.db.refresh(team)
        return team

    async def list_teams_simple(self, organization_id: str) -> List[Team]:
        """List all teams in organization (simplified)"""
        query = (
            select(Team)
            .where(Team.organization_id == organization_id)
            .order_by(Team.name)
        )
        result = await self.db.execute(query)
        return result.scalars().all()