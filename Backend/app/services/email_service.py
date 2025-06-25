import smtplib
import logging
from typing import Dict, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Fix import conflicts by importing email modules differently
import email.mime.text
import email.mime.multipart

from app.core.config import settings

logger = logging.getLogger(__name__)

class EmailService:
    """Service for sending emails"""
    
    def __init__(self):
        # Email configuration from settings
        self.smtp_server = settings.smtp_server
        self.smtp_port = settings.smtp_port
        self.sender_email = settings.smtp_from_email
        self.sender_username = settings.smtp_username
        self.sender_password = settings.smtp_password
        self.executor = ThreadPoolExecutor(max_workers=2)
    
    def _send_email_sync(self, to_email: str, subject: str, html_content: str, text_content: str = None) -> bool:
        """
        Synchronous email sending function to run in thread pool
        """
        try:
            # Create message
            msg = email.mime.multipart.MIMEMultipart('alternative')
            msg['From'] = self.sender_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add text version if provided
            if text_content:
                text_part = email.mime.text.MIMEText(text_content, 'plain')
                msg.attach(text_part)
            
            # Add HTML version
            html_part = email.mime.text.MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Only attempt real email sending if credentials are configured
            if self.sender_username and self.sender_password:
                # Connect to server and send email
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls()
                    server.login(self.sender_username, self.sender_password)
                    server.send_message(msg)
                
                logger.info(f"Email sent successfully to {to_email}")
                return True
            else:
                logger.warning("Email credentials not configured - email not sent")
                return False
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to send email to {to_email}: {e}")
            
            # Provide specific guidance for common Gmail errors
            if "534" in error_msg and "Application-specific password required" in error_msg:
                logger.error("Gmail Error: You must use an App Password, not your regular Gmail password!")
                logger.error("Solution: Go to Google Account > Security > App passwords and generate one")
            elif "535" in error_msg and ("Username and Password not accepted" in error_msg or "authentication failed" in error_msg.lower()):
                logger.error("Gmail Error: Username/Password authentication failed")
                logger.error("Solution: Verify your App Password is correct (16 characters, no spaces)")
            
            return False
    
    async def send_email(self, to_email: str, subject: str, html_content: str, text_content: str = None) -> bool:
        """
        Asynchronous wrapper for sending emails
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._send_email_sync,
            to_email,
            subject,
            html_content,
            text_content
        )
    
    async def send_admin_otp(self, email: str, otp_code: str) -> Dict[str, Any]:
        """
        Send OTP email to admin user
        
        Args:
            email: Admin email address
            otp_code: 6-digit OTP code
            
        Returns:
            Dict with success status and message
        """
        try:
            subject = "AdScribe.AI Admin Panel - Your OTP Code"
            
            # HTML email template
            html_content = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Admin OTP - AdScribe.AI</title>
                <style>
                    body {{
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        background-color: #f5f5f5;
                        margin: 0;
                        padding: 20px;
                    }}
                    .container {{
                        max-width: 600px;
                        margin: 0 auto;
                        background: white;
                        border-radius: 10px;
                        overflow: hidden;
                        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    }}
                    .header {{
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        padding: 30px;
                        text-align: center;
                    }}
                    .header h1 {{
                        margin: 0;
                        font-size: 28px;
                        font-weight: 300;
                    }}
                    .content {{
                        padding: 40px 30px;
                        text-align: center;
                    }}
                    .otp-code {{
                        font-size: 36px;
                        font-weight: bold;
                        color: #667eea;
                        background: #f8f9ff;
                        padding: 20px;
                        border-radius: 8px;
                        letter-spacing: 8px;
                        margin: 30px 0;
                        border: 2px dashed #667eea;
                    }}
                    .warning {{
                        background: #fff3cd;
                        border: 1px solid #ffeaa7;
                        color: #856404;
                        padding: 15px;
                        border-radius: 5px;
                        margin: 20px 0;
                    }}
                    .footer {{
                        background: #f8f9fa;
                        padding: 20px;
                        text-align: center;
                        font-size: 14px;
                        color: #6c757d;
                        border-top: 1px solid #dee2e6;
                    }}
                    .security-note {{
                        font-size: 12px;
                        color: #dc3545;
                        margin-top: 10px;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🛡️ AdScribe.AI Admin Access</h1>
                        <p>Secure Authentication Code</p>
                    </div>
                    
                    <div class="content">
                        <h2>Your Admin OTP Code</h2>
                        <p>Use this code to access the AdScribe.AI admin panel:</p>
                        
                        <div class="otp-code">{otp_code}</div>
                        
                        <div class="warning">
                            <strong>⏰ Important:</strong> This code expires in <strong>1 minute</strong> for security reasons.
                        </div>
                        
                        <p>If you didn't request this code, please ignore this email. Someone may have mistakenly entered your email address.</p>
                        
                        <div class="security-note">
                            <strong>Security Notice:</strong> Never share this code with anyone. Our team will never ask for your OTP code.
                        </div>
                    </div>
                    
                    <div class="footer">
                        <p>This is an automated email from AdScribe.AI Admin System</p>
                        <p>Email sent to: {email}</p>
                        <p style="font-size: 11px; margin-top: 15px;">
                            This email was sent because an OTP was requested for admin access. 
                            Admin access is restricted to authorized personnel only.
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Plain text version for email clients that don't support HTML
            text_content = f"""
            AdScribe.AI Admin Panel - OTP Code
            
            Your admin access code is: {otp_code}
            
            This code expires in 1 minute for security reasons.
            
            If you didn't request this code, please ignore this email.
            
            Never share this code with anyone.
            
            ---
            AdScribe.AI Admin System
            """
            
            logger.info(f"Sending OTP email to {email}")
            
            # Send the email
            if self.sender_username and self.sender_password:
                # Real email sending
                success = await self.send_email(email, subject, html_content, text_content)
                if success:
                    return {
                        "success": True,
                        "message": f"OTP sent to {email}"
                    }
                else:
                    return {
                        "success": False,
                        "message": "Failed to send OTP email"
                    }
            else:
                # Email not configured - log OTP for development
                logger.info("=== EMAIL NOT CONFIGURED - DEVELOPMENT MODE ===")
                logger.info(f"To: {email}")
                logger.info(f"Subject: {subject}")
                logger.info(f"OTP Code: {otp_code}")
                logger.info("Configure SMTP settings in environment variables for production")
                logger.info("=== END EMAIL SIMULATION ===")
                
                return {
                    "success": True,
                    "message": f"OTP sent to {email} (check server logs - email not configured)"
                }
                    
        except Exception as e:
            logger.error(f"Error sending OTP email: {e}")
            return {
                "success": False,
                "message": "Failed to send OTP email"
            }

# Global instance
email_service = EmailService() 