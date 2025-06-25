import random
import string
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.database import get_database
from app.models.admin_otp import AdminOTP, AdminSession
from app.services.email_service import email_service

logger = logging.getLogger(__name__)

class AdminAuthService:
    """Service for admin authentication using OTP"""
    
    # Authorized admin emails
    AUTHORIZED_EMAILS = {
        "shoaibahmad99@gmail.com",
        "h.baig34@gmail.com"
    }
    
    def __init__(self):
        self.db: Optional[AsyncIOMotorDatabase] = None
    
    def get_db(self) -> AsyncIOMotorDatabase:
        """Get database connection"""
        if self.db is None:
            self.db = get_database()
        return self.db
    
    @staticmethod
    def generate_otp() -> str:
        """Generate a 6-digit OTP"""
        return ''.join(random.choices(string.digits, k=6))
    
    @staticmethod
    def is_authorized_email(email: str) -> bool:
        """Check if email is authorized for admin access"""
        return email.lower().strip() in AdminAuthService.AUTHORIZED_EMAILS
    
    async def send_otp(self, email: str) -> Dict[str, Any]:
        """
        Generate and send OTP to authorized email
        
        Args:
            email: Email address to send OTP to
            
        Returns:
            Dict with success status and message
        """
        try:
            email = email.lower().strip()
            
            # Check if email is authorized
            if not self.is_authorized_email(email):
                logger.warning(f"Unauthorized admin access attempt from: {email}")
                return {
                    "success": False,
                    "message": "Access denied. This email is not authorized for admin access."
                }
            
            # Generate OTP
            otp_code = self.generate_otp()
            
            # Save OTP to database
            db = self.get_db()
            
            # Invalidate any existing OTPs for this email
            await db.admin_otps.update_many(
                {"email": email, "is_used": False},
                {"$set": {"is_used": True}}
            )
            
            # Create new OTP
            admin_otp = AdminOTP.create_otp(email, otp_code)
            await db.admin_otps.insert_one(admin_otp.model_dump(by_alias=True))
            
            # Send OTP via email
            email_result = await email_service.send_admin_otp(email, otp_code)
            
            if email_result["success"]:
                return {
                    "success": True,
                    "message": f"OTP sent to {email}"
                }
            else:
                # If email fails, mark OTP as used to prevent use
                await db.admin_otps.update_one(
                    {"email": email, "otp_code": otp_code},
                    {"$set": {"is_used": True}}
                )
                return {
                    "success": False,
                    "message": "Failed to send OTP email. Please try again."
                }
                
        except Exception as e:
            logger.error(f"Error sending admin OTP: {e}")
            return {
                "success": False,
                "message": "Failed to send OTP. Please try again."
            }
    
    async def verify_otp(self, email: str, otp_code: str) -> Dict[str, Any]:
        """
        Verify OTP and create admin session
        
        Args:
            email: Email address
            otp_code: OTP code to verify
            
        Returns:
            Dict with success status, message, and token if successful
        """
        try:
            email = email.lower().strip()
            
            # Check if email is authorized
            if not self.is_authorized_email(email):
                return {
                    "success": False,
                    "message": "Access denied."
                }
            
            db = self.get_db()
            
            # Find the latest unused OTP for this email
            otp_doc = await db.admin_otps.find_one(
                {
                    "email": email,
                    "is_used": False,
                    "otp_code": otp_code
                },
                sort=[("created_at", -1)]
            )
            
            if not otp_doc:
                # Increment attempts for any matching OTP
                await db.admin_otps.update_many(
                    {"email": email, "is_used": False},
                    {"$inc": {"attempts": 1}}
                )
                
                return {
                    "success": False,
                    "message": "Invalid OTP code."
                }
            
            # Convert to model
            admin_otp = AdminOTP(**otp_doc)
            
            # Increment attempts
            await db.admin_otps.update_one(
                {"_id": otp_doc["_id"]},
                {"$inc": {"attempts": 1}}
            )
            
            # Check if OTP is valid
            if not admin_otp.is_valid():
                if admin_otp.is_expired():
                    message = "OTP has expired. Please request a new one."
                elif admin_otp.attempts >= 3:
                    message = "Too many failed attempts. Please request a new OTP."
                else:
                    message = "Invalid OTP."
                
                return {
                    "success": False,
                    "message": message
                }
            
            # Mark OTP as used
            await db.admin_otps.update_one(
                {"_id": otp_doc["_id"]},
                {"$set": {"is_used": True}}
            )
            
            # Generate JWT token for 8-hour session
            token_payload = {
                "email": email,
                "type": "admin",
                "exp": datetime.utcnow() + timedelta(hours=8),
                "iat": datetime.utcnow()
            }
            
            token = jwt.encode(
                token_payload,
                settings.jwt_secret_key,
                algorithm="HS256"
            )
            
            # Save admin session
            admin_session = AdminSession.create_session(email, token)
            await db.admin_sessions.insert_one(admin_session.model_dump(by_alias=True))
            
            logger.info(f"Admin login successful for: {email}")
            
            return {
                "success": True,
                "message": "Authentication successful",
                "token": token,
                "expires_in": 8 * 3600  # 8 hours in seconds
            }
            
        except Exception as e:
            logger.error(f"Error verifying admin OTP: {e}")
            return {
                "success": False,
                "message": "Verification failed. Please try again."
            }
    
    async def verify_session(self, token: str) -> Dict[str, Any]:
        """
        Verify admin session token
        
        Args:
            token: JWT token to verify
            
        Returns:
            Dict with success status and user info if valid
        """
        try:
            # Decode JWT token
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=["HS256"]
            )
            
            email = payload.get("email")
            token_type = payload.get("type")
            
            # Check token type and email authorization
            if token_type != "admin" or not self.is_authorized_email(email):
                return {
                    "success": False,
                    "message": "Invalid token"
                }
            
            # Check if session exists and is active
            db = self.get_db()
            session_doc = await db.admin_sessions.find_one({
                "email": email,
                "token": token,
                "is_active": True
            })
            
            if not session_doc:
                return {
                    "success": False,
                    "message": "Session not found or inactive"
                }
            
            admin_session = AdminSession(**session_doc)
            
            # Check if session is expired
            if admin_session.is_expired():
                # Mark session as inactive
                await db.admin_sessions.update_one(
                    {"_id": session_doc["_id"]},
                    {"$set": {"is_active": False}}
                )
                
                return {
                    "success": False,
                    "message": "Session expired"
                }
            
            return {
                "success": True,
                "email": email,
                "message": "Valid session"
            }
            
        except jwt.ExpiredSignatureError:
            return {
                "success": False,
                "message": "Token expired"
            }
        except jwt.InvalidTokenError:
            return {
                "success": False,
                "message": "Invalid token"
            }
        except Exception as e:
            logger.error(f"Error verifying admin session: {e}")
            return {
                "success": False,
                "message": "Session verification failed"
            }
    
    async def logout(self, token: str) -> Dict[str, Any]:
        """
        Logout admin user by deactivating session
        
        Args:
            token: JWT token to logout
            
        Returns:
            Dict with success status
        """
        try:
            db = self.get_db()
            
            # Deactivate session
            result = await db.admin_sessions.update_one(
                {"token": token},
                {"$set": {"is_active": False}}
            )
            
            if result.modified_count > 0:
                return {
                    "success": True,
                    "message": "Logged out successfully"
                }
            else:
                return {
                    "success": False,
                    "message": "Session not found"
                }
                
        except Exception as e:
            logger.error(f"Error during admin logout: {e}")
            return {
                "success": False,
                "message": "Logout failed"
            }

# Global instance
admin_auth_service = AdminAuthService() 