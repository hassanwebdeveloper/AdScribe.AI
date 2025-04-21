import logging
from fastapi import APIRouter, Depends, HTTPException, status, Body
from typing import List, Optional, Any
from app.core.security import get_current_user_email
from app.services.user_service import get_user_by_email
from app.services.chat_service import (
    get_chat_sessions, 
    get_chat_session, 
    create_chat_session,
    update_chat_session,
    delete_chat_session,
    get_analysis_settings,
    update_analysis_settings
)
from app.models.chat import ChatSession, Message, AnalysisSettings, DateRange
from pydantic import BaseModel, Field
from datetime import datetime

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

class ChatSessionCreate(BaseModel):
    title: str = "New Chat"


class ChatSessionUpdate(BaseModel):
    title: Optional[str] = None
    messages: List[Message] = []
    
    class Config:
        # Allow extra fields to avoid validation errors with new fields
        extra = "allow"
        # Allow type conversion from strings to datetimes
        arbitrary_types_allowed = True


class DateRangeUpdate(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@router.get("/sessions", response_model=List[ChatSession])
async def read_chat_sessions(email: str = Depends(get_current_user_email)):
    """
    Get all chat sessions for the current user.
    """
    logger.info("🔍 [DEBUG] Getting chat sessions for user email: %s", email)
    user = await get_user_by_email(email)
    if not user:
        logger.error("🚫 [ERROR] User not found for email: %s", email)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    sessions = await get_chat_sessions(user.id)
    logger.info("🔍 [DEBUG] Found %d chat sessions for user %s", len(sessions), user.id)
    return sessions


@router.get("/sessions/{session_id}", response_model=ChatSession)
async def read_chat_session(
    session_id: str,
    email: str = Depends(get_current_user_email)
):
    """
    Get a specific chat session.
    """
    logger.info("🔍 [DEBUG] Getting chat session %s for user email: %s", session_id, email)
    user = await get_user_by_email(email)
    if not user:
        logger.error("🚫 [ERROR] User not found for email: %s", email)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return await get_chat_session(session_id, user.id)


@router.post("/sessions", response_model=ChatSession)
async def create_new_chat_session(
    session_data: ChatSessionCreate,
    email: str = Depends(get_current_user_email)
):
    """
    Create a new chat session.
    """
    logger.info("🔍 [DEBUG] Creating new chat session with title '%s' for user email: %s", 
                session_data.title, email)
    user = await get_user_by_email(email)
    if not user:
        logger.error("🚫 [ERROR] User not found for email: %s", email)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    session = await create_chat_session(user.id, session_data.title)
    logger.info("✅ [DEBUG] Created new chat session with ID: %s", session.id)
    return session


@router.put("/sessions/{session_id}", response_model=ChatSession)
async def update_existing_chat_session(
    session_id: str,
    session_data: ChatSessionUpdate,
    email: str = Depends(get_current_user_email)
):
    """
    Update an existing chat session.
    """
    logger.info("🔍 [DEBUG] Updating chat session %s for user email: %s", session_id, email)
    logger.info("🔍 [DEBUG] Received %d messages in update request", len(session_data.messages))
    
    # Log the first and last message for debugging
    if session_data.messages:
        first_msg = session_data.messages[0]
        last_msg = session_data.messages[-1]
        logger.info("🔍 [DEBUG] First message ID: %s, Role: %s", first_msg.id, first_msg.role)
        logger.info("🔍 [DEBUG] Last message ID: %s, Role: %s", last_msg.id, last_msg.role)
        
        # Log date fields for the last message
        logger.info("🔍 [DEBUG] Last message timestamp: %s (type: %s)", 
                   last_msg.timestamp, type(last_msg.timestamp))
        
        if hasattr(last_msg, 'start_date'):
            logger.info("🔍 [DEBUG] Last message start_date: %s (type: %s)", 
                       last_msg.start_date, type(last_msg.start_date))
        else:
            logger.info("⚠️ [WARNING] Last message has no start_date field")
            
        if hasattr(last_msg, 'end_date'):
            logger.info("🔍 [DEBUG] Last message end_date: %s (type: %s)", 
                       last_msg.end_date, type(last_msg.end_date))
        else:
            logger.info("⚠️ [WARNING] Last message has no end_date field")
    
    user = await get_user_by_email(email)
    if not user:
        logger.error("🚫 [ERROR] User not found for email: %s", email)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    logger.info("🔍 [DEBUG] Found user with ID: %s", user.id)
    
    try:
        updated_session = await update_chat_session(
            session_id,
            user.id,
            session_data.messages,
            session_data.title
        )
        logger.info("✅ [DEBUG] Successfully updated chat session %s, now has %d messages", 
                    session_id, len(updated_session.messages))
        return updated_session
    except Exception as e:
        logger.error("🚫 [ERROR] Failed to update session: %s", str(e), exc_info=True)
        raise


@router.delete("/sessions/{session_id}", response_model=dict)
async def delete_existing_chat_session(
    session_id: str,
    email: str = Depends(get_current_user_email)
):
    """
    Delete a chat session.
    """
    logger.info("🔍 [DEBUG] Deleting chat session %s for user email: %s", session_id, email)
    user = await get_user_by_email(email)
    if not user:
        logger.error("🚫 [ERROR] User not found for email: %s", email)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    await delete_chat_session(session_id, user.id)
    logger.info("✅ [DEBUG] Successfully deleted chat session %s", session_id)
    
    return {"message": "Chat session deleted successfully"}


@router.get("/settings", response_model=AnalysisSettings)
async def read_analysis_settings(
    email: str = Depends(get_current_user_email)
):
    """
    Get analysis settings for the current user.
    """
    logger.info("🔍 [DEBUG] Getting analysis settings for user email: %s", email)
    user = await get_user_by_email(email)
    if not user:
        logger.error("🚫 [ERROR] User not found for email: %s", email)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    settings = await get_analysis_settings(user.id)
    
    if not settings:
        logger.info("🔍 [DEBUG] No existing settings found, creating default settings")
        # Create default settings if none exist
        date_range = DateRange()
        settings = await update_analysis_settings(user.id, date_range)
    
    logger.info("🔍 [DEBUG] Retrieved analysis settings for user %s", user.id)
    return settings


@router.put("/settings", response_model=AnalysisSettings)
async def update_user_analysis_settings(
    date_range: DateRangeUpdate,
    email: str = Depends(get_current_user_email)
):
    """
    Update analysis settings for the current user.
    """
    logger.info("🔍 [DEBUG] Updating analysis settings for user email: %s", email)
    logger.info("🔍 [DEBUG] Date range: %s to %s", date_range.start_date, date_range.end_date)
    
    user = await get_user_by_email(email)
    if not user:
        logger.error("🚫 [ERROR] User not found for email: %s", email)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Convert to DateRange model
    settings_date_range = DateRange(
        start_date=date_range.start_date,
        end_date=date_range.end_date
    )
    
    updated_settings = await update_analysis_settings(user.id, settings_date_range)
    logger.info("✅ [DEBUG] Successfully updated analysis settings for user %s", user.id)
    return updated_settings 