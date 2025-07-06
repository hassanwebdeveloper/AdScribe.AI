from fastapi import APIRouter, Depends, HTTPException, status, Body, Path
from fastapi.responses import JSONResponse
import httpx
from typing import List, Dict, Any, Optional
import json
import logging
from pydantic import BaseModel
from bson import ObjectId
import redis

from app.core.database import get_database
from app.core.deps import get_current_user
from app.core.config import settings
from app.models.user import User
from app.models.ad_analysis import AdAnalysis, AdAnalysisResponse, InactiveAdAnalysis
from app.models.job_status import BackgroundJobResponse, JobStartResponse, JobStatus, BackgroundJob, JobType
from app.services.scheduler_service import SchedulerService
from app.services.metrics_service import MetricsService
from app.services.user_service import UserService
# Import the AI Agent service and background job service
from app.services.ai_agent_service import AIAgentService
from app.services.background_job_service import BackgroundJobService
from app.services.inactive_ads_service import InactiveAdsService

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

class CollectionStatusRequest(BaseModel):
    is_collecting: bool

# Global singleton instance of BackgroundJobService
_background_job_service_instance = None

def get_background_job_service() -> BackgroundJobService:
    """Get a singleton BackgroundJobService instance with lazy initialization."""
    global _background_job_service_instance
    if _background_job_service_instance is None:
        logger.info("Creating new BackgroundJobService singleton instance")
        _background_job_service_instance = BackgroundJobService()
    else:
        logger.debug(f"Returning existing BackgroundJobService instance with {len(_background_job_service_instance._running_jobs)} running jobs and {len(_background_job_service_instance._cancellation_tokens)} cancellation tokens")
    return _background_job_service_instance

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

@router.get("/", response_model=List[AdAnalysisResponse])
async def get_ad_analyses(current_user: User = Depends(get_current_user)):
    """
    Get all ad analyses for the current user.
    """
    try:
        db = get_database()
        
        # Fetch ad analyses for the current user
        cursor = db.ad_analyses.find({"user_id": str(current_user.id)}).sort("created_at", -1)
        ad_analyses = await cursor.to_list(length=None)
        
        logger.info(f"Retrieved {len(ad_analyses)} ad analyses for user {current_user.id}")
        return ad_analyses
        
    except Exception as e:
        logger.error(f"Error retrieving ad analyses: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving ad analyses"
        )

@router.post("/start-analysis/", response_model=JobStartResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_ad_analysis(current_user: User = Depends(get_current_user)):
    """
    Start ad analysis as a background job and return immediately.
    Returns a job ID that can be used to track progress.
    """
    # Check if user has Facebook Graph API key and Ad Account ID
    if not current_user.fb_graph_api_key or not current_user.fb_ad_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Facebook Graph API key and Ad Account ID are required. Please configure them in settings."
        )
    
    try:
        logger.info(f"Starting background ad analysis for user {current_user.id}")
        
        # Get background job service instance
        background_job_service = get_background_job_service()
        
        # Check if there's already a running job for this user
        recent_jobs = await background_job_service.get_user_jobs(str(current_user.id), limit=1)
        if recent_jobs and recent_jobs[0].status in [JobStatus.PENDING, JobStatus.RUNNING]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An analysis job is already {recent_jobs[0].status.value}. Please wait for it to complete or cancel it first."
            )
        
        # Start the background job
        job_id = await background_job_service.start_ad_analysis_job(
            user_id=str(current_user.id),
            access_token=current_user.fb_graph_api_key,
            account_id=current_user.fb_ad_account_id
        )
        
        logger.info(f"Started background job {job_id} for user {current_user.id}")
        
        return JobStartResponse(
            job_id=job_id,
            status=JobStatus.PENDING,
            message="Ad analysis job started successfully. Use the job ID to track progress.",
            estimated_duration_seconds=300
        )
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Error starting background ad analysis: {e}", exc_info=True)
        
        # Provide more specific error messages
        error_message = str(e)
        if "timeout" in error_message.lower():
            error_message = "The request timed out. Please try again later."
        elif "facebook" in error_message.lower() or "graph api" in error_message.lower():
            error_message = "Error accessing Facebook API. Please check your access token and ad account ID."
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting ad analysis: {error_message}"
        )

