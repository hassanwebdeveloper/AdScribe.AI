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
# Import the AI Agent service
from app.services.ai_agent_service import AIAgentService

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
    Analyze ads using the AI Agent and storing the results in MongoDB.
    Requires the user to have a Facebook Graph API key and Ad Account ID.
    """
    # Check if user has Facebook Graph API key and Ad Account ID
    if not current_user.fb_graph_api_key or not current_user.fb_ad_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Facebook Graph API key and Ad Account ID are required. Please configure them in settings."
        )
    
    try:       
        
        logger.info(f"Starting AI Agent analysis for user {current_user.id}")
        
        # Initialize the AI Agent service
        ai_agent_service = AIAgentService()
        
        # Run the AI Agent analysis
        stored_analyses = await ai_agent_service.analyze_ads_with_ai_agent(
            user_id=str(current_user.id),
            access_token=current_user.fb_graph_api_key,
            account_id=current_user.fb_ad_account_id
        )
        
        logger.info(f"AI Agent analysis completed. Stored {len(stored_analyses)} new ad analyses")
        return stored_analyses
        
    except Exception as e:
        logger.error(f"Error in AI Agent analysis: {e}", exc_info=True)
        
        # Provide more specific error messages
        error_message = str(e)
        if "timeout" in error_message.lower():
            error_message = "The ad analysis request timed out. This could be due to a large number of ads or slow processing. Please try again later."
        elif "facebook" in error_message.lower() or "graph api" in error_message.lower():
            error_message = "Error accessing Facebook API. Please check your access token and ad account ID."
        elif "openai" in error_message.lower():
            error_message = "Error with AI analysis service. Please try again later."
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing ads: {error_message}"
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