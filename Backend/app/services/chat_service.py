import logging
from datetime import datetime
import json
from bson import ObjectId
from fastapi import HTTPException, status
from app.core.base_service import BaseService
from app.models.chat import ChatSession, Message, AnalysisSettings, DateRange, Ad
from typing import List, Optional, Dict, Any

# Set up logging
logger = logging.getLogger(__name__)

class ChatService(BaseService):
    """Chat service with standardized database operations"""
    
    async def get_chat_sessions(self, user_id: str) -> List[ChatSession]:
        """Get all chat sessions for a user."""
        logger.info("🔍 [DEBUG] Getting chat sessions for user: %s", user_id)
        
        # Find all chat sessions for the user
        chat_sessions = await self.db.chat_sessions.find({"user_id": user_id}).sort("updated_at", -1).to_list(None)
        
        # Convert to ChatSession models
        chat_sessions = [ChatSession(**session) for session in chat_sessions]
        logger.info("🔍 [DEBUG] Found %d chat sessions for user", len(chat_sessions))
        
        return chat_sessions

    async def get_chat_session(self, session_id: str, user_id: str) -> ChatSession:
        """Get a specific chat session."""
        logger.info("🔍 [DEBUG] Getting chat session %s for user: %s", session_id, user_id)
        
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
        session = await self.db.chat_sessions.find_one({"_id": session_id, "user_id": user_id})
        
        # If not found, try with the original string ID
        if not session and isinstance(session_id, ObjectId):
            session = await self.db.chat_sessions.find_one({"_id": str(session_id), "user_id": user_id})
        
        if not session:
            logger.error("🚫 [ERROR] Chat session not found for ID: %s, user_id: %s", session_id, user_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found"
            )
            
        logger.info("🔍 [DEBUG] Found chat session %s with %d messages", 
                    session.get("_id"), len(session.get("messages", [])))
        
        return ChatSession(**session)

    async def create_chat_session(self, user_id: str, title: str) -> ChatSession:
        """Create a new chat session."""
        logger.info("🔍 [DEBUG] Creating new chat session for user: %s with title: %s", user_id, title)
        
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
            result = await self.db.chat_sessions.insert_one(session_dict)
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

    async def update_chat_session(self, session_id: str, user_id: str, messages: List[Message], title: Optional[str] = None) -> ChatSession:
        """Update a chat session with new messages."""
        logger.info("🔍 [DEBUG] Updating chat session %s for user: %s with %d messages", 
                    session_id, user_id, len(messages))
        
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
        session = await self.db.chat_sessions.find_one({"_id": obj_id, "user_id": user_id})
        
        # If not found, try with the original string ID
        if not session:
            logger.info("🔍 [DEBUG] Session not found with ObjectId, trying with string ID: %s", session_id)
            session = await self.db.chat_sessions.find_one({"_id": session_id, "user_id": user_id})
        
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
                       i, message_dict['start_date'], type(message_dict['start_date']),
                       message_dict['end_date'], type(message_dict['end_date']))
            
            # Handle ad field and update ads list
            if 'ad' in message_dict and message_dict['ad'] is not None:
                ad_data = message_dict['ad']
                logger.info("🔍 [DEBUG] Processing ad data for message %d: %s", i, type(ad_data))
                
                # If ad_data is a string, try to parse it as JSON
                if isinstance(ad_data, str):
                    try:
                        ad_data = json.loads(ad_data)
                        logger.info("🔍 [DEBUG] Successfully parsed ad JSON for message %d", i)
                    except json.JSONDecodeError as e:
                        logger.warning("⚠️ [WARNING] Failed to parse ad JSON for message %d: %s", i, str(e))
                        ad_data = None
                
                # If we have valid ad data, add it to the ads list
                if ad_data and isinstance(ad_data, dict):
                    # Check if this ad already exists in the list (by some unique identifier)
                    ad_id = ad_data.get('id') or ad_data.get('ad_id') or ad_data.get('_id')
                    if ad_id:
                        # Check if ad already exists
                        existing_ad = next((ad for ad in ads_list if ad.get('id') == ad_id or ad.get('ad_id') == ad_id), None)
                        if not existing_ad:
                            ads_list.append(ad_data)
                            logger.info("🔍 [DEBUG] Added new ad to ads list: %s", ad_id)
                        else:
                            logger.info("🔍 [DEBUG] Ad already exists in ads list: %s", ad_id)
                    else:
                        # If no ID, just add it (might be duplicate but we can't tell)
                        ads_list.append(ad_data)
                        logger.info("🔍 [DEBUG] Added ad without ID to ads list")
            
            message_dicts.append(message_dict)
        
        logger.info("🔍 [DEBUG] Final ads list has %d items", len(ads_list))
        
        # Prepare update data
        update_data = {
            "messages": message_dicts,
            "ads": ads_list,
            "updated_at": datetime.utcnow()
        }
        
        if title is not None:
            update_data["title"] = title
        
        # Update the session
        try:
            result = await self.db.chat_sessions.update_one(
                {"_id": obj_id, "user_id": user_id},
                {"$set": update_data}
            )
            
            if result.modified_count == 0:
                logger.error("🚫 [ERROR] No documents were modified during update")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to update chat session"
                )
            
            logger.info("✅ [DEBUG] Successfully updated chat session")
            
        except Exception as e:
            logger.error("🚫 [ERROR] Error updating chat session: %s", str(e), exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update chat session"
            )
        
        # Get the updated session
        updated_session = await self.db.chat_sessions.find_one({"_id": obj_id, "user_id": user_id})
        
        if not updated_session:
            logger.error("🚫 [ERROR] Could not retrieve updated session")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve updated chat session"
            )
        
        logger.info("✅ [DEBUG] Retrieved updated session with %d messages and %d ads", 
                   len(updated_session.get("messages", [])), len(updated_session.get("ads", [])))
        
        return ChatSession(**updated_session)

    async def delete_chat_session(self, session_id: str, user_id: str) -> bool:
        """Delete a chat session."""
        logger.info("🔍 [DEBUG] Deleting chat session %s for user: %s", session_id, user_id)
        
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
        
        # Delete the session
        try:
            result = await self.db.chat_sessions.delete_one({"_id": obj_id, "user_id": user_id})
            
            if result.deleted_count == 0:
                logger.error("🚫 [ERROR] No chat session found to delete")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Chat session not found"
                )
            
            logger.info("✅ [DEBUG] Successfully deleted chat session")
            return True
            
        except Exception as e:
            logger.error("🚫 [ERROR] Error deleting chat session: %s", str(e), exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete chat session"
            )

    async def get_analysis_settings(self, user_id: str) -> Optional[AnalysisSettings]:
        """Get analysis settings for a user."""
        logger.info("🔍 [DEBUG] Getting analysis settings for user: %s", user_id)
        
        try:
            settings = await self.db.analysis_settings.find_one({"user_id": user_id})
            
            if settings:
                logger.info("🔍 [DEBUG] Found analysis settings for user")
                return AnalysisSettings(**settings)
            else:
                logger.info("🔍 [DEBUG] No analysis settings found for user")
                return None
                
        except Exception as e:
            logger.error("🚫 [ERROR] Error getting analysis settings: %s", str(e), exc_info=True)
            return None

    async def update_analysis_settings(self, user_id: str, date_range: DateRange) -> AnalysisSettings:
        """Update analysis settings for a user."""
        logger.info("🔍 [DEBUG] Updating analysis settings for user: %s", user_id)
        
        # Create analysis settings object
        settings = AnalysisSettings(
            user_id=user_id,
            date_range=date_range,
            updated_at=datetime.utcnow()
        )
        
        # Convert to dict for MongoDB
        settings_dict = settings.model_dump(by_alias=True)
        
        try:
            # Use upsert to create or update
            result = await self.db.analysis_settings.update_one(
                {"user_id": user_id},
                {"$set": settings_dict},
                upsert=True
            )
            
            logger.info("✅ [DEBUG] Successfully updated analysis settings")
            return settings
            
        except Exception as e:
            logger.error("🚫 [ERROR] Error updating analysis settings: %s", str(e), exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update analysis settings"
            )

