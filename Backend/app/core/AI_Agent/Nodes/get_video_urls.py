import logging
from typing import Dict, Any
from app.services.facebook_service import FacebookAdService

logger = logging.getLogger(__name__)

async def get_video_urls_from_ads(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts video URLs for each ad with a video creative.

    Args:
        state (dict): Current LangGraph state, should include "ads" and "access_token".

    Returns:
        dict: Updated state with video URL info.
    """
    try:
        ads = state.get("ads", [])
        access_token = state.get("access_token")
        account_id = state.get("account_id")
        
        if not access_token:
            error_msg = "Missing access_token in state"
            logger.error(error_msg)
            return {"errors": [error_msg], "video_urls": []}
            
        if not ads:
            logger.warning("[⚠️] No ads found in state. Cannot extract video URLs.")
            return {"video_urls": []}

        # Initialize Facebook service to use the robust _make_request method
        fb_service = FacebookAdService(access_token=access_token, account_id=account_id or "dummy")

        video_urls = []

        for ad in ads:
            creative = ad.get("creative", {})
            video_id = (
                creative
                .get("object_story_spec", {})
                .get("video_data", {})
                .get("video_id")
            )

            if not video_id:
                logger.debug(f"[SKIP] No video ID found for ad_id {ad.get('id')}")
                continue

            video_url = f"{fb_service.base_url}/{video_id}"
            params = {
                "access_token": access_token,
                "fields": "source,permalink_url"
            }

            try:
                # Use the robust _make_request method instead of direct httpx
                data = await fb_service._make_request(video_url, params)

                video_info = {
                    "ad_id": ad.get("id"),
                    "video_id": video_id,
                    "source": data.get("source"),
                    "permalink_url": data.get("permalink_url")
                }

                video_urls.append(video_info)
                logger.debug(f"[✅] Found video URL for ad {ad.get('id')}, video {video_id}")

            except Exception as e:
                error_msg = f"Error getting video data for video_id {video_id}: {str(e)}"
                logger.warning(error_msg)
                video_urls.append({
                    "ad_id": ad.get("id"),
                    "video_id": video_id,
                    "error": error_msg
                })

        logger.info(f"[🔗] Found video URLs for {len([v for v in video_urls if 'error' not in v])} out of {len(video_urls)} ads with videos.")
        return {"video_urls": video_urls}

    except Exception as e:
        error_msg = f"Unexpected error in get_video_urls_from_ads: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"errors": [error_msg], "video_urls": []}
