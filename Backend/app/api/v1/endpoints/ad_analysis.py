from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.responses import JSONResponse
import httpx
from typing import List, Dict, Any
import json
import logging
from pydantic import BaseModel
from bson import ObjectId

from app.core.database import get_database
from app.core.deps import get_current_user, get_current_user_with_credentials, UserWithCredentials
from app.core.config import settings
from app.models.user import User
from app.models.ad_analysis import AdAnalysis, AdAnalysisResponse
from app.services.scheduler_service import SchedulerService
from app.services.metrics_service import MetricsService
from app.services.user_service import UserService

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

class CollectionStatusRequest(BaseModel):
    is_collecting: bool

@router.get("/collection-status")
async def get_collection_status(user_with_creds: UserWithCredentials = Depends(get_current_user_with_credentials)):
    """Get the current collection status for the current user."""
    try:
        scheduler_service = SchedulerService()
        metrics_service = MetricsService(scheduler=scheduler_service)
        
        # Get collection status, passing user data to avoid duplicate database query
        status = await metrics_service.get_collection_status(
            str(user_with_creds.user.id), 
            user_data=user_with_creds.raw_data
        )
        logger.info(f"Database status for user {user_with_creds.user.id}: {status}")
        
        # Also check if the job is actually running
        is_running = scheduler_service.is_job_running(str(user_with_creds.user.id))
        logger.info(f"Job running status for user {user_with_creds.user.id}: {is_running}")
        
        response_data = {
            "status": status,
            "is_running": is_running
        }
        logger.info(f"Returning collection status: {response_data}")
        
        return response_data
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error getting collection status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting collection status: {str(e)}")

@router.post("/toggle-collection")
async def toggle_collection(user_with_creds: UserWithCredentials = Depends(get_current_user_with_credentials)):
    """Toggle the collection status for the current user."""
    try:
        scheduler_service = SchedulerService()
        metrics_service = MetricsService(scheduler=scheduler_service)
        
        # Validate Facebook credentials
        if not user_with_creds.has_facebook_credentials():
            raise HTTPException(status_code=400, detail="Facebook credentials not found")
        
        # Toggle collection status, passing user data to avoid duplicate database query
        new_status = await metrics_service.toggle_collection(
            str(user_with_creds.user.id),
            user_data=user_with_creds.raw_data
        )
        logger.info(f"Toggled collection status for user {user_with_creds.user.id} to: {new_status}")
        
        # Check if job is running
        is_running = scheduler_service.is_job_running(str(user_with_creds.user.id))
        logger.info(f"Job running status after toggle for user {user_with_creds.user.id}: {is_running}")
        
        return {
            "status": new_status,
            "is_running": is_running
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error toggling collection: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error toggling collection: {str(e)}")

@router.post("/analyze/", response_model=List[AdAnalysisResponse], status_code=status.HTTP_201_CREATED)
async def analyze_ads(user_with_creds: UserWithCredentials = Depends(get_current_user_with_credentials)):
    """
    Analyze ads by calling the N8N webhook and storing the results in MongoDB.
    Requires the user to have a Facebook Graph API key and Ad Account ID.
    """
    # Check if user has Facebook credentials
    if not user_with_creds.has_facebook_credentials():
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
            {"user_id": str(user_with_creds.user.id)}, 
            {"video_id": 1}
        ).to_list(length=1000)
        
        # Extract video IDs from results
        existing_video_ids = [
            analysis.get("video_id") for analysis in existing_analyses 
            if analysis.get("video_id") is not None
        ]
        logger.info(f"Found {len(existing_video_ids)} existing video IDs for user {user_with_creds.user.id}")
    except Exception as e:
        logger.error(f"Error retrieving existing video IDs: {e}", exc_info=True)
        # Continue anyway - we'll just analyze all ads
    
    # Prepare payload for N8N with existing video IDs
    payload = {
        "fb_graph_api_key": user_with_creds.facebook_credentials["access_token"],
        "fb_ad_account_id": user_with_creds.facebook_credentials["account_id"],
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
                        user_id=str(user_with_creds.user.id),
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
                    continue
            
            logger.info(f"Successfully stored {len(stored_analyses)} ad analyses")
            
            # Convert stored analyses to response models
            response_analyses = []
            for analysis in stored_analyses:
                try:
                    # Convert ObjectId to string for the response
                    if "_id" in analysis and isinstance(analysis["_id"], ObjectId):
                        analysis["_id"] = str(analysis["_id"])
                    
                    response_analyses.append(AdAnalysisResponse(**analysis))
                except Exception as e:
                    logger.error(f"Error converting analysis to response model: {e}")
                    continue
            
            return response_analyses
            
    except httpx.TimeoutException:
        logger.error("Timeout calling N8N webhook")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Analysis request timed out. Please try again later."
        )
    except httpx.RequestError as e:
        logger.error(f"Request error calling N8N webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to connect to analysis service"
        )
    except Exception as e:
        logger.error(f"Unexpected error in analyze_ads: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during analysis"
        )

