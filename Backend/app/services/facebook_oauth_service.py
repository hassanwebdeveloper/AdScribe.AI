import httpx
from typing import Dict, Any, Optional
import logging
from urllib.parse import urlencode
from app.core.config import settings

logger = logging.getLogger(__name__)

class FacebookOAuthService:
    def __init__(self):
        self.client_id = settings.FACEBOOK_CLIENT_ID
        self.client_secret = settings.FACEBOOK_CLIENT_SECRET
        self.redirect_uri = settings.FACEBOOK_REDIRECT_URI
        self.frontend_url = settings.FRONTEND_URL
    
    def get_authorization_url(self) -> str:
        """Get the Facebook authorization URL for login."""
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': 'email,public_profile,ads_management,ads_read',
            'response_type': 'code',
            'state': 'oauth'  # Should be a random token to prevent CSRF
        }
        return f"https://www.facebook.com/v17.0/dialog/oauth?{urlencode(params)}"
    
    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """Exchange the authorization code for an access token."""
        params = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': self.redirect_uri,
            'code': code,
        }
        
        url = f"https://graph.facebook.com/v17.0/oauth/access_token"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
    
    async def get_long_lived_token(self, short_lived_token: str) -> Dict[str, Any]:
        """Exchange a short-lived token for a long-lived token."""
        params = {
            'grant_type': 'fb_exchange_token',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'fb_exchange_token': short_lived_token,
        }
        
        url = f"https://graph.facebook.com/v17.0/oauth/access_token"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
    
    async def get_user_profile(self, access_token: str) -> Dict[str, Any]:
        """Get the user's Facebook profile."""
        params = {
            'fields': 'id,name,email',
            'access_token': access_token,
        }
        
        url = f"https://graph.facebook.com/v17.0/me"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
    
    async def get_ad_accounts(self, access_token: str) -> Dict[str, Any]:
        """Get the user's Facebook ad accounts."""
        params = {
            'fields': 'id,name,account_status',
            'access_token': access_token,
        }
        
        url = f"https://graph.facebook.com/v17.0/me/adaccounts"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
    
    def get_login_success_redirect_url(self, token: str) -> str:
        """Get URL to redirect user after successful login."""
        return f"{self.frontend_url}/auth/facebook/success?token={token}"
    
    def get_login_failure_redirect_url(self, error: str) -> str:
        """Get URL to redirect user after failed login."""
        return f"{self.frontend_url}/auth/facebook/error?error={error}" 