@router.get("/job-status/{job_id}", response_model=BackgroundJobResponse)
async def get_job_status(job_id: str, current_user: User = Depends(get_current_user)):
    """
    Get the status of a background analysis job.
    """
    try:
        # Validate job_id
        if not job_id or job_id in ['undefined', 'null', '']:
            logger.warning(f"Invalid job ID provided: '{job_id}' for user {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid job ID provided"
            )
        
        logger.info(f"Getting job status for job_id: {job_id}, user: {current_user.id}")
        
        background_job_service = get_background_job_service()
        job_status = await background_job_service.get_job_status(job_id, str(current_user.id))
        
        if not job_status:
            logger.warning(f"Job {job_id} not found for user {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found for the current user"
            )
        
        logger.debug(f"Successfully retrieved job status for {job_id}: {job_status.status}")
        return job_status
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Error getting job status {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving job status"
        )

@router.get("/jobs/", response_model=List[BackgroundJobResponse])
async def get_user_jobs(current_user: User = Depends(get_current_user)):
    """
    Get recent background jobs for the current user.
    """
    try:
        background_job_service = get_background_job_service()
        jobs = await background_job_service.get_user_jobs(str(current_user.id), limit=20)
        return jobs
        
    except Exception as e:
        logger.error(f"Error getting user jobs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user jobs"
        )

@router.delete("/job/{job_id}")
async def cancel_job(job_id: str, current_user: User = Depends(get_current_user)):
    """
    Cancel a running background job.
    """
    try:
        background_job_service = get_background_job_service()
        success = await background_job_service.cancel_job(job_id, str(current_user.id))
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found or could not be cancelled"
            )
        
        return {"success": True, "message": "Job cancelled successfully"}
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error cancelling job"
        )

# Keep the old endpoint for backward compatibility but mark it as deprecated
@router.post("/analyze/", response_model=List[AdAnalysisResponse], status_code=status.HTTP_201_CREATED, deprecated=True)
async def analyze_ads_deprecated(current_user: User = Depends(get_current_user)):
    """
    DEPRECATED: Use /start-analysis/ instead for better performance.
    
    Analyze ads using the AI Agent and storing the results in MongoDB.
    This endpoint blocks until analysis is complete.
    """
    # Check if user has Facebook Graph API key and Ad Account ID
    if not current_user.fb_graph_api_key or not current_user.fb_ad_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Facebook Graph API key and Ad Account ID are required. Please configure them in settings."
        )
    
    try:       
        logger.info(f"Starting synchronous AI Agent analysis for user {current_user.id}")
        
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

