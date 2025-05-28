from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.responses import JSONResponse
import httpx
from typing import List, Dict, Any
import json
import logging
from pydantic import BaseModel
from bson import ObjectId

from app.core.database import get_database
from app.core.deps import get_current_user
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
async def get_collection_status(current_user: User = Depends(get_current_user)):
    """Get the current collection status for the current user."""
    try:
        scheduler_service = SchedulerService()
        metrics_service = MetricsService(scheduler=scheduler_service)
        
        # Get collection status
        status = await metrics_service.get_collection_status(str(current_user.id))
        logger.info(f"Database status for user {current_user.id}: {status}")
        
        # Also check if the job is actually running
        is_running = scheduler_service.is_job_running(str(current_user.id))
        logger.info(f"Job running status for user {current_user.id}: {is_running}")
        
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
async def toggle_collection(current_user: User = Depends(get_current_user)):
    """Toggle the collection status for the current user."""
    try:
        scheduler_service = SchedulerService()
        metrics_service = MetricsService(scheduler=scheduler_service)
        
        # Validate Facebook credentials
        if not current_user.fb_graph_api_key or not current_user.fb_ad_account_id:
            raise HTTPException(status_code=400, detail="Facebook credentials not found")
        
        # Toggle collection status
        new_status = await metrics_service.toggle_collection(str(current_user.id))
        logger.info(f"Toggled collection status for user {current_user.id} to: {new_status}")
        
        # Check if job is running
        is_running = scheduler_service.is_job_running(str(current_user.id))
        logger.info(f"Job running status after toggle for user {current_user.id}: {is_running}")
        
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
        async with httpx.AsyncClient(timeout=3600.0) as client:
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
        
        # Log information about the found analyses
        if ad_analyses:
            logger.info(f"Found {len(ad_analyses)} ad analyses for user {current_user.id}")
            for i, analysis in enumerate(ad_analyses[:3]):  # Log details for first 3 analyses
                logger.info(f"Analysis {i+1} ID: {analysis.get('_id')}")
                logger.info(f"Analysis {i+1} fields: {list(analysis.keys())}")
        else:
            logger.warning(f"No ad analyses found for user {current_user.id}")
        
        return ad_analyses or []  # Return empty list if None
    except Exception as e:
        logger.error(f"Error getting ad analyses: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving ad analyses: {str(e)}"
        )

@router.get("/get/{analysis_id}", response_model=AdAnalysisResponse)
async def get_single_ad_analysis(analysis_id: str, current_user: User = Depends(get_current_user)):
    """
    Get a specific ad analysis by ID using /get/ prefix to avoid conflicts.
    """
    try:
        db = get_database()
        logger.info(f"Attempting to fetch ad analysis with ID: {analysis_id} for user: {current_user.id}")
        
        # First try a more flexible query to see if the document exists at all
        ad_analysis = None
        
        # Try with ObjectId first if it's valid
        if ObjectId.is_valid(analysis_id):
            obj_id = ObjectId(analysis_id)
            logger.info(f"Valid ObjectId format, searching with ObjectId: {obj_id}")
            
            # First check if the document exists at all (without user_id restriction)
            existing_doc = await db.ad_analyses.find_one({"_id": obj_id})
            if existing_doc:
                logger.info(f"Found document with this ID, checking user_id match")
                # If it exists, check if it belongs to the current user
                if existing_doc.get("user_id") == str(current_user.id):
                    ad_analysis = existing_doc
                else:
                    logger.warning(f"Document found but belongs to user {existing_doc.get('user_id')}, not {current_user.id}")
            else:
                logger.warning(f"No document found with ObjectId: {obj_id}")
        
        # If not found with ObjectId, try with string ID
        if not ad_analysis:
            logger.info(f"Trying with string ID: {analysis_id}")
            existing_doc = await db.ad_analyses.find_one({"_id": analysis_id})
            if existing_doc:
                logger.info(f"Found document with string ID, checking user_id match")
                if existing_doc.get("user_id") == str(current_user.id):
                    ad_analysis = existing_doc
                else:
                    logger.warning(f"Document found but belongs to user {existing_doc.get('user_id')}, not {current_user.id}")
            else:
                logger.warning(f"No document found with string ID: {analysis_id}")
        
        # If still not found, try searching by different fields
        if not ad_analysis:
            logger.info("Trying alternative search methods")
            # Try by video_id
            video_id_match = await db.ad_analyses.find_one({
                "video_id": analysis_id,
                "user_id": str(current_user.id)
            })
            if video_id_match:
                logger.info(f"Found document by video_id match")
                ad_analysis = video_id_match
                
            # Try by ad_id (if present in schema)
            ad_id_match = await db.ad_analyses.find_one({
                "ad_id": analysis_id,
                "user_id": str(current_user.id)
            })
            if not ad_analysis and ad_id_match:
                logger.info(f"Found document by ad_id match")
                ad_analysis = ad_id_match
        
        if not ad_analysis:
            logger.error(f"Ad analysis not found with any search method for ID: {analysis_id}")
            # List a few sample IDs to help debugging
            sample_docs = await db.ad_analyses.find({"user_id": str(current_user.id)}).limit(3).to_list(3)
            if sample_docs:
                sample_ids = [str(doc.get("_id")) for doc in sample_docs]
                logger.info(f"Sample IDs for user {current_user.id}: {sample_ids}")
            
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ad analysis not found with ID: {analysis_id}"
            )
        
        logger.info(f"Successfully found ad analysis with ID: {ad_analysis.get('_id')}")
        return ad_analysis
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error getting ad analysis: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving ad analysis: {str(e)}"
        )

