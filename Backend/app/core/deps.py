from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from app.core.config import settings
from app.services.user_service import get_user_by_email
from app.models.user import User
from app.core.security import get_current_user_email

# OAuth2 setup for dependency injection
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """
    Get current user from the token.
    This is a dependency that can be used in API endpoints.
    """
    email = await get_current_user_email(token)
    user = await get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user 