@router.get("/debug/{analysis_id}")
async def debug_analysis_access(analysis_id: str, current_user: User = Depends(get_current_user)):
    """
    Debug endpoint to check why we can't access a specific analysis
    """
    try:
        db = get_database()
        logger.info(f"=== DEBUG ANALYSIS ACCESS ===")
        logger.info(f"Looking for analysis_id: {analysis_id}")
        logger.info(f"Current user ID: {current_user.id} (type: {type(current_user.id)})")
        logger.info(f"Current user ID as string: {str(current_user.id)}")
        
        # Check if document exists at all
        if ObjectId.is_valid(analysis_id):
            obj_id = ObjectId(analysis_id)
            doc = await db.ad_analyses.find_one({"_id": obj_id})
            if doc:
                logger.info(f"Document found with ObjectId!")
                logger.info(f"Document user_id: '{doc.get('user_id')}' (type: {type(doc.get('user_id'))})")
                logger.info(f"String comparison: '{doc.get('user_id')}' == '{str(current_user.id)}' -> {doc.get('user_id') == str(current_user.id)}")
                
                # Try different comparison methods
                comparisons = {
                    "direct": doc.get("user_id") == current_user.id,
                    "string": doc.get("user_id") == str(current_user.id),
                    "doc_as_str": str(doc.get("user_id")) == str(current_user.id),
                }
                logger.info(f"Comparison results: {comparisons}")
                
                return {
                    "found": True,
                    "document_user_id": doc.get("user_id"),
                    "document_user_id_type": str(type(doc.get("user_id"))),
                    "current_user_id": current_user.id,
                    "current_user_id_type": str(type(current_user.id)),
                    "comparisons": comparisons,
                    "has_ad_analysis": "ad_analysis" in doc,
                    "ad_analysis_keys": list(doc.get("ad_analysis", {}).keys()) if doc.get("ad_analysis") else []
                }
            else:
                logger.info(f"Document NOT found with ObjectId {obj_id}")
                return {"found": False, "searched_with": "ObjectId"}
        else:
            logger.info(f"Invalid ObjectId, searching with string")
            doc = await db.ad_analyses.find_one({"_id": analysis_id})
            if doc:
                logger.info(f"Document found with string ID!")
                return {
                    "found": True,
                    "document_user_id": doc.get("user_id"),
                    "current_user_id": current_user.id,
                    "match": doc.get("user_id") == str(current_user.id)
                }
            else:
                logger.info(f"Document NOT found with string ID {analysis_id}")
                return {"found": False, "searched_with": "string"}
                
    except Exception as e:
        logger.error(f"Debug error: {e}")
        return {"error": str(e)}

@router.get("/products", response_model=Dict[str, List[str]])
async def get_unique_products(current_user: User = Depends(get_current_user)):
    """
    Get unique products and product types from user's ad analyses
    """
    try:
        db = get_database()
        
        # Aggregate unique products and product types
        pipeline = [
            {"$match": {"user_id": str(current_user.id)}},
            {"$group": {
                "_id": None,
                "products": {"$addToSet": "$ad_analysis.product"},
                "product_types": {"$addToSet": "$ad_analysis.product_type"}
            }}
        ]
        
        result = await db.ad_analyses.aggregate(pipeline).to_list(length=1)
        
        if result and len(result) > 0:
            products = [p for p in result[0].get("products", []) if p and p.strip()]
            product_types = [pt for pt in result[0].get("product_types", []) if pt and pt.strip()]
        else:
            products = []
            product_types = []
        
        return {
            "products": sorted(list(set(products))),
            "product_types": sorted(list(set(product_types)))
        }
        
    except Exception as e:
        logger.error(f"Error fetching unique products: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching products: {str(e)}"
        )

@router.delete("/all")
async def delete_all_ad_analyses(current_user: User = Depends(get_current_user)):
    """
    Delete all ad analyses for the current user.
    """
    try:
        db = get_database()
        
        # Count how many analyses exist for the user before deletion
        count_before = await db.ad_analyses.count_documents({"user_id": str(current_user.id)})
        
        if count_before == 0:
            return {
                "success": True,
                "message": "No ad analyses found to delete",
                "deleted_count": 0
            }
        
        # Delete all analyses for the current user
        result = await db.ad_analyses.delete_many({"user_id": str(current_user.id)})
        
        logger.info(f"Deleted {result.deleted_count} ad analyses for user {current_user.id}")
        
        return {
            "success": True,
            "message": f"Successfully deleted {result.deleted_count} ad analyses",
            "deleted_count": result.deleted_count
        }
        
    except Exception as e:
        logger.error(f"Error deleting all ad analyses for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting all ad analyses"
        )

