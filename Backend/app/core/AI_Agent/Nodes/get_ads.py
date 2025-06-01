import logging
from typing import Dict, Any
from app.services.facebook_service import FacebookAdService

logger = logging.getLogger(__name__)

async def get_facebook_ads(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch Facebook Ads data from Graph API and store it in the graph state.

    Args:
        state (dict): The current state of the graph containing access_token and account_id.

    Returns:
        dict: Updated graph state including raw ad data.
    """
    try:
        access_token = state.get("access_token")
        account_id = state.get("account_id")
        
        if not access_token or not account_id:
            error_msg = "Missing access_token or account_id in state"
            logger.error(error_msg)
            return {"errors": [error_msg]}
        
        # Initialize Facebook service to use the robust _make_request method
        fb_service = FacebookAdService(access_token=access_token, account_id=account_id)
        
        # Remove 'act_' prefix if present (FacebookAdService handles this)
        account_id = account_id.replace('act_', '')
        
        url = f"{fb_service.base_url}/act_{account_id}/ads"
        params = {
            "access_token": access_token,
            "fields": ",".join([
                "id",
                "name",
                "ad_active_time",
                "adlabels",
                "campaign{id,name}",
                "adset{id,name,targeting}",
                "creative{id,video_id,effective_object_story_id,object_story_spec}",
                "status"
            ]),
            "limit": 100  # Add limit to prevent too many results
        }

        # Use the robust _make_request method instead of direct httpx
        data = await fb_service._make_request(url, params)
        ads_data = data.get("data", [])

        logger.info(f"[📥] Retrieved {len(ads_data)} ads from Meta for account {account_id}")

        # Return only the fields to be updated
        return {"ads": ads_data}

    except Exception as e:
        error_msg = f"Unexpected error occurred: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"errors": [error_msg]}
