from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, Field
from bson import ObjectId


class AdminOTP(BaseModel):
    """Model for admin OTP verification"""
    id: Optional[str] = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    email: str = Field(..., description="Admin email address")
    otp_code: str = Field(..., description="6-digit OTP code")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(..., description="OTP expiration time")
    is_used: bool = Field(default=False, description="Whether OTP has been used")
    attempts: int = Field(default=0, description="Number of verification attempts")
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}
        
    @classmethod
    def create_otp(cls, email: str, otp_code: str) -> "AdminOTP":
        """Create a new OTP with 1-minute expiration"""
        return cls(
            email=email,
            otp_code=otp_code,
            expires_at=datetime.utcnow() + timedelta(minutes=1)
        )
    
    def is_expired(self) -> bool:
        """Check if OTP has expired"""
        return datetime.utcnow() > self.expires_at
    
    def is_valid(self) -> bool:
        """Check if OTP is valid (not expired, not used, attempts < 3)"""
        return not self.is_expired() and not self.is_used and self.attempts < 3


class AdminSession(BaseModel):
    """Model for admin session management"""
    id: Optional[str] = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    email: str = Field(..., description="Admin email address")
    token: str = Field(..., description="JWT session token")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(..., description="Session expiration time")
    is_active: bool = Field(default=True, description="Whether session is active")
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}
        
    @classmethod
    def create_session(cls, email: str, token: str) -> "AdminSession":
        """Create a new admin session with 8-hour expiration"""
        return cls(
            email=email,
            token=token,
            expires_at=datetime.utcnow() + timedelta(hours=8)
        )
    
    def is_expired(self) -> bool:
        """Check if session has expired"""
        return datetime.utcnow() > self.expires_at
    
    def is_valid(self) -> bool:
        """Check if session is valid (not expired and active)"""
        return not self.is_expired() and self.is_active 