@router.delete("/{analysis_id}")
async def delete_ad_analysis(analysis_id: str, current_user: User = Depends(get_current_user)):
    """
    Delete a specific ad analysis by ID.
    """
    try:
        db = get_database()
        logger.info(f"Attempting to delete ad analysis with ID: {analysis_id} for user: {current_user.id}")
        
        # First, check if the document exists and belongs to the current user (same logic as update)
        existing_doc = None
        
        # Try with ObjectId first if it's valid
        if ObjectId.is_valid(analysis_id):
            logger.info(f"Valid ObjectId format, searching with analysis_id: {analysis_id}")
            
            # First check if the document exists at all (without user_id restriction)
            doc_check = await db.ad_analyses.find_one({"_id": analysis_id})
            if doc_check:
                logger.info(f"Document exists! Stored user_id: '{doc_check.get('user_id')}', Current user_id: '{current_user.id}'")
                # Check if it belongs to the current user
                if user_ids_match(doc_check.get("user_id"), current_user.id):
                    existing_doc = doc_check
                    logger.info("User ID match found for delete!")
                else:
                    logger.warning(f"Document found but user_id mismatch for delete. Document user_id: '{doc_check.get('user_id')}', Current user_id: '{current_user.id}'")
            else:
                logger.warning(f"No document found with analysis_id: {analysis_id}")
        
        # If not found with ObjectId, try with string ID
        if not existing_doc:
            logger.info(f"Trying with string ID: {analysis_id}")
            doc_check = await db.ad_analyses.find_one({"_id": analysis_id})
            if doc_check:
                logger.info(f"Document found with string ID. Stored user_id: '{doc_check.get('user_id')}', Current user_id: '{current_user.id}'")
                if user_ids_match(doc_check.get("user_id"), current_user.id):
                    existing_doc = doc_check
                else:
                    logger.warning(f"Document found but user_id mismatch with string search for delete")
            else:
                logger.warning(f"No document found with string ID: {analysis_id}")
        
        if not existing_doc:
            logger.error(f"Ad analysis not found with ID: {analysis_id} for user: {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ad analysis not found with ID: {analysis_id}"
            )
        
        # Create the query for delete based on what we found
        query = {"_id": analysis_id}
        
        # Delete the document (we already verified ownership above)
        result = await db.ad_analyses.delete_one(query)
        
        if result.deleted_count == 1:
            logger.info(f"Successfully deleted ad analysis with ID: {analysis_id}")
            return {"success": True, "message": "Ad analysis deleted successfully"}
        else:
            logger.error(f"Failed to delete ad analysis with ID: {analysis_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete ad analysis"
            )
            
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error deleting ad analysis: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting ad analysis: {str(e)}"
        )

# Add this helper function at the top level
def user_ids_match(doc_user_id, current_user_id):
    """
    Flexible user ID comparison that handles both ObjectId and string formats
    """
    if doc_user_id is None or current_user_id is None:
        return False
    
    # Convert both to strings for comparison
    doc_user_str = str(doc_user_id)
    current_user_str = str(current_user_id)
    
    return doc_user_str == current_user_str

class AdAnalysisUpdateRequest(BaseModel):
    product: Optional[str] = None
    product_type: Optional[str] = None

