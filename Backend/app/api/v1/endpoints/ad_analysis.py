from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.responses import JSONResponse
import httpx
from typing import List, Dict, Any
import json
import logging

from app.core.database import get_database
from app.core.deps import get_current_user
from app.models.user import User
from app.models.ad_analysis import AdAnalysis, AdAnalysisResponse

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

# N8N Webhook URL
N8N_WEBHOOK_URL = "https://n8n.srv764032.hstgr.cloud/webhook-test/5a4483f4-7fca-4476-be74-84970f60ebaf"

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
    
    # Prepare payload for N8N
    payload = {
        "fb_graph_api_key": current_user.fb_graph_api_key,
        "fb_ad_account_id": current_user.fb_ad_account_id
    }
    
    try:
        # Call N8N webhook with increased timeout (15 minutes)
        async with httpx.AsyncClient(timeout=900.0) as client:
            response = await client.post(N8N_WEBHOOK_URL, json=payload)
            
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
                
                ad_analyses = response_data
            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON response: {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Invalid JSON response from N8N webhook"
                )
            
            # Get database connection
            db = get_database()
            
            # Store ad analyses in MongoDB
            stored_analyses = []
            for ad_analysis_data in ad_analyses:
                try:
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
                except Exception as e:
                    logger.error(f"Error storing ad analysis: {e}", exc_info=True)
                    # Continue with the next item instead of failing completely
                    continue
            
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