# Create service instance
chat_service = ChatService()

# Standalone functions for backward compatibility
async def get_chat_sessions(user_id: str) -> List[ChatSession]:
    """Get all chat sessions for a user."""
    return await chat_service.get_chat_sessions(user_id)

async def get_chat_session(session_id: str, user_id: str) -> ChatSession:
    """Get a specific chat session."""
    return await chat_service.get_chat_session(session_id, user_id)

async def create_chat_session(user_id: str, title: str) -> ChatSession:
    """Create a new chat session."""
    return await chat_service.create_chat_session(user_id, title)

async def update_chat_session(session_id: str, user_id: str, messages: List[Message], title: Optional[str] = None) -> ChatSession:
    """Update a chat session with new messages."""
    return await chat_service.update_chat_session(session_id, user_id, messages, title)

async def delete_chat_session(session_id: str, user_id: str) -> bool:
    """Delete a chat session."""
    return await chat_service.delete_chat_session(session_id, user_id)

async def get_analysis_settings(user_id: str) -> Optional[AnalysisSettings]:
    """Get analysis settings for a user."""
    return await chat_service.get_analysis_settings(user_id)

async def update_analysis_settings(user_id: str, date_range: DateRange) -> AnalysisSettings:
    """Update analysis settings for a user."""
    return await chat_service.update_analysis_settings(user_id, date_range) 