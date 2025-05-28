from abc import ABC
from typing import Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection
from bson import ObjectId
from app.core.database import get_database
from app.core.deps import ensure_object_id, ensure_string_id
import logging

logger = logging.getLogger(__name__)

class BaseService(ABC):
    """Base service class with common database operations and utilities"""
    
    def __init__(self):
        self._db = None
    
    @property
    def db(self) -> AsyncIOMotorDatabase:
        """Get database instance lazily when needed."""
        if self._db is None:
            self._db = get_database()
        return self._db
    
    def get_collection(self, collection_name: str) -> AsyncIOMotorCollection:
        """Get a specific collection"""
        return self.db[collection_name]
    
    async def find_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Find user by ID with consistent ObjectId handling"""
        try:
            # Try with ObjectId first
            obj_id = ensure_object_id(user_id)
            user = await self.db.users.find_one({"_id": obj_id})
            
            if not user:
                # Try with string ID as fallback
                user = await self.db.users.find_one({"_id": user_id})
            
            return user
        except Exception as e:
            logger.error(f"Error finding user by ID {user_id}: {str(e)}")
            return None
    
    async def find_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Find user by email"""
        try:
            return await self.db.users.find_one({"email": email})
        except Exception as e:
            logger.error(f"Error finding user by email {email}: {str(e)}")
            return None
    
    def extract_facebook_credentials(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract Facebook credentials from user data in various formats"""
        credentials = {}
        
        # Check for facebook_credentials field
        if "facebook_credentials" in user_data and isinstance(user_data["facebook_credentials"], dict):
            credentials = user_data["facebook_credentials"].copy()
        
        # Check for legacy fields and merge
        if "fb_graph_api_key" in user_data and user_data["fb_graph_api_key"]:
            credentials["access_token"] = user_data["fb_graph_api_key"]
        
        if "fb_ad_account_id" in user_data and user_data["fb_ad_account_id"]:
            credentials["account_id"] = user_data["fb_ad_account_id"]
        
        if "facebook_access_token" in user_data and user_data["facebook_access_token"]:
            credentials["access_token"] = user_data["facebook_access_token"]
        
        return credentials
    
    def has_valid_facebook_credentials(self, credentials: Dict[str, Any]) -> bool:
        """Check if Facebook credentials are valid"""
        return bool(
            credentials.get("access_token") and 
            credentials.get("account_id")
        )
    
    async def get_user_with_facebook_credentials(self, user_id: str) -> tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """Get user and their Facebook credentials in one call"""
        user = await self.find_user_by_id(user_id)
        if not user:
            return None, {}
        
        credentials = self.extract_facebook_credentials(user)
        return user, credentials
    
    def ensure_object_id(self, id_value: Any) -> ObjectId:
        """Convert various ID formats to ObjectId"""
        return ensure_object_id(id_value)
    
    def ensure_string_id(self, id_value: Any) -> str:
        """Convert various ID formats to string"""
        return ensure_string_id(id_value)
    
    async def update_user_field(self, user_id: str, field_updates: Dict[str, Any]) -> bool:
        """Update specific fields for a user"""
        try:
            obj_id = self.ensure_object_id(user_id)
            result = await self.db.users.update_one(
                {"_id": obj_id},
                {"$set": field_updates}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {str(e)}")
            return False 