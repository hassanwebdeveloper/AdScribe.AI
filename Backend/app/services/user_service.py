from datetime import datetime, timedelta
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError
from typing import Optional, Dict, Any
from app.core.base_service import BaseService
from app.core.security import get_password_hash, verify_password, create_access_token
from app.models.user import UserCreate, UserInDB, User, UserResponse, FacebookProfile, FacebookCredentials

class UserService(BaseService):
    """User service with standardized database operations"""
    
    async def create_user(self, user: UserCreate) -> UserResponse:
        """Create a new user with the given user data."""
        # Check if user with this email already exists
        existing_user = await self.find_user_by_email(user.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )
        
        # Prepare user document
        user_dict = user.model_dump(exclude={"password"})
        
        user_in_db = UserInDB(
            **user_dict,
            hashed_password=get_password_hash(user.password) if user.password else None,
            fb_graph_api_key="",
            fb_ad_account_id="",
            is_facebook_login=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Create an index for email uniqueness (if it doesn't exist)
        await self.db.users.create_index("email", unique=True)
        
        try:
            # Insert the user
            user_data = user_in_db.model_dump(by_alias=True)
            # Convert _id from string to ObjectId if not already
            if "_id" in user_data and isinstance(user_data["_id"], str):
                user_data["_id"] = ObjectId(user_data["_id"])
                
            result = await self.db.users.insert_one(user_data)
            
            # Get the created user
            created_user = await self.db.users.find_one({"_id": result.inserted_id})
            
            # Ensure _id is converted to string if it's an ObjectId
            if created_user and "_id" in created_user and isinstance(created_user["_id"], ObjectId):
                created_user["_id"] = str(created_user["_id"])
            
            # Create token
            token = create_access_token(data={"sub": user.email})
            
            # Return user and token
            return UserResponse(
                user=User(**created_user),
                token=token
            )
        except DuplicateKeyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )
    
    async def get_user_by_email(self, email: str) -> Optional[UserInDB]:
        """Get a user by email."""
        user = await self.find_user_by_email(email)
        if not user:
            return None
        
        # Ensure _id is converted to string if it's an ObjectId
        if "_id" in user and isinstance(user["_id"], ObjectId):
            user["_id"] = str(user["_id"])
            
        return UserInDB(**user)
    
    async def authenticate_user(self, email: str, password: str) -> UserResponse:
        """Authenticate a user with email and password."""
        user = await self.get_user_by_email(email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # For Facebook users without a password
        if user.is_facebook_login and not user.hashed_password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Please log in with Facebook"
            )
        
        if not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Create token
        token = create_access_token(data={"sub": email})
        
        # Convert UserInDB to User
        user_dict = user.model_dump(exclude={"hashed_password"})
        # Return user and token
        return UserResponse(
            user=User(**user_dict),
            token=token
        )
    
    async def update_user_settings(self, email: str, settings: dict) -> User:
        """Update user settings."""
        # Find the user
        user = await self.find_user_by_email(email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Prepare update data
        update_data = {
            "updated_at": datetime.utcnow()
        }
        
        # Add settings to update data
        if "fb_graph_api_key" in settings:
            update_data["fb_graph_api_key"] = settings["fb_graph_api_key"]
        if "fb_ad_account_id" in settings:
            update_data["fb_ad_account_id"] = settings["fb_ad_account_id"]
        
        # Update the user
        user_id = user["_id"]
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        result = await self.db.users.update_one(
            {"_id": user_id},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User settings could not be updated"
            )
        
        # Get the updated user
        updated_user = await self.db.users.find_one({"_id": user_id})
        
        # Ensure _id is converted to string
        if "_id" in updated_user and isinstance(updated_user["_id"], ObjectId):
            updated_user["_id"] = str(updated_user["_id"])
        
        return User(**updated_user)
    
    async def find_or_create_facebook_user(self, fb_profile: dict, access_token: str, expires_in: int) -> UserResponse:
        """Find or create a user based on Facebook profile."""
        # Create Facebook profile object
        facebook_profile = FacebookProfile(
            id=fb_profile.get("id"),
            name=fb_profile.get("name"),
            email=fb_profile.get("email")
        )
        
        # Calculate token expiration
        token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        # Try to find user by Facebook ID
        user = await self.db.users.find_one({"facebook_profile.id": facebook_profile.id})
        
        # If user doesn't exist, try to find by email
        if not user and facebook_profile.email:
            user = await self.find_user_by_email(facebook_profile.email)
        
        # If user exists, update Facebook information
        if user:
            user_id = user["_id"]
            if isinstance(user_id, str):
                user_id = ObjectId(user_id)
            
            # Update user with Facebook profile and credentials
            update_data = {
                "facebook_profile": facebook_profile.model_dump(),
                "facebook_credentials": {
                    "access_token": access_token,
                    "account_id": "",  # Will be set later when user selects an ad account
                    "token_expires_at": token_expires_at
                },
                "is_facebook_login": True,
                "updated_at": datetime.utcnow()
            }
            
            # Update user
            await self.db.users.update_one(
                {"_id": user_id},
                {"$set": update_data}
            )
            
            # Get the updated user
            updated_user = await self.db.users.find_one({"_id": user_id})
            
            # Ensure _id is converted to string
            if "_id" in updated_user and isinstance(updated_user["_id"], ObjectId):
                updated_user["_id"] = str(updated_user["_id"])
            
            # Create token
            token = create_access_token(data={"sub": updated_user["email"]})
            
            return UserResponse(
                user=User(**updated_user),
                token=token
            )
        
        # If user doesn't exist, create a new one
        else:
            # Create new user with Facebook profile
            name = facebook_profile.name or "Facebook User"
            email = facebook_profile.email or f"fb_{facebook_profile.id}@facebook.com"
            
            user_create = UserCreate(
                name=name,
                email=email
            )
            
            # Create the user
            new_user = await self.create_user(user_create)
            
            # Update with Facebook profile and credentials
            user_id = new_user.user.id
            if isinstance(user_id, str):
                user_id = ObjectId(user_id)
            
            update_data = {
                "facebook_profile": facebook_profile.model_dump(),
                "facebook_credentials": {
                    "access_token": access_token,
                    "account_id": "",  # Will be set later when user selects an ad account
                    "token_expires_at": token_expires_at
                },
                "is_facebook_login": True,
                "updated_at": datetime.utcnow()
            }
            
            # Update user
            await self.db.users.update_one(
                {"_id": user_id},
                {"$set": update_data}
            )
            
            # Get the updated user
            updated_user = await self.db.users.find_one({"_id": user_id})
            
            # Ensure _id is converted to string
            if "_id" in updated_user and isinstance(updated_user["_id"], ObjectId):
                updated_user["_id"] = str(updated_user["_id"])
            
            return UserResponse(
                user=User(**updated_user),
                token=new_user.token
            )
    
    async def update_facebook_ad_account(self, user_id: str, account_id: str) -> User:
        """Update the Facebook ad account ID for a user."""
        # Find the user
        user = await self.find_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check if user has Facebook credentials
        if "facebook_credentials" not in user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User does not have Facebook credentials"
            )
        
        # Update Facebook account ID
        facebook_credentials = user["facebook_credentials"]
        facebook_credentials["account_id"] = account_id
        
        update_data = {
            "facebook_credentials": facebook_credentials,
            "updated_at": datetime.utcnow()
        }
        
        # Update the user using base service method
        success = await self.update_user_field(user_id, update_data)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Facebook ad account could not be updated"
            )
        
        # Get the updated user
        updated_user = await self.find_user_by_id(user_id)
        
        # Ensure _id is converted to string
        if "_id" in updated_user and isinstance(updated_user["_id"], ObjectId):
            updated_user["_id"] = str(updated_user["_id"])
        
        return User(**updated_user)
    
    async def get_facebook_credentials(self, user_id: str) -> Dict[str, Any]:
        """Get Facebook credentials for a user."""
        user = await self.find_user_by_id(user_id)
        if not user:
            return {}
        
        return self.extract_facebook_credentials(user)

# Standalone functions for backward compatibility
async def create_user(user: UserCreate) -> UserResponse:
    """Create a new user with the given user data."""
    service = UserService()
    return await service.create_user(user)

async def get_user_by_email(email: str) -> Optional[UserInDB]:
    """Get a user by email."""
    service = UserService()
    return await service.get_user_by_email(email)

async def authenticate_user(email: str, password: str) -> UserResponse:
    """Authenticate a user with email and password."""
    service = UserService()
    return await service.authenticate_user(email, password)

async def update_user_settings(email: str, settings: dict) -> User:
    """Update user settings."""
    service = UserService()
    return await service.update_user_settings(email, settings)

async def find_or_create_facebook_user(fb_profile: dict, access_token: str, expires_in: int) -> UserResponse:
    """Find or create a user based on Facebook profile."""
    service = UserService()
    return await service.find_or_create_facebook_user(fb_profile, access_token, expires_in)

async def update_facebook_ad_account(user_id: str, account_id: str) -> User:
    """Update the Facebook ad account ID for a user."""
    service = UserService()
    return await service.update_facebook_ad_account(user_id, account_id) 