from fastapi import HTTPException, Header, Depends
from typing import Optional

from app.services.admin_auth_service import admin_auth_service

async def verify_admin_token(authorization: Optional[str] = Header(None)) -> str:
    """
    Dependency to verify admin authentication token
    
    Returns:
        Admin email if token is valid
        
    Raises:
        HTTPException: If token is invalid or missing
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Admin authentication required. Please provide a valid Bearer token."
        )
    
    token = authorization.split(" ")[1]
    result = await admin_auth_service.verify_session(token)
    
    if not result["success"]:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid or expired admin session: {result['message']}"
        )
    
    return result["email"] 