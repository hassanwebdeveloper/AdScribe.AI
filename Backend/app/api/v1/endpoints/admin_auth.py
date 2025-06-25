from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr
from typing import Optional

from app.services.admin_auth_service import admin_auth_service

router = APIRouter()

class SendOTPRequest(BaseModel):
    email: EmailStr

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp_code: str

class AuthResponse(BaseModel):
    success: bool
    message: str
    token: Optional[str] = None
    expires_in: Optional[int] = None

class SessionResponse(BaseModel):
    success: bool
    message: str
    email: Optional[str] = None

@router.post("/send-otp", response_model=AuthResponse)
async def send_admin_otp(request: SendOTPRequest):
    """
    Send OTP to authorized admin email
    """
    result = await admin_auth_service.send_otp(request.email)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return AuthResponse(**result)

@router.post("/verify-otp", response_model=AuthResponse)
async def verify_admin_otp(request: VerifyOTPRequest):
    """
    Verify OTP and get admin session token
    """
    result = await admin_auth_service.verify_otp(request.email, request.otp_code)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return AuthResponse(**result)

@router.get("/verify-session", response_model=SessionResponse)
async def verify_admin_session(authorization: Optional[str] = Header(None)):
    """
    Verify current admin session
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    token = authorization.split(" ")[1]
    result = await admin_auth_service.verify_session(token)
    
    if not result["success"]:
        raise HTTPException(status_code=401, detail=result["message"])
    
    return SessionResponse(**result)

@router.post("/logout", response_model=SessionResponse)
async def logout_admin(authorization: Optional[str] = Header(None)):
    """
    Logout admin user
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    token = authorization.split(" ")[1]
    result = await admin_auth_service.logout(token)
    
    return SessionResponse(**result) 