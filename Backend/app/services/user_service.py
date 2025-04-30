from datetime import datetime, timedelta
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError
from app.core.database import get_database
from app.core.security import get_password_hash, verify_password, create_access_token
from app.models.user import UserCreate, UserInDB, User, UserResponse, FacebookProfile, FacebookCredentials

class UserService:
    async def create_user(self, user: UserCreate) -> UserResponse:
        """Create a new user with the given user data."""
        return await create_user(user)
    
    async def get_user_by_email(self, email: str) -> UserInDB:
        """Get a user by email."""
        return await get_user_by_email(email)
    
    async def authenticate_user(self, email: str, password: str) -> UserResponse:
        """Authenticate a user with email and password."""
        return await authenticate_user(email, password)
    
    async def update_user_settings(self, email: str, settings: dict) -> User:
        """Update user settings."""
        return await update_user_settings(email, settings)
    
    async def find_or_create_facebook_user(self, fb_profile: dict, access_token: str, expires_in: int) -> UserResponse:
        """Find or create a user based on Facebook profile."""
        return await find_or_create_facebook_user(fb_profile, access_token, expires_in)
    
    async def update_facebook_ad_account(self, user_id: str, account_id: str) -> User:
        """Update the Facebook ad account ID for a user."""
        return await update_facebook_ad_account(user_id, account_id)

async def create_user(user: UserCreate) -> UserResponse:
    """Create a new user with the given user data."""
    db = get_database()
    
    # Check if user with this email already exists
    existing_user = await db.users.find_one({"email": user.email})
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
    await db.users.create_index("email", unique=True)
    
    try:
        # Insert the user
        user_data = user_in_db.model_dump(by_alias=True)
        # Convert _id from string to ObjectId if not already
        if "_id" in user_data and isinstance(user_data["_id"], str):
            user_data["_id"] = ObjectId(user_data["_id"])
            
        result = await db.users.insert_one(user_data)
        
        # Get the created user
        created_user = await db.users.find_one({"_id": result.inserted_id})
        
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

async def get_user_by_email(email: str) -> UserInDB:
    """Get a user by email."""
    db = get_database()
    user = await db.users.find_one({"email": email})
    if not user:
        return None
    
    # Ensure _id is converted to string if it's an ObjectId
    if "_id" in user and isinstance(user["_id"], ObjectId):
        user["_id"] = str(user["_id"])
        
    return UserInDB(**user)

async def authenticate_user(email: str, password: str) -> UserResponse:
    """Authenticate a user with email and password."""
    user = await get_user_by_email(email)
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

async def update_user_settings(email: str, settings: dict) -> User:
    """Update user settings."""
    db = get_database()
    
    # Find the user
    user = await db.users.find_one({"email": email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Convert _id to ObjectId if it's a string
    user_id = user["_id"]
    if isinstance(user_id, str):
        user_id = ObjectId(user_id)
    
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
    result = await db.users.update_one(
        {"_id": user_id},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User settings could not be updated"
        )
    
    # Get the updated user
    updated_user = await db.users.find_one({"_id": user_id})
    
    # Ensure _id is converted to string
    if "_id" in updated_user and isinstance(updated_user["_id"], ObjectId):
        updated_user["_id"] = str(updated_user["_id"])
    
    return User(**updated_user)

async def find_or_create_facebook_user(fb_profile: dict, access_token: str, expires_in: int) -> UserResponse:
    """Find or create a user based on Facebook profile."""
    db = get_database()
    
    # Create Facebook profile object
    facebook_profile = FacebookProfile(
        id=fb_profile.get("id"),
        name=fb_profile.get("name"),
        email=fb_profile.get("email")
    )
    
    # Calculate token expiration
    token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    
    # Try to find user by Facebook ID
    user = await db.users.find_one({"facebook_profile.id": facebook_profile.id})
    
    # If user doesn't exist, try to find by email
    if not user and facebook_profile.email:
        user = await db.users.find_one({"email": facebook_profile.email})
    
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
        await db.users.update_one(
            {"_id": user_id},
            {"$set": update_data}
        )
        
        # Get the updated user
        updated_user = await db.users.find_one({"_id": user_id})
        
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
        new_user = await create_user(user_create)
        
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
        await db.users.update_one(
            {"_id": user_id},
            {"$set": update_data}
        )
        
        # Get the updated user
        updated_user = await db.users.find_one({"_id": user_id})
        
        # Ensure _id is converted to string
        if "_id" in updated_user and isinstance(updated_user["_id"], ObjectId):
            updated_user["_id"] = str(updated_user["_id"])
        
        return UserResponse(
            user=User(**updated_user),
            token=new_user.token
        )

async def update_facebook_ad_account(user_id: str, account_id: str) -> User:
    """Update the Facebook ad account ID for a user."""
    db = get_database()
    
    # Convert user_id to ObjectId if it's a string
    if isinstance(user_id, str):
        user_id = ObjectId(user_id)
    
    # Find the user
    user = await db.users.find_one({"_id": user_id})
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
    
    # Update the user
    result = await db.users.update_one(
        {"_id": user_id},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Facebook ad account could not be updated"
        )
    
    # Get the updated user
    updated_user = await db.users.find_one({"_id": user_id})
    
    # Ensure _id is converted to string
    if "_id" in updated_user and isinstance(updated_user["_id"], ObjectId):
        updated_user["_id"] = str(updated_user["_id"])
    
    return User(**updated_user) 