from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from app.models.user import UserCreate, UserResponse, User
from app.services.user_service import create_user, authenticate_user, get_user_by_email, update_user_settings
from app.core.security import get_current_user_email
from app.core.deps import get_current_user

router = APIRouter()

class LoginRequest(BaseModel):
    email: str
    password: str

class UserSettingsUpdate(BaseModel):
    fb_graph_api_key: Optional[str] = None
    fb_ad_account_id: Optional[str] = None

@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(user: UserCreate):
    """
    Create a new user with the given user data.
    """
    return await create_user(user)

@router.post("/login", response_model=UserResponse)
async def login(request: LoginRequest):
    """
    Authenticate a user with email and password.
    """
    return await authenticate_user(request.email, request.password)

@router.get("/me", response_model=User)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Get the current authenticated user.
    """
    return current_user

@router.patch("/settings", response_model=User)
async def update_settings(
    settings: UserSettingsUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Update user settings.
    """
    return await update_user_settings(current_user.email, settings.model_dump(exclude_none=True)) 