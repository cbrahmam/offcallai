# backend/app/api/v1/endpoints/slack.py
# FIXED VERSION - Uses app.core.security instead of app.core.auth

import json
from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
from app.database import get_async_session
from app.models.user import User
from app.models.integration import Integration, IntegrationType
from app.core.security import get_current_user  # FIXED: Changed from app.core.auth
from app.core.config import settings
import secrets
import base64
import uuid

router = APIRouter()

# ===== OAUTH ENDPOINTS =====

@router.post("/oauth/start")
async def start_slack_oauth(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Start Slack OAuth flow"""
    try:
        client_id = settings.SLACK_CLIENT_ID
        if not client_id:
            raise HTTPException(status_code=500, detail="Slack integration not configured")
        
        # Generate state that includes user info (encoded)
        state_data = {
            "user_id": str(current_user.id),
            "org_id": str(current_user.organization_id),
            "timestamp": datetime.utcnow().isoformat(),
            "random": secrets.token_urlsafe(16)
        }
        
        # Encode state data
        state = base64.urlsafe_b64encode(json.dumps(state_data).encode()).decode()
        
        redirect_uri = f"{settings.FRONTEND_URL}/settings/integrations/slack/callback"
        
        scopes = [
            "chat:write",
            "chat:write.public",
            "channels:read",
            "groups:read",
            "im:read",
            "users:read"
        ]
        
        authorization_url = (
            f"https://slack.com/oauth/v2/authorize"
            f"?client_id={client_id}"
            f"&scope={','.join(scopes)}"
            f"&redirect_uri={redirect_uri}"
            f"&state={state}"
            f"&user_scope="
        )
        
        print(f"✅ Slack OAuth started for user: {current_user.id}")
        
        return {
            "authorization_url": authorization_url,
            "state": state
        }
        
    except Exception as e:
        print(f"Slack OAuth start error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/oauth/callback")
async def slack_oauth_callback(
    request: Request,
    db: AsyncSession = Depends(get_async_session)
):
    """Handle Slack OAuth callback - NO AUTH REQUIRED (validates state instead)"""
    try:
        import httpx
        
        # Parse JSON body
        body = await request.json()
        code = body.get("code")
        state = body.get("state")
        
        if not code or not state:
            raise HTTPException(status_code=400, detail="Missing code or state")
        
        # Decode and validate state
        try:
            state_json = base64.urlsafe_b64decode(state.encode()).decode()
            state_data = json.loads(state_json)
            
            # Validate timestamp (must be within 10 minutes)
            timestamp = datetime.fromisoformat(state_data["timestamp"])
            if datetime.utcnow() - timestamp > timedelta(minutes=10):
                raise HTTPException(status_code=400, detail="OAuth state expired")
            
            user_id = state_data["user_id"]
            org_id = state_data["org_id"]
            
        except Exception as e:
            print(f"Invalid state parameter: {e}")
            raise HTTPException(status_code=400, detail="Invalid state parameter")
        
        client_id = settings.SLACK_CLIENT_ID
        client_secret = settings.SLACK_CLIENT_SECRET
        
        if not client_id or not client_secret:
            raise HTTPException(status_code=500, detail="Slack credentials not configured")
        
        # Exchange code for access token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://slack.com/api/oauth.v2.access",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": f"{settings.FRONTEND_URL}/settings/integrations/slack/callback"
                }
            )
            
            data = response.json()
            
            if not data.get("ok"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Slack OAuth failed: {data.get('error', 'Unknown error')}"
                )
        
        # Store Slack credentials for this user/org
        access_token = data.get("access_token")
        team_id = data.get("team", {}).get("id")
        team_name = data.get("team", {}).get("name")
        bot_user_id = data.get("bot_user_id")
        scopes = data.get("scope", "").split(",")
        
        # Store in database (Integration model)
        result = await db.execute(
            select(Integration).where(
                Integration.organization_id == org_id,
                Integration.type == IntegrationType.SLACK
            )
        )
        existing_integration = result.scalar_one_or_none()
        
        if existing_integration:
            # Update existing
            existing_integration.is_active = True
            existing_integration.config = {
                "access_token": access_token,
                "team_id": team_id,
                "team_name": team_name,
                "bot_user_id": bot_user_id,
                "scopes": scopes
            }
            existing_integration.updated_at = datetime.utcnow()
        else:
            # Create new
            new_integration = Integration(
                id=uuid.uuid4(),
                organization_id=uuid.UUID(org_id),
                name=f"Slack - {team_name}",
                type=IntegrationType.SLACK,
                is_active=True,
                config={
                    "access_token": access_token,
                    "team_id": team_id,
                    "team_name": team_name,
                    "bot_user_id": bot_user_id,
                    "scopes": scopes
                },
                created_at=datetime.utcnow()
            )
            db.add(new_integration)
        
        await db.commit()
        
        print(f"✅ Slack OAuth successful for user: {user_id}, team: {team_name}")
        
        return {
            "success": True,
            "workspace_name": team_name,
            "team_id": team_id,
            "bot_user_id": bot_user_id,
            "message": "Slack connected successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Slack OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def slack_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Check Slack connection status"""
    try:
        # Check if user has Slack integration configured in database
        result = await db.execute(
            select(Integration).where(
                Integration.organization_id == current_user.organization_id,
                Integration.type == IntegrationType.SLACK,
                Integration.is_active == True
            )
        )
        integration = result.scalar_one_or_none()
        
        if integration:
            config = integration.config or {}
            return {
                "connected": True,
                "workspace_name": config.get("team_name"),
                "bot_user_id": config.get("bot_user_id"),
                "team_id": config.get("team_id")
            }
        else:
            return {
                "connected": False,
                "workspace_name": None,
                "bot_user_id": None,
                "team_id": None
            }
        
    except Exception as e:
        print(f"❌ Slack status check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disconnect")
async def disconnect_slack(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Disconnect Slack integration"""
    try:
        # Remove Slack integration from database
        result = await db.execute(
            select(Integration).where(
                Integration.organization_id == current_user.organization_id,
                Integration.type == IntegrationType.SLACK
            )
        )
        integration = result.scalar_one_or_none()
        
        if integration:
            integration.is_active = False
            integration.updated_at = datetime.utcnow()
            await db.commit()
        
        print(f"✅ Slack disconnected for user: {current_user.id}")
        
        return {
            "success": True,
            "message": "Slack disconnected successfully"
        }
        
    except Exception as e:
        print(f"❌ Slack disconnect error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test")
async def send_test_message(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Send a test message to Slack (requires Slack connection)"""
    try:
        # Parse request
        body = await request.json()
        channel = body.get("channel", "#all-offcallai")
        message = body.get("message", "🚨 Test from OffCall AI!")
        
        # Get user's Slack token from database
        result = await db.execute(
            select(Integration).where(
                Integration.organization_id == current_user.organization_id,
                Integration.type == IntegrationType.SLACK,
                Integration.is_active == True
            )
        )
        integration = result.scalar_one_or_none()
        
        if not integration:
            raise HTTPException(status_code=404, detail="Slack not connected")
        
        access_token = integration.config.get("access_token")
        
        # Send message
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"channel": channel, "text": message}
            )
            result_data = response.json()
            
            if not result_data.get("ok"):
                raise HTTPException(status_code=400, detail=result_data.get("error"))
        
        return {
            "success": True,
            "message": "Test message sent to Slack",
            "channel": channel
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Slack test message error: {e}")
        raise HTTPException(status_code=500, detail=str(e))