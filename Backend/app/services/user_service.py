from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError
from app.core.database import get_database
from app.core.security import get_password_hash, verify_password, create_access_token
from app.models.user import UserCreate, UserInDB, User, UserResponse

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
    hashed_password = get_password_hash(user.password)
    user_dict = user.model_dump(exclude={"password"})
    
    user_in_db = UserInDB(
        **user_dict,
        hashed_password=hashed_password,
        fb_graph_api_key="",
        fb_ad_account_id="",
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