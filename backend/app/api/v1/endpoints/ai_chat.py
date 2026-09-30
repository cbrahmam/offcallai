# backend/app/api/v1/endpoints/ai_chat.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional
from datetime import datetime
import uuid
import base64
import logging
import json

from app.database import get_async_session
from app.models.user import User
from app.models.incident import Incident
from app.models.ai_chat import AIChatSession, AIChatMessage
from app.core.security import get_current_user
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

# Schemas
class ChatMessageCreate(BaseModel):
    content: str
    provider: str = 'claude'
    image_base64: Optional[str] = None

class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    provider: Optional[str]
    attachments: Optional[dict]
    created_at: datetime
    
    class Config:
        from_attributes = True

class ChatSessionResponse(BaseModel):
    id: str
    incident_id: str
    title: Optional[str]
    is_encrypted: bool
    created_at: datetime
    updated_at: Optional[datetime]
    message_count: int
    
    class Config:
        from_attributes = True

# CRITICAL: Routes use /{incident_id}/chat/* because router is registered with prefix="/incidents" in __init__.py
# This creates final paths: /api/v1/incidents/{incident_id}/chat/session, etc.

@router.get("/{incident_id}/chat/session", response_model=ChatSessionResponse)
async def get_chat_session(
    incident_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Get existing chat session or create new one"""
    logger.info(f"🔍 GET /{{incident_id}}/chat/session called with incident_id={incident_id}")
    try:
        # Validate incident exists and user has access
        incident_result = await db.execute(
            select(Incident).where(
                and_(
                    Incident.id == uuid.UUID(incident_id),
                    Incident.organization_id == current_user.organization_id
                )
            )
        )
        incident = incident_result.scalar_one_or_none()
        if not incident:
            logger.error(f"❌ Incident {incident_id} not found or no access")
            raise HTTPException(status_code=404, detail="Incident not found")
        
        # Check for existing session
        result = await db.execute(
            select(AIChatSession).where(
                and_(
                    AIChatSession.incident_id == uuid.UUID(incident_id),
                    AIChatSession.user_id == current_user.id
                )
            )
        )
        session = result.scalar_one_or_none()
        
        if not session:
            logger.info(f"📝 Creating new chat session for incident {incident_id}")
            # Create new session
            session = AIChatSession(
                id=uuid.uuid4(),
                incident_id=uuid.UUID(incident_id),
                user_id=current_user.id,
                organization_id=current_user.organization_id,
                title=f"AI Chat - {incident.title[:50]}",
                is_encrypted=True
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)
        else:
            logger.info(f"♻️ Reusing existing chat session {session.id}")
        
        # Get message count
        msg_result = await db.execute(
            select(AIChatMessage).where(AIChatMessage.session_id == session.id)
        )
        messages = msg_result.scalars().all()
        
        response = ChatSessionResponse(
            id=str(session.id),
            incident_id=str(session.incident_id),
            title=session.title,
            is_encrypted=session.is_encrypted,
            created_at=session.created_at,
            updated_at=session.updated_at,
            message_count=len(messages)
        )
        logger.info(f"✅ Returning session {session.id} with {len(messages)} messages")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting chat session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{incident_id}/chat/messages", response_model=List[ChatMessageResponse])
async def get_chat_messages(
    incident_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Get all messages for incident chat session"""
    logger.info(f"🔍 GET /{{incident_id}}/chat/messages called with incident_id={incident_id}")
    try:
        # Get session
        session_result = await db.execute(
            select(AIChatSession).where(
                and_(
                    AIChatSession.incident_id == uuid.UUID(incident_id),
                    AIChatSession.user_id == current_user.id
                )
            )
        )
        session = session_result.scalar_one_or_none()
        
        if not session:
            logger.info(f"📝 No existing session, returning empty messages")
            return []
        
        # Get messages
        msg_result = await db.execute(
            select(AIChatMessage)
            .where(AIChatMessage.session_id == session.id)
            .order_by(AIChatMessage.created_at.asc())
        )
        messages = msg_result.scalars().all()
        
        response = [
            ChatMessageResponse(
                id=str(msg.id),
                role=msg.role,
                content=msg.content,
                provider=msg.provider,
                attachments=msg.message_metadata.get('attachments') if msg.message_metadata else None,
                created_at=msg.created_at
            )
            for msg in messages
        ]
        
        logger.info(f"✅ Returning {len(response)} messages")
        return response
        
    except Exception as e:
        logger.error(f"❌ Error getting chat messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{incident_id}/chat")
async def send_chat_message(
    incident_id: str,
    message: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Send a message and get AI response"""
    logger.info(f"💬 POST /{{incident_id}}/chat called with incident_id={incident_id}, provider={message.provider}")
    try:
        # Validate incident
        incident_result = await db.execute(
            select(Incident).where(
                and_(
                    Incident.id == uuid.UUID(incident_id),
                    Incident.organization_id == current_user.organization_id
                )
            )
        )
        incident = incident_result.scalar_one_or_none()
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        # Get or create session
        session_result = await db.execute(
            select(AIChatSession).where(
                and_(
                    AIChatSession.incident_id == uuid.UUID(incident_id),
                    AIChatSession.user_id == current_user.id
                )
            )
        )
        session = session_result.scalar_one_or_none()
        
        if not session:
            session = AIChatSession(
                id=uuid.uuid4(),
                incident_id=uuid.UUID(incident_id),
                user_id=current_user.id,
                organization_id=current_user.organization_id,
                title=f"AI Chat - {incident.title[:50]}",
                is_encrypted=True
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)
        
        # Save user message
        user_msg = AIChatMessage(
            id=uuid.uuid4(),
            session_id=session.id,
            role="user",
            content=message.content,
            provider=None,
            message_metadata={
                'has_image': bool(message.image_base64),
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        db.add(user_msg)
        await db.flush()  # Flush to get user_msg.id
        
        # Get incident context for AI
        incident_result = await db.execute(
            select(Incident).where(Incident.id == uuid.UUID(incident_id))
        )
        incident = incident_result.scalar_one()
        
        incident_context = {
            'title': incident.title,
            'description': incident.description or '',
            'severity': incident.severity,
            'status': incident.status,
            'tags': incident.tags or [],
            'created_at': incident.created_at.isoformat()
        }
        
        # Load AI service with user's API keys (BYOK)
        from app.services.real_ai_service import RealAIService
        ai_service = RealAIService(db=db, organization_id=current_user.organization_id)
        await ai_service.load_user_api_keys()
        
        # Get AI response based on provider
        try:
            if message.provider == 'claude':
                analysis = await ai_service.analyze_incident_with_claude(incident_context)
                if analysis and isinstance(analysis, dict):
                    # Extract clean markdown summary
                    summary = analysis.get('summary', '')
                    actions = analysis.get('recommended_actions', [])
                    
                    ai_response_content = f"**Analysis:**\n{summary}"
                    if actions and len(actions) > 0:
                        ai_response_content += f"\n\n**Quick Actions:**\n" + "\n".join(f"• {action}" for action in actions[:3])
                else:
                    ai_response_content = "⚠️ Claude API key not configured. Add your Anthropic API key in Settings → API Keys."
                    
            elif message.provider == 'gemini':
                analysis = await ai_service.analyze_incident_with_gemini(incident_context)
                if analysis and isinstance(analysis, dict):
                    # Extract clean markdown summary
                    summary = analysis.get('summary', '')
                    actions = analysis.get('recommended_actions', [])
                    
                    ai_response_content = f"**Analysis:**\n{summary}"
                    if actions and len(actions) > 0:
                        ai_response_content += f"\n\n**Quick Actions:**\n" + "\n".join(f"• {action}" for action in actions[:3])
                else:
                    ai_response_content = "⚠️ Gemini API key not configured. Add your Google AI API key in Settings → API Keys."
                    
            elif message.provider == 'both':
                # Multi-AI consensus - get both and format cleanly
                analyses = await ai_service.multi_ai_analysis(incident_context)
                if analyses and isinstance(analyses, dict):
                    claude_data = analyses.get('claude', {})
                    gemini_data = analyses.get('gemini', {})
                    
                    parts = []
                    if claude_data.get('summary'):
                        parts.append(f"**Claude:**\n{claude_data['summary'][:300]}...")
                    if gemini_data.get('summary'):
                        parts.append(f"**Gemini:**\n{gemini_data['summary'][:300]}...")
                    
                    ai_response_content = "\n\n".join(parts) if parts else "⚠️ No AI providers configured."
                else:
                    ai_response_content = "⚠️ No AI providers configured. Add API keys in Settings → API Keys."
            else:
                ai_response_content = f"❌ Unknown provider: {message.provider}"
                
        except Exception as e:
            logger.error(f"AI analysis error: {e}", exc_info=True)
            ai_response_content = f"❌ AI analysis failed: {str(e)[:100]}"
        
        # Save AI response
        ai_msg = AIChatMessage(
            id=uuid.uuid4(),
            session_id=session.id,
            role="assistant",
            content=ai_response_content,
            provider=message.provider,
            message_metadata={
                'model': 'claude-sonnet-4' if message.provider == 'claude' else 'gemini-2.0-flash-exp',
                'timestamp': datetime.utcnow().isoformat(),
                'user_message_id': str(user_msg.id)
            }
        )
        db.add(ai_msg)
        
        await db.commit()
        await db.refresh(user_msg)
        await db.refresh(ai_msg)
        
        logger.info(f"✅ Chat exchange saved: user_msg={user_msg.id}, ai_msg={ai_msg.id}")
        
        # Return AI message in proper ChatMessageResponse format
        return ChatMessageResponse(
            id=str(ai_msg.id),
            role=ai_msg.role,
            content=ai_msg.content,
            provider=ai_msg.provider,
            attachments=None,
            created_at=ai_msg.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in chat: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{incident_id}/chat/stream")
async def stream_chat_message(
    incident_id: str,
    message: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Stream AI response for real-time chat experience"""
    logger.info(f"🌊 POST /{incident_id}/chat/stream called with provider={message.provider}")

    try:
        # Validate incident
        incident_result = await db.execute(
            select(Incident).where(
                and_(
                    Incident.id == uuid.UUID(incident_id),
                    Incident.organization_id == current_user.organization_id
                )
            )
        )
        incident = incident_result.scalar_one_or_none()
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")

        # Get or create session
        session_result = await db.execute(
            select(AIChatSession).where(
                and_(
                    AIChatSession.incident_id == uuid.UUID(incident_id),
                    AIChatSession.user_id == current_user.id
                )
            )
        )
        session = session_result.scalar_one_or_none()

        if not session:
            session = AIChatSession(
                id=uuid.uuid4(),
                incident_id=uuid.UUID(incident_id),
                user_id=current_user.id,
                organization_id=current_user.organization_id,
                title=f"AI Chat - {incident.title[:50]}",
                is_encrypted=True
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)

        # Save user message
        user_msg = AIChatMessage(
            id=uuid.uuid4(),
            session_id=session.id,
            role="user",
            content=message.content,
            provider=None,
            message_metadata={
                'has_image': bool(message.image_base64),
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        db.add(user_msg)
        await db.commit()

        # Get incident context
        incident_context = {
            'title': incident.title,
            'description': incident.description or '',
            'severity': incident.severity,
            'status': incident.status,
            'tags': incident.tags or [],
            'created_at': incident.created_at.isoformat()
        }

        # Load AI service
        from app.services.real_ai_service import RealAIService
        ai_service = RealAIService(db=db, organization_id=current_user.organization_id)
        await ai_service.load_user_api_keys()

        async def generate_stream():
            collected_content = []

            try:
                if message.provider == 'claude':
                    async for chunk in ai_service.stream_chat_with_claude(
                        incident_context,
                        message.content
                    ):
                        yield chunk
                        # Extract text for saving
                        if chunk.startswith('data: ') and '[DONE]' not in chunk:
                            try:
                                data = json.loads(chunk[6:].strip())
                                if 'text' in data:
                                    collected_content.append(data['text'])
                            except (json.JSONDecodeError, KeyError):
                                pass

                elif message.provider == 'gemini':
                    async for chunk in ai_service.stream_chat_with_gemini(
                        incident_context,
                        message.content
                    ):
                        yield chunk
                        if chunk.startswith('data: ') and '[DONE]' not in chunk:
                            try:
                                data = json.loads(chunk[6:].strip())
                                if 'text' in data:
                                    collected_content.append(data['text'])
                            except (json.JSONDecodeError, KeyError):
                                pass
                else:
                    yield "data: " + json.dumps({"error": f"Unknown provider: {message.provider}"}) + "\n\n"
                    return

            except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield "data: " + json.dumps({"error": str(e)}) + "\n\n"

            # Save AI response after streaming completes
            try:
                full_content = ''.join(collected_content)
                if full_content:
                    ai_msg = AIChatMessage(
                        id=uuid.uuid4(),
                        session_id=session.id,
                        role="assistant",
                        content=full_content,
                        provider=message.provider,
                        message_metadata={
                            'model': 'claude-sonnet-4' if message.provider == 'claude' else 'gemini-2.0-flash-exp',
                            'timestamp': datetime.utcnow().isoformat(),
                            'streamed': True
                        }
                    )
                    db.add(ai_msg)
                    await db.commit()
                    logger.info(f"✅ Streamed response saved: {len(full_content)} chars")
            except Exception as e:
                logger.error(f"Failed to save streamed response: {e}")

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Stream chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Route registration debug log
logger.info("🔧 ai_chat.py routes defined: /{incident_id}/chat/session, /{incident_id}/chat/messages, /{incident_id}/chat, /{incident_id}/chat/stream")