@router.get("/", response_model=List[AdAnalysisResponse])
async def get_ad_analyses(current_user: User = Depends(get_current_user)):
    """
    Get all ad analyses for the current user.
    """
    db = get_database()
    
    try:
        logger.info(f"Getting all ad analyses for user {current_user.id}")
        
        # First, check total count of analyses for this user
        total_count = await db.ad_analyses.count_documents({"user_id": str(current_user.id)})
        logger.info(f"Found {total_count} ad analyses for user {current_user.id}")
        
        # Find all ad analyses for the user
        analyses = await db.ad_analyses.find({"user_id": str(current_user.id)}).sort("created_at", -1).to_list(length=1000)
        
        logger.info(f"Retrieved {len(analyses)} ad analyses from database")
        
        # Convert to response models
        response_analyses = []
        for i, analysis in enumerate(analyses):
            try:
                # Log the analysis ID for debugging
                analysis_id = analysis.get("_id")
                logger.debug(f"Processing analysis {i+1}/{len(analyses)} with ID: {analysis_id}")
                
                # Convert ObjectId to string for the response
                if "_id" in analysis and isinstance(analysis["_id"], ObjectId):
                    analysis["_id"] = str(analysis["_id"])
                
                response_analyses.append(AdAnalysisResponse(**analysis))
            except Exception as e:
                logger.error(f"Error converting analysis {i+1} to response model: {e}")
                logger.error(f"Analysis data: {analysis}")
                continue
        
        logger.info(f"Successfully converted {len(response_analyses)} analyses to response models")
        return response_analyses
        
    except Exception as e:
        logger.error(f"Error getting ad analyses: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve ad analyses"
        )

@router.get("/get/{analysis_id}", response_model=AdAnalysisResponse)
async def get_single_ad_analysis(analysis_id: str, current_user: User = Depends(get_current_user)):
    """
    Get a single ad analysis by ID.
    """
    db = get_database()
    
    try:
        logger.info(f"Getting ad analysis {analysis_id} for user {current_user.id}")
        
        # Convert string ID to ObjectId
        try:
            obj_id = ObjectId(analysis_id)
            logger.debug(f"Converted analysis_id {analysis_id} to ObjectId: {obj_id}")
        except Exception as e:
            logger.error(f"Invalid ObjectId format for analysis_id {analysis_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid analysis ID format: {analysis_id}"
            )
        
        # First, check if any analysis exists with this ID (regardless of user)
        analysis_exists = await db.ad_analyses.find_one({"_id": obj_id})
        if not analysis_exists:
            logger.warning(f"No ad analysis found with ID {analysis_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ad analysis with ID {analysis_id} not found"
            )
        
        # Check if the analysis belongs to the current user
        if analysis_exists.get("user_id") != str(current_user.id):
            logger.warning(f"Ad analysis {analysis_id} belongs to user {analysis_exists.get('user_id')}, not {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ad analysis not found"  # Don't reveal that it exists but belongs to another user
            )
        
        analysis = analysis_exists
        logger.info(f"Found ad analysis {analysis_id} for user {current_user.id}")
        
        # Convert ObjectId to string for the response
        if "_id" in analysis and isinstance(analysis["_id"], ObjectId):
            analysis["_id"] = str(analysis["_id"])
        
        return AdAnalysisResponse(**analysis)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting ad analysis {analysis_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve ad analysis"
        )

@router.get("/{analysis_id}", response_model=AdAnalysisResponse)
async def get_ad_analysis(analysis_id: str, current_user: User = Depends(get_current_user)):
    """
    Get a specific ad analysis by ID.
    """
    return await get_single_ad_analysis(analysis_id, current_user)

@router.get("/debug/list-all")
async def debug_list_all_analyses(current_user: User = Depends(get_current_user)):
    """
    Debug endpoint to list all analyses with their IDs for troubleshooting.
    """
    db = get_database()
    
    try:
        # Get all analyses for this user with minimal data
        analyses = await db.ad_analyses.find(
            {"user_id": str(current_user.id)}, 
            {"_id": 1, "created_at": 1, "ad_title": 1, "video_id": 1}
        ).sort("created_at", -1).to_list(length=100)
        
        debug_info = []
        for analysis in analyses:
            debug_info.append({
                "id": str(analysis["_id"]),
                "created_at": analysis.get("created_at"),
                "ad_title": analysis.get("ad_title"),
                "video_id": analysis.get("video_id")
            })
        
        return {
            "user_id": str(current_user.id),
            "total_analyses": len(debug_info),
            "analyses": debug_info
        }
        
    except Exception as e:
        logger.error(f"Error in debug endpoint: {e}", exc_info=True)
        return {"error": str(e)} 