@router.get("/{analysis_id}", response_model=AdAnalysisResponse)
async def get_ad_analysis(analysis_id: str, current_user: User = Depends(get_current_user)):
    """
    Get a specific ad analysis by ID.
    """
    try:
        db = get_database()
        logger.info(f"Attempting to fetch ad analysis with ID: {analysis_id} for user: {current_user.id}")
        
        # First try a more flexible query to see if the document exists at all
        ad_analysis = None
        
        # Try with ObjectId first if it's valid
        if ObjectId.is_valid(analysis_id):
            obj_id = ObjectId(analysis_id)
            logger.info(f"Valid ObjectId format, searching with ObjectId: {obj_id}")
            
            # First check if the document exists at all (without user_id restriction)
            existing_doc = await db.ad_analyses.find_one({"_id": obj_id})
            if existing_doc:
                logger.info(f"Found document with this ID, checking user_id match")
                # If it exists, check if it belongs to the current user
                if existing_doc.get("user_id") == str(current_user.id):
                    ad_analysis = existing_doc
                else:
                    logger.warning(f"Document found but belongs to user {existing_doc.get('user_id')}, not {current_user.id}")
            else:
                logger.warning(f"No document found with ObjectId: {obj_id}")
        
        # If not found with ObjectId, try with string ID
        if not ad_analysis:
            logger.info(f"Trying with string ID: {analysis_id}")
            existing_doc = await db.ad_analyses.find_one({"_id": analysis_id})
            if existing_doc:
                logger.info(f"Found document with string ID, checking user_id match")
                if existing_doc.get("user_id") == str(current_user.id):
                    ad_analysis = existing_doc
                else:
                    logger.warning(f"Document found but belongs to user {existing_doc.get('user_id')}, not {current_user.id}")
            else:
                logger.warning(f"No document found with string ID: {analysis_id}")
        
        # If still not found, try searching by different fields
        if not ad_analysis:
            logger.info("Trying alternative search methods")
            # Try by video_id
            video_id_match = await db.ad_analyses.find_one({
                "video_id": analysis_id,
                "user_id": str(current_user.id)
            })
            if video_id_match:
                logger.info(f"Found document by video_id match")
                ad_analysis = video_id_match
                
            # Try by ad_id (if present in schema)
            ad_id_match = await db.ad_analyses.find_one({
                "ad_id": analysis_id,
                "user_id": str(current_user.id)
            })
            if not ad_analysis and ad_id_match:
                logger.info(f"Found document by ad_id match")
                ad_analysis = ad_id_match
        
        if not ad_analysis:
            logger.error(f"Ad analysis not found with any search method for ID: {analysis_id}")
            # List a few sample IDs to help debugging
            sample_docs = await db.ad_analyses.find({"user_id": str(current_user.id)}).limit(3).to_list(3)
            if sample_docs:
                sample_ids = [str(doc.get("_id")) for doc in sample_docs]
                logger.info(f"Sample IDs for user {current_user.id}: {sample_ids}")
            
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ad analysis not found with ID: {analysis_id}"
            )
        
        logger.info(f"Successfully found ad analysis with ID: {ad_analysis.get('_id')}")
        return ad_analysis
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error getting ad analysis: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving ad analysis: {str(e)}"
        ) 