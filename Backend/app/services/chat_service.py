import logging
from datetime import datetime
import json
from bson import ObjectId
from fastapi import HTTPException, status
from app.core.database import get_database
from app.models.chat import ChatSession, Message, AnalysisSettings, DateRange, Ad
from typing import List, Optional, Dict, Any

# Set up logging
logger = logging.getLogger(__name__)

async def get_chat_sessions(user_id: str) -> List[ChatSession]:
    """Get all chat sessions for a user."""
    logger.info("🔍 [DEBUG] Getting chat sessions for user: %s", user_id)
    db = get_database()
    
    # Find all chat sessions for the user
    chat_sessions = await db.chat_sessions.find({"user_id": user_id}).sort("updated_at", -1).to_list(None)
    
    # Convert to ChatSession models
    chat_sessions = [ChatSession(**session) for session in chat_sessions]
    logger.info("🔍 [DEBUG] Found %d chat sessions for user", len(chat_sessions))
    
    return chat_sessions


async def get_chat_session(session_id: str, user_id: str) -> ChatSession:
    """Get a specific chat session."""
    logger.info("🔍 [DEBUG] Getting chat session %s for user: %s", session_id, user_id)
    db = get_database()
    
    # Convert string ID to ObjectId
    try:
        if isinstance(session_id, str):
            session_id = ObjectId(session_id)
        else:
            session_id = session_id
    except Exception as e:
        logger.error("🚫 [ERROR] Error converting session_id to ObjectId: %s", str(e))
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
        logger.error("🚫 [ERROR] Chat session not found for ID: %s, user_id: %s", session_id, user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
        
    logger.info("🔍 [DEBUG] Found chat session %s with %d messages", 
                session.get("_id"), len(session.get("messages", [])))
    
    return ChatSession(**session)


async def create_chat_session(user_id: str, title: str) -> ChatSession:
    """Create a new chat session."""
    logger.info("🔍 [DEBUG] Creating new chat session for user: %s with title: %s", user_id, title)
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
    try:
        result = await db.chat_sessions.insert_one(session_dict)
        logger.info("✅ [DEBUG] Chat session created with ID: %s", result.inserted_id)
    except Exception as e:
        logger.error("🚫 [ERROR] Error creating chat session: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create chat session"
        )
    
    # Update the _id in the dict with the inserted ID
    session_dict["_id"] = str(result.inserted_id)
    
    # Return ChatSession model with the updated _id
    return ChatSession(**session_dict)


async def update_chat_session(session_id: str, user_id: str, messages: List[Message], title: Optional[str] = None) -> ChatSession:
    """Update a chat session with new messages."""
    logger.info("🔍 [DEBUG] Updating chat session %s for user: %s with %d messages", 
                session_id, user_id, len(messages))
    db = get_database()
    
    # Convert string ID to ObjectId
    try:
        if isinstance(session_id, str):
            obj_id = ObjectId(session_id)
            logger.info("🔍 [DEBUG] Converted string ID to ObjectId: %s", obj_id)
        else:
            obj_id = session_id
            logger.info("🔍 [DEBUG] Using provided ObjectId: %s", obj_id)
    except Exception as e:
        logger.error("🚫 [ERROR] Error converting session_id to ObjectId: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session ID format"
        )
    
    # Find the chat session - try with ObjectId first
    logger.info("🔍 [DEBUG] Finding session with ObjectId: %s", obj_id)
    session = await db.chat_sessions.find_one({"_id": obj_id, "user_id": user_id})
    
    # If not found, try with the original string ID
    if not session:
        logger.info("🔍 [DEBUG] Session not found with ObjectId, trying with string ID: %s", session_id)
        session = await db.chat_sessions.find_one({"_id": session_id, "user_id": user_id})
    
    if not session:
        logger.error("🚫 [ERROR] Chat session not found for ID: %s, user_id: %s", session_id, user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    logger.info("🔍 [DEBUG] Found session: %s with %d existing messages", 
                session.get("_id"), len(session.get("messages", [])))
    
    # Convert messages to dictionary format for MongoDB
    message_dicts = []
    ads_list = session.get("ads", [])  # Get existing ads list or create empty one
    logger.info("🔍 [DEBUG] Initial ads list from DB has %d items", len(ads_list))
    
    for i, msg in enumerate(messages):
        # Handle both direct model instances and dict-like objects
        if hasattr(msg, 'model_dump'):
            logger.info("🔍 [DEBUG] Converting message %d using model_dump", i)
            message_dict = msg.model_dump()
        else:
            # If it's already a dict-like object
            logger.info("🔍 [DEBUG] Converting message %d using dict()", i)
            message_dict = dict(msg)
        
        # Log whether message has ad field
        if 'ad' in message_dict:
            logger.info("🔍 [DEBUG] Message %d has 'ad' field: %s", i, 
                      "None" if message_dict['ad'] is None else "with value")
            # Log the ad content for debugging
            if message_dict['ad']:
                logger.info("🔍 [DEBUG] Ad content type: %s", type(message_dict['ad']))
                logger.info("🔍 [DEBUG] Ad content preview: %s", 
                          str(message_dict['ad'])[:100] if isinstance(message_dict['ad'], str) else message_dict['ad'])
        else:
            logger.info("🔍 [DEBUG] Message %d does NOT have 'ad' field", i)
        
        # Validate message format
        if 'id' not in message_dict or 'content' not in message_dict or 'role' not in message_dict:
            logger.warning("⚠️ [WARNING] Message %d is missing required fields: %s", i, message_dict)
        
        # Ensure start_date and end_date are present
        if 'start_date' not in message_dict or message_dict['start_date'] is None:
            logger.info("🔍 [DEBUG] Adding missing start_date to message %d", i)
            message_dict['start_date'] = datetime.utcnow()
        elif isinstance(message_dict['start_date'], str):
            try:
                # Try to parse the string as a datetime
                logger.info("🔍 [DEBUG] Converting start_date string to datetime: %s", message_dict['start_date'])
                message_dict['start_date'] = datetime.fromisoformat(message_dict['start_date'].replace('Z', '+00:00'))
                logger.info("🔍 [DEBUG] Converted start_date string to datetime for message %d: %s", i, message_dict['start_date'])
            except Exception as e:
                logger.warning("⚠️ [WARNING] Error parsing start_date as datetime: %s. Using current time instead.", str(e))
                message_dict['start_date'] = datetime.utcnow()
        
        if 'end_date' not in message_dict or message_dict['end_date'] is None:
            logger.info("🔍 [DEBUG] Adding missing end_date to message %d", i)
            message_dict['end_date'] = datetime.utcnow()
        elif isinstance(message_dict['end_date'], str):
            try:
                # Try to parse the string as a datetime
                logger.info("🔍 [DEBUG] Converting end_date string to datetime: %s", message_dict['end_date'])
                message_dict['end_date'] = datetime.fromisoformat(message_dict['end_date'].replace('Z', '+00:00'))
                logger.info("🔍 [DEBUG] Converted end_date string to datetime for message %d: %s", i, message_dict['end_date'])
            except Exception as e:
                logger.warning("⚠️ [WARNING] Error parsing end_date as datetime: %s. Using current time instead.", str(e))
                message_dict['end_date'] = datetime.utcnow()
            
        # Log date fields for debugging
        logger.info("🔍 [DEBUG] Message %d date fields - start: %s (type: %s), end: %s (type: %s)", 
                   i, 
                   message_dict.get('start_date'), type(message_dict.get('start_date')),
                   message_dict.get('end_date'), type(message_dict.get('end_date')))
        
        # Process ad if present in the message
        if 'ad' in message_dict and message_dict['ad']:
            try:
                # If ad is a JSON string, parse it into a dictionary
                if isinstance(message_dict['ad'], str):
                    logger.info("🔍 [DEBUG] Converting ad string to dictionary for message %d", i)
                    ad_data = json.loads(message_dict['ad'])
                    logger.info("🔍 [DEBUG] Successfully parsed ad JSON: %s", str(ad_data)[:100])
                else:
                    logger.info("🔍 [DEBUG] Ad is already a dictionary/object for message %d", i)
                    ad_data = message_dict['ad']
                
                # Log the ad data schema
                logger.info("🔍 [DEBUG] Ad data keys: %s", str(ad_data.keys()) if hasattr(ad_data, 'keys') else "Not a dict")
                
                # Create Ad model and add to ads list
                try:
                    logger.info("🔍 [DEBUG] Creating Ad model from data")
                    ad = Ad(**ad_data)
                    ad_dict = ad.model_dump()
                    logger.info("✅ [DEBUG] Successfully created Ad model: %s", ad.title)
                    
                    # Check if this ad already exists in the list (by title)
                    ad_exists = False
                    for existing_ad in ads_list:
                        if existing_ad.get('title') == ad.title:
                            ad_exists = True
                            break
                    
                    if not ad_exists:
                        ads_list.append(ad_dict)
                        logger.info("✅ [DEBUG] Added ad to ads list: %s", ad.title)
                    else:
                        logger.info("🔍 [DEBUG] Ad already exists in list, skipping: %s", ad.title)
                except Exception as e:
                    logger.error("🚫 [ERROR] Error creating Ad model: %s", str(e), exc_info=True)
            except json.JSONDecodeError as e:
                logger.error("🚫 [ERROR] JSON decode error processing ad data: %s", str(e), exc_info=True)
                logger.error("🚫 [ERROR] Invalid JSON in ad data: %s", message_dict['ad'][:100])
            except Exception as e:
                logger.error("🚫 [ERROR] Error processing ad data: %s", str(e), exc_info=True)
        
        message_dicts.append(message_dict)
    
    # Debug the message array we're about to save
    logger.info("🔍 [DEBUG] Updating messages for session %s, message count: %d", session_id, len(message_dicts))
    logger.info("🔍 [DEBUG] Final ads list count: %d", len(ads_list))
    if ads_list:
        logger.info("🔍 [DEBUG] First ad title: %s", ads_list[0].get('title', 'No title'))
    
    # Prepare update data
    update_data = {
        "messages": message_dicts,
        "ads": ads_list,
        "updated_at": datetime.utcnow()
    }
    
    if title:
        update_data["title"] = title
        logger.info("🔍 [DEBUG] Also updating title to: %s", title)
    
    # Use the session's actual _id from the database for updating
    actual_id = session["_id"]
    logger.info("🔍 [DEBUG] Using actual _id for update: %s (type: %s)", actual_id, type(actual_id))
    
    # Update the chat session
    try:
        result = await db.chat_sessions.update_one(
            {"_id": actual_id, "user_id": user_id},
            {"$set": update_data}
        )
        
        logger.info("🔍 [DEBUG] Update result - matched: %d, modified: %d", 
                    result.matched_count, result.modified_count)
        
        if result.modified_count == 0:
            if result.matched_count > 0:
                logger.warning("⚠️ [WARNING] Session matched but not modified - possible no changes needed")
            else:
                logger.error("🚫 [ERROR] No documents matched the query criteria")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Chat session could not be updated - no match found"
                )
    except Exception as e:
        logger.error("🚫 [ERROR] Database error updating session: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )
    
    # Get the updated chat session
    updated_session = await db.chat_sessions.find_one({"_id": actual_id})
    
    # Verify the updated session has the correct message count
    if updated_session and "messages" in updated_session:
        logger.info("✅ [DEBUG] Session after update has %d messages", len(updated_session["messages"]))
        logger.info("✅ [DEBUG] Session after update has %d ads", len(updated_session.get("ads", [])))
        
        # Check the ads in the updated session
        if "ads" in updated_session and updated_session["ads"]:
            logger.info("✅ [DEBUG] Ads were successfully saved to the session")
            for i, ad in enumerate(updated_session["ads"]):
                logger.info("✅ [DEBUG] Ad %d: %s", i, ad.get("title", "No title"))
        else:
            logger.warning("⚠️ [WARNING] No ads in the updated session")
    else:
        logger.error("🚫 [ERROR] Could not retrieve updated session or messages field is missing")
    
    return ChatSession(**updated_session)


async def delete_chat_session(session_id: str, user_id: str) -> bool:
    """Delete a chat session."""
    logger.info("🔍 [DEBUG] Deleting chat session %s for user: %s", session_id, user_id)
    db = get_database()
    
    # Convert string ID to ObjectId
    try:
        if isinstance(session_id, str):
            obj_id = ObjectId(session_id)
        else:
            obj_id = session_id
    except Exception as e:
        logger.error("🚫 [ERROR] Error converting session_id to ObjectId: %s", str(e))
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
        logger.error("🚫 [ERROR] Chat session not found for ID: %s, user_id: %s", session_id, user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    # Use the session's actual _id from the database for deleting
    actual_id = session["_id"]
    
    # Delete the chat session
    try:
        result = await db.chat_sessions.delete_one({"_id": actual_id, "user_id": user_id})
        
        if result.deleted_count == 0:
            logger.error("🚫 [ERROR] Failed to delete session %s", session_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found"
            )
        
        logger.info("✅ [DEBUG] Successfully deleted chat session %s", session_id)
    except Exception as e:
        logger.error("🚫 [ERROR] Error deleting chat session: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )
    
    return True


async def get_analysis_settings(user_id: str) -> Optional[AnalysisSettings]:
    """Get analysis settings for a user."""
    logger.info("🔍 [DEBUG] Getting analysis settings for user: %s", user_id)
    db = get_database()
    
    # Find analysis settings for the user
    settings = await db.analysis_settings.find_one({"user_id": user_id})
    
    if not settings:
        logger.info("🔍 [DEBUG] No analysis settings found for user: %s", user_id)
        return None
    
    logger.info("🔍 [DEBUG] Found analysis settings for user: %s", user_id)
    return AnalysisSettings(**settings)


async def update_analysis_settings(user_id: str, date_range: DateRange) -> AnalysisSettings:
    """Update or create analysis settings for a user."""
    logger.info("🔍 [DEBUG] Updating analysis settings for user: %s", user_id)
    db = get_database()
    
    # Convert date_range to dictionary
    date_range_dict = {}
    if hasattr(date_range, 'model_dump'):
        date_range_dict = date_range.model_dump()
        logger.info("🔍 [DEBUG] Converted date_range using model_dump")
    else:
        date_range_dict = dict(date_range)
        logger.info("🔍 [DEBUG] Converted date_range using dict()")
    
    logger.info("🔍 [DEBUG] Date range: %s", date_range_dict)
    
    # Check if settings exist
    existing_settings = await db.analysis_settings.find_one({"user_id": user_id})
    
    if existing_settings:
        logger.info("🔍 [DEBUG] Updating existing settings for user: %s", user_id)
        # Update existing settings
        try:
            result = await db.analysis_settings.update_one(
                {"user_id": user_id},
                {"$set": {
                    "date_range": date_range_dict,
                    "updated_at": datetime.utcnow()
                }}
            )
            
            if result.modified_count == 0:
                logger.warning("⚠️ [WARNING] Analysis settings not modified - possibly no changes")
        except Exception as e:
            logger.error("🚫 [ERROR] Error updating analysis settings: %s", str(e), exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Analysis settings could not be updated"
            )
        
        # Get the updated settings
        updated_settings = await db.analysis_settings.find_one({"user_id": user_id})
        logger.info("✅ [DEBUG] Successfully updated analysis settings for user: %s", user_id)
        return AnalysisSettings(**updated_settings)
    else:
        logger.info("🔍 [DEBUG] Creating new analysis settings for user: %s", user_id)
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
        try:
            result = await db.analysis_settings.insert_one(settings_dict)
            logger.info("✅ [DEBUG] Created new analysis settings with ID: %s", result.inserted_id)
        except Exception as e:
            logger.error("🚫 [ERROR] Error creating analysis settings: %s", str(e), exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create analysis settings"
            )
        
        # Get the created settings
        created_settings = await db.analysis_settings.find_one({"_id": result.inserted_id})
        
        return AnalysisSettings(**created_settings) 