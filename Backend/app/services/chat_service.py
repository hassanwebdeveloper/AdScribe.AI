from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException, status
from app.core.database import get_database
from app.models.chat import ChatSession, Message, AnalysisSettings, DateRange
from typing import List, Optional


async def get_chat_sessions(user_id: str) -> List[ChatSession]:
    """Get all chat sessions for a user."""
    db = get_database()
    
    # Find all chat sessions for the user
    chat_sessions = await db.chat_sessions.find({"user_id": user_id}).sort("updated_at", -1).to_list(None)
    
    return [ChatSession(**session) for session in chat_sessions]


async def get_chat_session(session_id: str, user_id: str) -> ChatSession:
    """Get a specific chat session."""
    db = get_database()
    
    # Convert string ID to ObjectId
    try:
        if isinstance(session_id, str):
            session_id = ObjectId(session_id)
    except Exception as e:
        print(f"Error converting session_id to ObjectId: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session ID format"
        )
    
    # Find the chat session - try with ObjectId first
    session = await db.chat_sessions.find_one({"_id": session_id, "user_id": user_id})
    
    # If not found, try with the original string ID
    if not session and isinstance(session_id, ObjectId):
        session = await db.chat_sessions.find_one({"_id": str(session_id), "user_id": user_id})
    
    if not session:
        print(f"Chat session not found for ID: {session_id}, user_id: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
        
    return ChatSession(**session)


async def create_chat_session(user_id: str, title: str) -> ChatSession:
    """Create a new chat session."""
    db = get_database()
    
    # Create a new chat session
    chat_session = ChatSession(
        user_id=user_id,
        title=title,
        messages=[],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    # Convert model to dict for MongoDB insertion
    session_dict = chat_session.model_dump(by_alias=True)
    
    # Insert the chat session
    result = await db.chat_sessions.insert_one(session_dict)
    
    # Update the _id in the dict with the inserted ID
    session_dict["_id"] = str(result.inserted_id)
    
    # Return ChatSession model with the updated _id
    return ChatSession(**session_dict)


async def update_chat_session(session_id: str, user_id: str, messages: List[Message], title: Optional[str] = None) -> ChatSession:
    """Update a chat session with new messages."""
    db = get_database()
    
    # Convert string ID to ObjectId
    try:
        if isinstance(session_id, str):
            obj_id = ObjectId(session_id)
        else:
            obj_id = session_id
    except Exception as e:
        print(f"Error converting session_id to ObjectId: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session ID format"
        )
    
    # Find the chat session - try with ObjectId first
    session = await db.chat_sessions.find_one({"_id": obj_id, "user_id": user_id})
    
    # If not found, try with the original string ID
    if not session:
        session = await db.chat_sessions.find_one({"_id": session_id, "user_id": user_id})
    
    if not session:
        print(f"Chat session not found for ID: {session_id}, user_id: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    # Convert messages to dictionary format for MongoDB
    message_dicts = []
    for msg in messages:
        # Handle both direct model instances and dict-like objects
        if hasattr(msg, 'model_dump'):
            message_dicts.append(msg.model_dump())
        else:
            # If it's already a dict-like object
            message_dicts.append(dict(msg))
    
    # Debug the message array we're about to save
    print(f"Updating messages for session {session_id}, message count: {len(message_dicts)}")
    
    # Prepare update data
    update_data = {
        "messages": message_dicts,
        "updated_at": datetime.utcnow()
    }
    
    if title:
        update_data["title"] = title
    
    # Use the session's actual _id from the database for updating
    actual_id = session["_id"]
    
    # Update the chat session
    result = await db.chat_sessions.update_one(
        {"_id": actual_id, "user_id": user_id},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chat session could not be updated"
        )
    
    # Get the updated chat session
    updated_session = await db.chat_sessions.find_one({"_id": actual_id})
    
    # Verify the updated session has the correct message count
    if updated_session and "messages" in updated_session:
        print(f"Session after update has {len(updated_session['messages'])} messages")
    
    return ChatSession(**updated_session)


async def delete_chat_session(session_id: str, user_id: str) -> bool:
    """Delete a chat session."""
    db = get_database()
    
    # Convert string ID to ObjectId
    try:
        if isinstance(session_id, str):
            obj_id = ObjectId(session_id)
        else:
            obj_id = session_id
    except Exception as e:
        print(f"Error converting session_id to ObjectId: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session ID format"
        )
    
    # Try to find the session first to ensure it exists
    session = await db.chat_sessions.find_one({"_id": obj_id, "user_id": user_id})
    
    # If not found with ObjectId, try string ID
    if not session:
        session = await db.chat_sessions.find_one({"_id": session_id, "user_id": user_id})
        
    if not session:
        print(f"Chat session not found for ID: {session_id}, user_id: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    # Use the session's actual _id from the database for deleting
    actual_id = session["_id"]
    
    # Delete the chat session
    result = await db.chat_sessions.delete_one({"_id": actual_id, "user_id": user_id})
    
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    return True


async def get_analysis_settings(user_id: str) -> Optional[AnalysisSettings]:
    """Get analysis settings for a user."""
    db = get_database()
    
    # Find analysis settings for the user
    settings = await db.analysis_settings.find_one({"user_id": user_id})
    
    if not settings:
        return None
    
    return AnalysisSettings(**settings)


async def update_analysis_settings(user_id: str, date_range: DateRange) -> AnalysisSettings:
    """Update or create analysis settings for a user."""
    db = get_database()
    
    # Convert date_range to dictionary
    date_range_dict = {}
    if hasattr(date_range, 'model_dump'):
        date_range_dict = date_range.model_dump()
    else:
        date_range_dict = dict(date_range)
    
    # Check if settings exist
    existing_settings = await db.analysis_settings.find_one({"user_id": user_id})
    
    if existing_settings:
        # Update existing settings
        result = await db.analysis_settings.update_one(
            {"user_id": user_id},
            {"$set": {
                "date_range": date_range_dict,
                "updated_at": datetime.utcnow()
            }}
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Analysis settings could not be updated"
            )
        
        # Get the updated settings
        updated_settings = await db.analysis_settings.find_one({"user_id": user_id})
        return AnalysisSettings(**updated_settings)
    else:
        # Create new settings
        settings = AnalysisSettings(
            user_id=user_id,
            date_range=date_range,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Insert the settings - make sure we properly handle the model
        settings_dict = settings.model_dump(by_alias=True)
        
        # Insert the settings
        result = await db.analysis_settings.insert_one(settings_dict)
        
        # Get the created settings
        created_settings = await db.analysis_settings.find_one({"_id": result.inserted_id})
        
        return AnalysisSettings(**created_settings) 