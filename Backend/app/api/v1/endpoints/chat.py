from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
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
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class ChatSessionCreate(BaseModel):
    title: str = "New Chat"


class ChatSessionUpdate(BaseModel):
    title: Optional[str] = None
    messages: List[Message] = []


class DateRangeUpdate(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@router.get("/sessions", response_model=List[ChatSession])
async def read_chat_sessions(email: str = Depends(get_current_user_email)):
    """
    Get all chat sessions for the current user.
    """
    user = await get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return await get_chat_sessions(user.id)


@router.get("/sessions/{session_id}", response_model=ChatSession)
async def read_chat_session(
    session_id: str,
    email: str = Depends(get_current_user_email)
):
    """
    Get a specific chat session.
    """
    user = await get_user_by_email(email)
    if not user:
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
    user = await get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return await create_chat_session(user.id, session_data.title)


@router.put("/sessions/{session_id}", response_model=ChatSession)
async def update_existing_chat_session(
    session_id: str,
    session_data: ChatSessionUpdate,
    email: str = Depends(get_current_user_email)
):
    """
    Update an existing chat session.
    """
    user = await get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return await update_chat_session(
        session_id,
        user.id,
        session_data.messages,
        session_data.title
    )


@router.delete("/sessions/{session_id}", response_model=dict)
async def delete_existing_chat_session(
    session_id: str,
    email: str = Depends(get_current_user_email)
):
    """
    Delete a chat session.
    """
    user = await get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    await delete_chat_session(session_id, user.id)
    
    return {"message": "Chat session deleted successfully"}


@router.get("/settings", response_model=AnalysisSettings)
async def read_analysis_settings(
    email: str = Depends(get_current_user_email)
):
    """
    Get analysis settings for the current user.
    """
    user = await get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    settings = await get_analysis_settings(user.id)
    
    if not settings:
        # Create default settings if none exist
        date_range = DateRange()
        settings = await update_analysis_settings(user.id, date_range)
    
    return settings


@router.put("/settings", response_model=AnalysisSettings)
async def update_user_analysis_settings(
    date_range: DateRangeUpdate,
    email: str = Depends(get_current_user_email)
):
    """
    Update analysis settings for the current user.
    """
    user = await get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Convert to DateRange model
    settings_date_range = DateRange(
        start_date=date_range.start_date,
        end_date=date_range.end_date
    )
    
    return await update_analysis_settings(user.id, settings_date_range) 