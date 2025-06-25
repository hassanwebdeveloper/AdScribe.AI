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
        # Check for cancellation at the start (both mechanisms)
        cancellation_token = state.get("cancellation_token")
        if (cancellation_token and cancellation_token.get("cancelled", False)) or state.get("cancelled", False):
            logger.info("Job cancelled during get_video_urls_from_ads")
            return {"errors": ["Job was cancelled"]}
        
        ads = state.get("ads", [])
        access_token = state.get("access_token")
        account_id = state.get("account_id")
        progress_callback = state.get("progress_callback")
        
        if not access_token:
            error_msg = "Missing access_token in state"
            logger.error(error_msg)
            return {"errors": [error_msg], "video_urls": []}
            
        if not ads:
            logger.warning("[⚠️] No ads found in state. Cannot extract video URLs.")
            return {"video_urls": []}

        if progress_callback:
            await progress_callback(41, f"Extracting video URLs from {len(ads)} ads...")

        # Initialize Facebook service to use the robust _make_request method
        fb_service = FacebookAdService(access_token=access_token, account_id=account_id or "dummy")
        
        try:
            video_urls = []
            ads_with_videos = [ad for ad in ads if ad.get("creative", {}).get("object_story_spec", {}).get("video_data", {}).get("video_id")]

            if progress_callback:
                await progress_callback(43, f"Found {len(ads_with_videos)} ads with videos...")

            for i, ad in enumerate(ads):
                # Check for cancellation before each video URL extraction (both mechanisms)
                if (cancellation_token and cancellation_token.get("cancelled", False)) or state.get("cancelled", False):
                    logger.info(f"Job cancelled during video URL extraction (ad {i+1}/{len(ads)})")
                    return {"errors": ["Job was cancelled"]}
                
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

                # Report progress for video URL extraction
                if progress_callback and ads_with_videos:
                    video_index = len([v for v in video_urls if 'video_id' in v]) + 1
                    url_progress = 43 + video_index / len(ads_with_videos) * 7  # 43-50% range
                    await progress_callback(int(url_progress), f"Getting video URL {video_index}/{len(ads_with_videos)}...")

                video_url = f"{fb_service.base_url}/{video_id}"
                params = {
                    "access_token": access_token,
                    "fields": "source,permalink_url"
                }

                try:
                    # Check for cancellation before making API call (both mechanisms)
                    if (cancellation_token and cancellation_token.get("cancelled", False)) or state.get("cancelled", False):
                        logger.info(f"Job cancelled before video URL API call for video {video_id}")
                        return {"errors": ["Job was cancelled"]}
                    
                    # Use the robust _make_request method with cancellation token
                    data = await fb_service._make_request(video_url, params, cancellation_token=cancellation_token)

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
            
            if progress_callback:
                successful_urls = len([v for v in video_urls if 'error' not in v])
                await progress_callback(50, f"Extracted {successful_urls} video URLs successfully")
            
            return {"video_urls": video_urls}
        finally:
            # Always cleanup Facebook service to close HTTP client and thread pools
            await fb_service.cleanup()

    except Exception as e:
        error_msg = f"Unexpected error in get_video_urls_from_ads: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"errors": [error_msg], "video_urls": []}
    finally:
        # Ensure cleanup happens even if an exception occurs
        if 'fb_service' in locals():
            try:
                await fb_service.cleanup()
            except Exception as cleanup_error:
                logger.debug(f"Error during Facebook service cleanup: {cleanup_error}")
