import logging
from typing import Dict, Any, List
from app.services.facebook_service import FacebookAdService
from datetime import datetime, timedelta
from app.core.database import get_database

logger = logging.getLogger(__name__)

async def get_ads_from_facebook(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetches active ads and insights from Facebook API for analysis.

    Args:
        state (dict): Current LangGraph state containing access_token, account_id, and user_id.

    Returns:
        dict: Updated state with active ads and analyzed_video_ids.
    """
    # Check for cancellation at the start (both mechanisms)
    cancellation_token = state.get("cancellation_token")
    if (cancellation_token and cancellation_token.get("cancelled", False)) or state.get("cancelled", False):
        logger.info("Job cancelled during get_ads_from_facebook")
        return {"errors": ["Job was cancelled"]}
    
    try:
        access_token = state.get("access_token")
        account_id = state.get("account_id")
        user_id = state.get("user_id")
        progress_callback = state.get("progress_callback")
        
        if not access_token or not account_id or not user_id:
            error_msg = "Missing required parameters: access_token, account_id, or user_id"
            logger.error(error_msg)
            return {"errors": [error_msg]}

        if progress_callback:
            await progress_callback(35, "Fetching active ads from Facebook...")

        logger.info(f"Fetching active ads for account {account_id}")

        # Initialize Facebook service
        fb_service = FacebookAdService(access_token=access_token, account_id=account_id)
        
        try:
            # Prepare API URL and parameters for ads with insights
            url = f"{fb_service.base_url}/act_{account_id}/ads"
            
            # Calculate date range (yesterday to today)
            end_date = datetime.utcnow().strftime('%Y-%m-%d')
            start_date = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            # Check for cancellation before making API request (both mechanisms)
            if (cancellation_token and cancellation_token.get("cancelled", False)) or state.get("cancelled", False):
                logger.info("Job cancelled before Facebook API request")
                return {"errors": ["Job was cancelled"]}

            # Make the API request with cancellation token
            # Note: We'll filter for active ads in code since Facebook API doesn't support effective_status parameter directly
            params = {
                "fields": "id,name,campaign_id,campaign{name},adset_id,adset{name,targeting},creative{id,video_id,effective_object_story_id,object_story_spec},status,effective_status,insights.time_range({'since':'" + start_date + "','until':'" + end_date + "'}){actions,action_values,video_p25_watched_actions,video_p50_watched_actions,video_p75_watched_actions,video_p95_watched_actions,video_p100_watched_actions,impressions,reach,clicks,spend,cpc,cpm,ctr,purchase_roas}",
                "limit": 100
            }
            
            data = await fb_service._make_api_request(f"act_{account_id}/ads", params, cancellation_token=cancellation_token)
            
            if not data:
                logger.warning("No data returned from Facebook API")
                return {"ads": [], "analyzed_video_ids": []}

            ads = data.get("data", [])
            
            # Additional filtering to ensure we only have active ads
            active_ads = [ad for ad in ads if ad.get("effective_status") == "ACTIVE"]
            
            logger.info(f"Retrieved {len(ads)} ads from Facebook API, {len(active_ads)} are active")

            if progress_callback:
                await progress_callback(40, f"Found {len(active_ads)} active ads to analyze")

            # Get previously analyzed video IDs for this user
            analyzed_video_ids = await get_analyzed_video_ids(user_id)
            logger.info(f"Found {len(analyzed_video_ids)} previously analyzed videos for user {user_id}")

            return {
                "ads": active_ads,  # Return only active ads
                "analyzed_video_ids": analyzed_video_ids
            }
        finally:
            # Always cleanup Facebook service to close HTTP client and thread pools
            await fb_service.cleanup()

    except ValueError as e:
        if "cancelled" in str(e).lower():
            logger.info("Facebook API request was cancelled")
            return {"errors": ["Job was cancelled"]}
        else:
            error_msg = f"Facebook API error: {str(e)}"
            logger.error(error_msg)
            return {"errors": [error_msg]}
    except Exception as e:
        error_msg = f"Unexpected error in get_ads_from_facebook: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"errors": [error_msg]}
    finally:
        # Ensure cleanup happens even if an exception occurs
        if 'fb_service' in locals():
            try:
                await fb_service.cleanup()
            except Exception as cleanup_error:
                logger.debug(f"Error during Facebook service cleanup: {cleanup_error}")

async def get_analyzed_video_ids(user_id: str) -> List[str]:
    """
    Fetch list of video IDs that have already been analyzed for the user.
    
    Args:
        user_id: The user ID to fetch analyzed video IDs for
        
    Returns:
        List of video IDs that are already analyzed
    """
    try:
        logger.info(f"Fetching analyzed video IDs for user {user_id}")
        
        db = get_database()
        if db is None:
            logger.warning("Database not available, returning empty list")
            return []
        
        # Query the ad_analyses collection for this user
        cursor = db.ad_analyses.find(
            {"user_id": user_id},
            {"video_id": 1, "_id": 0}  # Only return video_id field
        )
        
        analyses = await cursor.to_list(length=None)
        
        # Extract video IDs, filtering out None/empty values
        video_ids = [
            analysis["video_id"] 
            for analysis in analyses 
            if analysis.get("video_id") is not None and analysis.get("video_id").strip()
        ]
        
        # Remove duplicates while preserving order
        unique_video_ids = list(dict.fromkeys(video_ids))
        
        logger.info(f"Found {len(unique_video_ids)} already analyzed video IDs for user {user_id}")
        if unique_video_ids:
            logger.debug(f"Analyzed video IDs: {unique_video_ids[:10]}{'...' if len(unique_video_ids) > 10 else ''}")
            
        return unique_video_ids
        
    except Exception as e:
        logger.error(f"Error fetching analyzed video IDs for user {user_id}: {e}", exc_info=True)
        return []  # Return empty list on error to avoid breaking the flow
