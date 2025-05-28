from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional, Any, Dict
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings
from app.core.database import get_database
from app.models.user import UserCreate, UserResponse, User, FacebookCredentialsUpdate
from app.services.user_service import UserService, create_user, authenticate_user, get_user_by_email, update_user_settings
from app.core.security import get_current_user_email, create_access_token
from app.core.deps import get_current_user, get_current_user_with_credentials, UserWithCredentials
from app.services.scheduler_service import SchedulerService
from app.services.facebook_oauth_service import FacebookOAuthService

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/token")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
user_service = UserService()

# Use lazy loading for scheduler service
def get_scheduler_service():
    return SchedulerService()

# Use lazy loading for Facebook OAuth service
def get_facebook_oauth_service():
    return FacebookOAuthService()

class LoginRequest(BaseModel):
    email: str
    password: str

class UserSettingsUpdate(BaseModel):
    fb_graph_api_key: Optional[str] = None
    fb_ad_account_id: Optional[str] = None

class FacebookAdAccountRequest(BaseModel):
    account_id: str

class TokenRefreshRequest(BaseModel):
    refresh_token: str

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
    user_response = await authenticate_user(request.email, request.password)
    
    # Create refresh token with longer expiration
    refresh_token = create_access_token(
        data={"sub": request.email},
        expires_delta=timedelta(days=30)  # Refresh token lasts 30 days
    )
    
    # Add refresh token to response
    user_response.refresh_token = refresh_token
    
    return user_response

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

@router.post("/facebook-credentials")
async def update_facebook_credentials(
    credentials: FacebookCredentialsUpdate, 
    user_with_creds: UserWithCredentials = Depends(get_current_user_with_credentials)
):
    """
    Update Facebook credentials for the current user and schedule metrics collection.
    """
    user_id = user_with_creds.user.id
    db = get_database()
    
    # Calculate token expiration (90 days from now as a default)
    token_expires_at = datetime.utcnow() + timedelta(days=90)
    
    # Update the user's Facebook credentials using ObjectId
    obj_id = user_with_creds.get_object_id()
    result = await db.users.update_one(
        {"_id": obj_id},
        {
            "$set": {
                "facebook_credentials": {
                    "access_token": credentials.access_token,
                    "account_id": credentials.account_id,
                    "token_expires_at": token_expires_at
                },
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update Facebook credentials"
        )
    
    # Get scheduler service instance and schedule metrics collection
    scheduler_service = get_scheduler_service()
    await scheduler_service.schedule_metrics_collection_for_user(user_id)
    
    return {"message": "Facebook credentials updated and metrics collection scheduled"}

@router.get("/facebook/login")
async def facebook_login():
    """
    Redirect to Facebook for OAuth authentication.
    """
    # Get Facebook OAuth service
    fb_oauth_service = get_facebook_oauth_service()
    
    # Get authorization URL
    auth_url = fb_oauth_service.get_authorization_url()
    
    # Redirect to Facebook
    return RedirectResponse(url=auth_url)

@router.get("/facebook/callback")
async def facebook_callback(code: str, state: Optional[str] = None):
    """
    Handle the callback from Facebook OAuth.
    """
    fb_oauth_service = get_facebook_oauth_service()
    
    try:
        # Exchange the code for an access token
        token_data = await fb_oauth_service.exchange_code_for_token(code)
        
        # Get short-lived access token
        access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in", 0)
        
        # Exchange for long-lived token
        long_lived_token_data = await fb_oauth_service.get_long_lived_token(access_token)
        long_lived_token = long_lived_token_data.get("access_token")
        long_lived_expires_in = long_lived_token_data.get("expires_in", 0)
        
        # Get user profile
        fb_profile = await fb_oauth_service.get_user_profile(long_lived_token)
        
        # Find or create user
        user_response = await user_service.find_or_create_facebook_user(fb_profile, long_lived_token, long_lived_expires_in)
        
        # Redirect to frontend with token
        redirect_url = fb_oauth_service.get_login_success_redirect_url(user_response.token)
        return RedirectResponse(url=redirect_url)
        
    except Exception as e:
        # Redirect to frontend with error
        error_url = fb_oauth_service.get_login_failure_redirect_url(str(e))
        return RedirectResponse(url=error_url)

@router.post("/facebook/ad-account", response_model=User)
async def set_facebook_ad_account(
    request: FacebookAdAccountRequest,
    user_with_creds: UserWithCredentials = Depends(get_current_user_with_credentials)
):
    """
    Set the Facebook ad account to use for metrics collection.
    """
    # Update the ad account
    updated_user = await user_service.update_facebook_ad_account(user_with_creds.user.id, request.account_id)
    
    # Schedule metrics collection
    scheduler_service = get_scheduler_service()
    await scheduler_service.schedule_metrics_collection_for_user(user_with_creds.user.id)
    
    return updated_user

@router.get("/facebook/ad-accounts")
async def get_facebook_ad_accounts(user_with_creds: UserWithCredentials = Depends(get_current_user_with_credentials)):
    """
    Get the list of Facebook ad accounts for the current user.
    """
    # Check if user has Facebook credentials
    if not user_with_creds.has_facebook_credentials():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Facebook credentials not found. Please connect your Facebook account first."
        )
    
    # Import Facebook service here to avoid circular imports
    from app.services.facebook_service import FacebookAdService
    
    try:
        # Create Facebook service with user's credentials
        fb_service = FacebookAdService(
            access_token=user_with_creds.facebook_credentials["access_token"],
            account_id=user_with_creds.facebook_credentials.get("account_id", "")
        )
        
        # Get ad accounts
        ad_accounts = await fb_service.get_ad_accounts()
        
        return {"ad_accounts": ad_accounts}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Facebook ad accounts: {str(e)}"
        )

@router.post("/refresh-token")
async def refresh_token(request: TokenRefreshRequest):
    """
    Refresh an access token using a refresh token.
    """
    try:
        # Verify the refresh token
        email = await get_current_user_email(request.refresh_token)
        
        # Create a new access token
        new_token = create_access_token(data={"sub": email})
        
        return {"access_token": new_token, "token_type": "bearer"}
        
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        ) 