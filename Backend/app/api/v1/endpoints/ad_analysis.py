from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.responses import JSONResponse
import httpx
from typing import List, Dict, Any
import json
import logging

from app.core.database import get_database
from app.core.deps import get_current_user
from app.core.config import settings
from app.models.user import User
from app.models.ad_analysis import AdAnalysis, AdAnalysisResponse

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/analyze/", response_model=List[AdAnalysisResponse], status_code=status.HTTP_201_CREATED)
async def analyze_ads(current_user: User = Depends(get_current_user)):
    """
    Analyze ads by calling the N8N webhook and storing the results in MongoDB.
    Requires the user to have a Facebook Graph API key and Ad Account ID.
    """
    # Check if user has Facebook Graph API key and Ad Account ID
    if not current_user.fb_graph_api_key or not current_user.fb_ad_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Facebook Graph API key and Ad Account ID are required. Please configure them in settings."
        )
    
    # Get database connection
    db = get_database()
    
    # Get existing video IDs from the database for this user
    existing_video_ids = []
    try:
        existing_analyses = await db.ad_analyses.find(
            {"user_id": str(current_user.id)}, 
            {"video_id": 1}
        ).to_list(length=1000)
        
        # Extract video IDs from results
        existing_video_ids = [
            analysis.get("video_id") for analysis in existing_analyses 
            if analysis.get("video_id") is not None
        ]
        logger.info(f"Found {len(existing_video_ids)} existing video IDs for user {current_user.id}")
    except Exception as e:
        logger.error(f"Error retrieving existing video IDs: {e}", exc_info=True)
        # Continue anyway - we'll just analyze all ads
    
    # Prepare payload for N8N with existing video IDs
    payload = {
        "fb_graph_api_key": current_user.fb_graph_api_key,
        "fb_ad_account_id": current_user.fb_ad_account_id,
        "existing_video_ids": existing_video_ids
    }
    
    # Get N8N webhook URL from settings
    n8n_webhook_url = settings.N8N_WEBHOOK_URL_ANALYZE_ALL_ADS
    if not n8n_webhook_url:
        logger.error("N8N webhook URL not configured in environment")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="N8N webhook URL not configured"
        )
    
    try:
        logger.info(f"Calling N8N webhook with {len(existing_video_ids)} existing video IDs")
        # Call N8N webhook with increased timeout (15 minutes)
        async with httpx.AsyncClient(timeout=900.0) as client:
            response = await client.post(n8n_webhook_url, json=payload)
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to analyze ads: {response.text}"
                )
            
            # Parse response and ensure it's an array
            try:
                response_data = response.json()
                if not isinstance(response_data, list):
                    logger.error(f"Expected list but got {type(response_data)}: {response_data}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Invalid response format from N8N webhook: expected a list"
                    )
                
                logger.info(f"Received {len(response_data)} new ad analyses from N8N")
                
                # If no new ads were found, return empty list
                if len(response_data) == 0:
                    logger.info("No new ads to analyze")
                    return []
                
                ad_analyses = response_data
            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON response: {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Invalid JSON response from N8N webhook"
                )
            
            # Store ad analyses in MongoDB
            stored_analyses = []
            for ad_analysis_data in ad_analyses:
                try:
                    # Check if this ad's video_id already exists to avoid duplicates
                    # (This is a safeguard even though we sent the IDs to N8N)
                    video_id = ad_analysis_data.get("video_id")
                    if video_id and video_id in existing_video_ids:
                        logger.info(f"Skipping already analyzed video: {video_id}")
                        continue
                    
                    # Create AdAnalysis object
                    ad_analysis = AdAnalysis(
                        user_id=str(current_user.id),
                        **ad_analysis_data
                    )
                    
                    # Insert into database
                    result = await db.ad_analyses.insert_one(ad_analysis.model_dump(by_alias=True))
                    
                    # Get the inserted document
                    stored_analysis = await db.ad_analyses.find_one({"_id": result.inserted_id})
                    stored_analyses.append(stored_analysis)
                    
                    # Add to existing IDs to prevent duplicates in this batch
                    if video_id:
                        existing_video_ids.append(video_id)
                        
                except Exception as e:
                    logger.error(f"Error storing ad analysis: {e}", exc_info=True)
                    # Continue with the next item instead of failing completely
                    continue
            
            logger.info(f"Stored {len(stored_analyses)} new ad analyses in database")
            return stored_analyses
            
    except httpx.RequestError as e:
        logger.error(f"HTTP request error: {e}", exc_info=True)
        
        error_message = str(e)
        if isinstance(e, httpx.ReadTimeout) or isinstance(e, httpx.TimeoutException):
            error_message = "The ad analysis request timed out. This could be due to a large number of ads or slow response from Facebook API. Please try again later."
            
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calling N8N webhook: {error_message}"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing ads: {str(e)}"
        )

@router.get("/", response_model=List[AdAnalysisResponse])
async def get_ad_analyses(current_user: User = Depends(get_current_user)):
    """
    Get all ad analyses for the current user.
    """
    try:
        db = get_database()
        ad_analyses = await db.ad_analyses.find({"user_id": str(current_user.id)}).to_list(length=100)
        return ad_analyses or []  # Return empty list if None
    except Exception as e:
        logger.error(f"Error getting ad analyses: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving ad analyses: {str(e)}"
        ) 