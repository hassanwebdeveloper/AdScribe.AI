from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from typing import Optional, Dict, Any
from bson import ObjectId
from app.core.config import settings
from app.core.database import get_database
from app.models.user import User
from app.core.security import get_current_user_email

# OAuth2 setup for dependency injection
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

class UserWithCredentials:
    """Enhanced user object that includes Facebook credentials and other metadata"""
    def __init__(self, user_data: Dict[str, Any]):
        self.user = User(**self._clean_user_data(user_data))
        self.facebook_credentials = self._extract_facebook_credentials(user_data)
        self.raw_data = user_data
    
    def _clean_user_data(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean user data for User model creation"""
        cleaned = user_data.copy()
        # Ensure _id is string for User model
        if "_id" in cleaned and isinstance(cleaned["_id"], ObjectId):
            cleaned["_id"] = str(cleaned["_id"])
        return cleaned
    
    def _extract_facebook_credentials(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
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
    
    def has_facebook_credentials(self) -> bool:
        """Check if user has valid Facebook credentials"""
        return bool(
            self.facebook_credentials.get("access_token") and 
            self.facebook_credentials.get("account_id")
        )
    
    def get_object_id(self) -> ObjectId:
        """Get user ID as ObjectId"""
        user_id = self.raw_data.get("_id")
        if isinstance(user_id, ObjectId):
            return user_id
        elif isinstance(user_id, str):
            return ObjectId(user_id)
        else:
            raise ValueError(f"Invalid user ID format: {user_id}")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """
    Get current user from the token.
    This is a dependency that can be used in API endpoints.
    """
    email = await get_current_user_email(token)
    user_with_creds = await get_current_user_with_credentials(token)
    return user_with_creds.user

async def get_current_user_with_credentials(token: str = Depends(oauth2_scheme)) -> UserWithCredentials:
    """
    Get current user with Facebook credentials from the token.
    This reduces database queries by fetching everything in one call.
    """
    email = await get_current_user_email(token)
    db = get_database()
    
    user_data = await db.users.find_one({"email": email})
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserWithCredentials(user_data)

# Utility functions for consistent ObjectId handling
def ensure_object_id(id_value: Any) -> ObjectId:
    """Convert various ID formats to ObjectId"""
    if isinstance(id_value, ObjectId):
        return id_value
    elif isinstance(id_value, str):
        try:
            return ObjectId(id_value)
        except Exception:
            raise ValueError(f"Invalid ObjectId format: {id_value}")
    else:
        raise ValueError(f"Cannot convert {type(id_value)} to ObjectId")

def ensure_string_id(id_value: Any) -> str:
    """Convert various ID formats to string"""
    if isinstance(id_value, ObjectId):
        return str(id_value)
    elif isinstance(id_value, str):
        return id_value
    else:
        raise ValueError(f"Cannot convert {type(id_value)} to string") 