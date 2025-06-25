from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any
import logging
from pydantic import BaseModel

from app.core.database import get_database
from app.core.deps import get_current_user
from app.models.user import User

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

class PrerequisiteStatus(BaseModel):
    has_facebook_credentials: bool
    has_analyzed_ads: bool
    is_complete: bool
    missing_requirements: list[str]
    message: str

@router.get("/check", response_model=PrerequisiteStatus)
async def check_user_prerequisites(current_user: User = Depends(get_current_user)):
    """
    Check if user has completed all prerequisites to access advanced features.
    
    Prerequisites:
    1. Facebook Graph API key configured
    2. Facebook Ad Account ID configured  
    3. At least one ad analysis completed
    """
    try:
        db = get_database()
        
        # Check Facebook credentials
        has_facebook_credentials = bool(
            current_user.fb_graph_api_key and 
            current_user.fb_ad_account_id and
            current_user.fb_graph_api_key.strip() and
            current_user.fb_ad_account_id.strip()
        )
        
        # Check if user has any analyzed ads
        has_analyzed_ads = False
        ad_count = 0
        
        if has_facebook_credentials:
            ad_count = await db.ad_analyses.count_documents({
                "user_id": str(current_user.id)
            })
            has_analyzed_ads = ad_count > 0
        
        # Determine what's missing
        missing_requirements = []
        if not has_facebook_credentials:
            if not current_user.fb_graph_api_key or not current_user.fb_graph_api_key.strip():
                missing_requirements.append("Facebook Graph API Key")
            if not current_user.fb_ad_account_id or not current_user.fb_ad_account_id.strip():
                missing_requirements.append("Facebook Ad Account ID")
        
        if has_facebook_credentials and not has_analyzed_ads:
            missing_requirements.append("Ad Analysis (run at least one analysis)")
        
        is_complete = has_facebook_credentials and has_analyzed_ads
        
        # Generate user-friendly message
        if is_complete:
            message = f"All prerequisites completed! You have {ad_count} analyzed ads."
        else:
            if not has_facebook_credentials:
                message = "Please configure your Facebook credentials in Settings first."
            elif not has_analyzed_ads:
                message = "Please run ad analysis first to access advanced features."
            else:
                message = "Please complete the missing requirements to continue."
        
        logger.info(f"Prerequisites check for user {current_user.id}: complete={is_complete}, missing={missing_requirements}")
        
        return PrerequisiteStatus(
            has_facebook_credentials=has_facebook_credentials,
            has_analyzed_ads=has_analyzed_ads,
            is_complete=is_complete,
            missing_requirements=missing_requirements,
            message=message
        )
        
    except Exception as e:
        logger.error(f"Error checking prerequisites for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error checking user prerequisites"
        ) 