@router.patch("/{analysis_id}")
async def update_ad_analysis(
    analysis_id: str, 
    update_data: AdAnalysisUpdateRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Update specific fields of an ad analysis (currently supports product and product_type).
    """
    try:
        db = get_database()
        logger.info(f"Attempting to update ad analysis with ID: {analysis_id} for user: {current_user.id}")
        
        # First, let's check if the document exists at all (debug step)
        existing_doc = None
        
        # Try with ObjectId first if it's valid
        if ObjectId.is_valid(analysis_id):
            obj_id = ObjectId(analysis_id)
            logger.info(f"Valid ObjectId format, searching with ObjectId: {obj_id}")
            
            # First check if the document exists at all (without user_id restriction)
            doc_check = await db.ad_analyses.find_one({"_id": obj_id})
            if doc_check:
                logger.info(f"Document exists! Stored user_id: '{doc_check.get('user_id')}', Current user_id: '{current_user.id}', str(current_user.id): '{str(current_user.id)}'")
                # Check if it belongs to the current user
                if user_ids_match(doc_check.get("user_id"), current_user.id):
                    existing_doc = doc_check
                    logger.info("User ID match found!")
                else:
                    logger.warning(f"Document found but user_id mismatch. Document user_id: '{doc_check.get('user_id')}' (type: {type(doc_check.get('user_id'))}), Current user_id: '{current_user.id}' (type: {type(current_user.id)})")
            else:
                logger.warning(f"No document found with ObjectId: {obj_id}")
        
        # If not found with ObjectId, try with string ID
        if not existing_doc:
            logger.info(f"Trying with string ID: {analysis_id}")
            doc_check = await db.ad_analyses.find_one({"_id": analysis_id})
            if doc_check:
                logger.info(f"Document found with string ID. Stored user_id: '{doc_check.get('user_id')}', Current user_id: '{current_user.id}'")
                if user_ids_match(doc_check.get("user_id"), current_user.id):
                    existing_doc = doc_check
                else:
                    logger.warning(f"Document found but user_id mismatch with string search")
            else:
                logger.warning(f"No document found with string ID: {analysis_id}")
        
        if not existing_doc:
            # Let's also list some sample documents for this user to help debug
            sample_docs = await db.ad_analyses.find({"user_id": str(current_user.id)}).limit(3).to_list(3)
            if sample_docs:
                sample_info = [{"_id": str(doc.get("_id")), "user_id": doc.get("user_id")} for doc in sample_docs]
                logger.info(f"Sample documents for user {current_user.id}: {sample_info}")
            
            logger.error(f"Ad analysis not found with ID: {analysis_id} for user: {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ad analysis not found with ID: {analysis_id}"
            )
        
        # Prepare update data - only update fields that are provided
        update_fields = {}
        if update_data.product is not None:
            update_fields["ad_analysis.product"] = update_data.product.strip() if update_data.product else ""
        if update_data.product_type is not None:
            update_fields["ad_analysis.product_type"] = update_data.product_type.strip() if update_data.product_type else ""
        
        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid fields provided for update"
            )
        
        logger.info(f"Prepared update_fields: {update_fields}")
        
        # Check if ad_analysis object exists, if not we might need to create it
        if existing_doc and not existing_doc.get("ad_analysis"):
            logger.info("ad_analysis object doesn't exist, will create it")
            # If ad_analysis doesn't exist, we need to create the whole object
            new_ad_analysis = {}
            if update_data.product is not None:
                new_ad_analysis["product"] = update_data.product.strip() if update_data.product else ""
            if update_data.product_type is not None:
                new_ad_analysis["product_type"] = update_data.product_type.strip() if update_data.product_type else ""
            
            # Use $set to create the entire ad_analysis object
            update_fields = {"ad_analysis": new_ad_analysis}
            logger.info(f"Creating new ad_analysis object: {update_fields}")
        
        # Create the query for update based on what we found - since we already verified ownership, 
        # we can just use the _id without user_id restriction to avoid the same comparison issue
        
        query = {"_id": analysis_id}
        
        logger.info(f"Using query for update: {query}")
        logger.info(f"Update fields: {update_fields}")
        
        # Let's also log the current field values before update for comparison
        current_doc = await db.ad_analyses.find_one(query)
        if current_doc:
            current_ad_analysis = current_doc.get("ad_analysis", {})
            logger.info(f"Current ad_analysis structure: {current_ad_analysis}")
            logger.info(f"Current product: '{current_ad_analysis.get('product')}'")
            logger.info(f"Current product_type: '{current_ad_analysis.get('product_type')}'")
        else:
            logger.warning(f"Could not find document with query {query} for pre-update check")
        
        # Update the document
        result = await db.ad_analyses.update_one(
            query,
            {"$set": update_fields}
        )
        
        logger.info(f"Update result - matched_count: {result.matched_count}, modified_count: {result.modified_count}")
        
        # If the update didn't modify anything, let's try alternative approaches
        if result.matched_count > 0 and result.modified_count == 0:
            logger.warning("Document was matched but not modified. Trying alternative update strategies...")
            
            # Strategy 1: Try using $unset and then $set to force the update
            if update_data.product is not None:
                logger.info("Trying alternative strategy for product field...")
                unset_result = await db.ad_analyses.update_one(
                    query,
                    {"$unset": {"ad_analysis.product": ""}}
                )
                set_result = await db.ad_analyses.update_one(
                    query,
                    {"$set": {"ad_analysis.product": update_data.product.strip()}}
                )
                logger.info(f"Unset result: {unset_result.modified_count}, Set result: {set_result.modified_count}")
            
            if update_data.product_type is not None:
                logger.info("Trying alternative strategy for product_type field...")
                unset_result = await db.ad_analyses.update_one(
                    query,
                    {"$unset": {"ad_analysis.product_type": ""}}
                )
                set_result = await db.ad_analyses.update_one(
                    query,
                    {"$set": {"ad_analysis.product_type": update_data.product_type.strip()}}
                )
                logger.info(f"Unset result: {unset_result.modified_count}, Set result: {set_result.modified_count}")
            
            # Check the result again
            result = await db.ad_analyses.find_one(query)
            if result:
                logger.info("Alternative strategy completed, checking final result...")
        
        # Let's also check the document after update to see what actually happened
        post_update_doc = await db.ad_analyses.find_one(query)
        if post_update_doc:
            post_ad_analysis = post_update_doc.get("ad_analysis", {})
            logger.info(f"After update ad_analysis structure: {post_ad_analysis}")
            logger.info(f"After update product: '{post_ad_analysis.get('product')}'")
            logger.info(f"After update product_type: '{post_ad_analysis.get('product_type')}'")
        
        if result.modified_count == 1:
            logger.info(f"Successfully updated ad analysis with ID: {analysis_id}")
            
            # Fetch and return the updated document
            updated_doc = await db.ad_analyses.find_one(query)
            return {
                "success": True, 
                "message": "Ad analysis updated successfully",
                "updated_analysis": updated_doc
            }
        else:
            logger.warning(f"No changes made to ad analysis with ID: {analysis_id}")
            return {
                "success": True,
                "message": "No changes were necessary",
                "updated_analysis": existing_doc
            }
            
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error updating ad analysis: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating ad analysis: {str(e)}"
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

@router.post("/debug-database")
async def debug_database_operations(current_user: dict = Depends(get_current_user)):
    """
    Debug endpoint to test database operations.
    """
    try:
        user_id = str(current_user["_id"])
        logger.info(f"Testing database operations for user {user_id}")
        
        # Test database connection
        background_job_service = get_background_job_service()
        is_connected = await background_job_service.test_database_connection()
        
        if not is_connected:
            return {
                "success": False,
                "error": "Database connection test failed",
                "details": "Unable to connect to MongoDB"
            }
        
        # Test creating a simple job record (but don't start the actual job)
        from app.models.job_status import BackgroundJob, JobStatus, JobType
        from datetime import datetime
        
        test_job = BackgroundJob(
            user_id=user_id,
            job_type=JobType.AD_ANALYSIS,
            status=JobStatus.PENDING,
            message="Test job for debugging",
            parameters={"test": True},
            estimated_duration_seconds=60
        )
        
        # Try to insert and then immediately delete the test job
        db = background_job_service.db
        
        async def test_insert():
            return await db.background_jobs.insert_one(test_job.model_dump(by_alias=True))
        
        result = await background_job_service._safe_db_operation("test_insert", test_insert)
        test_job_id = result.inserted_id
        
        # Test update operation
        async def test_update():
            return await db.background_jobs.update_one(
                {"_id": test_job_id},
                {"$set": {"message": "Test job updated", "progress": 50}}
            )
        
        update_result = await background_job_service._safe_db_operation("test_update", test_update)
        
        # Test find operation
        async def test_find():
            return await db.background_jobs.find_one({"_id": test_job_id})
        
        found_job = await background_job_service._safe_db_operation("test_find", test_find)
        
        # Clean up test job
        async def test_delete():
            return await db.background_jobs.delete_one({"_id": test_job_id})
        
        delete_result = await background_job_service._safe_db_operation("test_delete", test_delete)
        
        return {
            "success": True,
            "database_connected": True,
            "operations": {
                "insert": {"success": True, "inserted_id": str(test_job_id)},
                "update": {"success": True, "modified_count": update_result.modified_count},
                "find": {"success": True, "found": found_job is not None, "message": found_job.get("message") if found_job else None},
                "delete": {"success": True, "deleted_count": delete_result.deleted_count}
            }
        }
        
    except Exception as e:
        logger.error(f"Database debug operations failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "details": "Database operations test failed"
        }

@router.get("/inactive", response_model=List[AdAnalysisResponse])
async def get_inactive_ads(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user)
):
    """
    Get inactive ads for the current user.
    """
    try:
        inactive_ads_service = InactiveAdsService()
        inactive_ads = await inactive_ads_service.get_inactive_ads(current_user.id, skip, limit)
        return inactive_ads
    except Exception as e:
        logger.error(f"Error fetching inactive ads: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching inactive ads: {str(e)}"
        )

@router.get("/inactive/count", response_model=Dict[str, int])
async def count_inactive_ads(
    current_user: User = Depends(get_current_user)
):
    """
    Count the number of inactive ads for the current user.
    """
    try:
        inactive_ads_service = InactiveAdsService()
        count = await inactive_ads_service.count_inactive_ads(current_user.id)
        return {"count": count}
    except Exception as e:
        logger.error(f"Error counting inactive ads: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error counting inactive ads: {str(e)}"
        )

@router.get("/inactive/{ad_id}", response_model=AdAnalysisResponse)
async def get_inactive_ad_by_id(
    ad_id: str = Path(..., title="The ID of the inactive ad to get"),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific inactive ad by ID.
    """
    try:
        inactive_ads_service = InactiveAdsService()
        inactive_ad = await inactive_ads_service.get_inactive_ad_by_id(current_user.id, ad_id)
        
        if not inactive_ad:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inactive ad with ID {ad_id} not found"
            )
        
        return inactive_ad
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching inactive ad by ID: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching inactive ad by ID: {str(e)}"
        )

@router.post("/inactive/{ad_id}/restore", response_model=Dict[str, bool])
async def restore_inactive_ad(
    ad_id: str = Path(..., title="The ID of the inactive ad to restore"),
    current_user: User = Depends(get_current_user)
):
    """
    Restore an inactive ad to the active ads collection.
    """
    try:
        inactive_ads_service = InactiveAdsService()
        success = await inactive_ads_service.restore_inactive_ad(current_user.id, ad_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inactive ad with ID {ad_id} not found or could not be restored"
            )
        
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restoring inactive ad: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error restoring inactive ad: {str(e)}"
        )

@router.delete("/inactive/{ad_id}", response_model=Dict[str, bool])
async def delete_inactive_ad(
    ad_id: str = Path(..., title="The ID of the inactive ad to delete"),
    current_user: User = Depends(get_current_user)
):
    """
    Permanently delete an inactive ad.
    """
    try:
        inactive_ads_service = InactiveAdsService()
        success = await inactive_ads_service.delete_inactive_ad(current_user.id, ad_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inactive ad with ID {ad_id} not found or could not be deleted"
            )
        
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting inactive ad: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting inactive ad: {str(e)}"
        ) 