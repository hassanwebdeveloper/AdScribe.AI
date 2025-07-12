import logging
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from app.core.database import get_database
from app.services.facebook_service import FacebookAdService
from app.services.user_service import UserService
import asyncio

logger = logging.getLogger(__name__)

class VideoUrlService:
    """Service to handle Facebook video URL expiration and refresh."""
    
    def __init__(self):
        self.user_service = UserService()
        
    async def check_and_refresh_video_url(self, video_url: str, video_id: str, user_id: str) -> Optional[str]:
        """
        Check if a video URL is expired and refresh it if needed.
        
        Args:
            video_url: Current video URL to check
            video_id: Facebook video ID
            user_id: User ID for getting Facebook credentials
            
        Returns:
            Valid video URL or None if refresh failed
        """
        try:
            # First check if the current URL is still valid
            if await self._is_url_valid(video_url):
                logger.debug(f"Video URL is still valid for video_id {video_id}")
                return video_url
            
            logger.info(f"Video URL expired for video_id {video_id}, refreshing...")
            
            # Get fresh URL from Facebook API
            fresh_url = await self._get_fresh_video_url(video_id, user_id)
            
            if fresh_url:
                # Update the database with the new URL
                await self._update_video_url_in_database(video_id, fresh_url, user_id)
                logger.info(f"Successfully refreshed video URL for video_id {video_id}")
                return fresh_url
            else:
                logger.warning(f"Failed to get fresh video URL for video_id {video_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error checking/refreshing video URL for video_id {video_id}: {str(e)}")
            return video_url  # Return original URL as fallback
    
    async def _is_url_valid(self, url: str) -> bool:
        """
        Check if a video URL is still valid by making a HEAD request.
        
        Args:
            url: Video URL to check
            
        Returns:
            True if URL is valid, False otherwise
        """
        if not url:
            return False
            
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.head(url, follow_redirects=True)
                # Consider 200-299 status codes as valid
                is_valid = 200 <= response.status_code < 300
                logger.debug(f"URL validation for {url[:50]}... returned status {response.status_code}")
                return is_valid
        except Exception as e:
            logger.debug(f"URL validation failed for {url[:50]}...: {str(e)}")
            return False
    
    async def _get_fresh_video_url(self, video_id: str, user_id: str) -> Optional[str]:
        """
        Get a fresh video URL from Facebook API.
        
        Args:
            video_id: Facebook video ID
            user_id: User ID for getting Facebook credentials
            
        Returns:
            Fresh video URL or None if failed
        """
        try:
            # Get user's Facebook credentials
            credentials = await self.user_service.get_facebook_credentials(user_id)
            
            if not credentials or not credentials.get("access_token"):
                logger.warning(f"No Facebook credentials found for user {user_id}")
                return None
            
            access_token = credentials["access_token"]
            account_id = credentials.get("account_id", "")
            
            # Initialize Facebook service
            fb_service = FacebookAdService(access_token=access_token, account_id=account_id)
            
            # Get fresh video URL
            fresh_url = await fb_service.get_video_url(video_id)
            
            if fresh_url:
                logger.info(f"Successfully fetched fresh URL for video_id {video_id}")
                return fresh_url
            else:
                logger.warning(f"Facebook API returned no URL for video_id {video_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching fresh video URL for video_id {video_id}: {str(e)}")
            return None
    
    async def _update_video_url_in_database(self, video_id: str, new_url: str, user_id: str):
        """
        Update the video URL in the ad_analyses collection.
        
        Args:
            video_id: Facebook video ID
            new_url: New video URL
            user_id: User ID
        """
        try:
            db = get_database()
            
            # Update all documents with this video_id for this user
            result = await db.ad_analyses.update_many(
                {
                    "user_id": user_id,
                    "video_id": video_id
                },
                {
                    "$set": {
                        "video_url": new_url,
                        "video_url_updated_at": datetime.utcnow()
                    }
                }
            )
            
            logger.info(f"Updated {result.modified_count} documents with new video URL for video_id {video_id}")
            
        except Exception as e:
            logger.error(f"Error updating video URL in database for video_id {video_id}: {str(e)}")
    
    async def refresh_expired_urls_for_user(self, user_id: str) -> Dict[str, Any]:
        """
        Batch refresh expired video URLs for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with refresh results
        """
        try:
            db = get_database()
            
            # Get all ad analyses for this user that have video URLs
            analyses = await db.ad_analyses.find({
                "user_id": user_id,
                "video_url": {"$exists": True, "$ne": ""}
            }).to_list(length=None)
            
            if not analyses:
                return {"refreshed": 0, "failed": 0, "total": 0}
            
            logger.info(f"Found {len(analyses)} ad analyses with video URLs for user {user_id}")
            
            refreshed_count = 0
            failed_count = 0
            
            # Process in batches to avoid overwhelming the API
            batch_size = 5
            for i in range(0, len(analyses), batch_size):
                batch = analyses[i:i + batch_size]
                
                # Process batch concurrently
                tasks = []
                for analysis in batch:
                    video_id = analysis.get("video_id")
                    video_url = analysis.get("video_url")
                    
                    if video_id and video_url:
                        task = self.check_and_refresh_video_url(video_url, video_id, user_id)
                        tasks.append(task)
                
                # Wait for batch to complete
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Count results
                for result in results:
                    if isinstance(result, Exception):
                        failed_count += 1
                    elif result:
                        refreshed_count += 1
                    else:
                        failed_count += 1
                
                # Add delay between batches to respect rate limits
                if i + batch_size < len(analyses):
                    await asyncio.sleep(1)
            
            logger.info(f"Batch refresh completed for user {user_id}: {refreshed_count} refreshed, {failed_count} failed")
            
            return {
                "refreshed": refreshed_count,
                "failed": failed_count,
                "total": len(analyses)
            }
            
        except Exception as e:
            logger.error(f"Error in batch refresh for user {user_id}: {str(e)}")
            return {"refreshed": 0, "failed": 0, "total": 0, "error": str(e)}
    
    async def get_video_url_with_refresh(self, video_id: str, user_id: str) -> Optional[str]:
        """
        Get video URL for a specific video ID, refreshing if needed.
        This is the main method to use when returning video URLs to the frontend.
        
        Args:
            video_id: Facebook video ID
            user_id: User ID
            
        Returns:
            Valid video URL or None if not found/failed
        """
        try:
            db = get_database()
            
            # Find the ad analysis with this video_id
            analysis = await db.ad_analyses.find_one({
                "user_id": user_id,
                "video_id": video_id
            })
            
            if not analysis:
                logger.warning(f"No ad analysis found for video_id {video_id} and user {user_id}")
                return None
            
            current_url = analysis.get("video_url")
            
            if not current_url:
                logger.warning(f"No video URL found in analysis for video_id {video_id}")
                # Try to get fresh URL from Facebook
                fresh_url = await self._get_fresh_video_url(video_id, user_id)
                if fresh_url:
                    await self._update_video_url_in_database(video_id, fresh_url, user_id)
                    return fresh_url
                return None
            
            # Check and refresh if needed
            valid_url = await self.check_and_refresh_video_url(current_url, video_id, user_id)
            return valid_url
            
        except Exception as e:
            logger.error(f"Error getting video URL with refresh for video_id {video_id}: {str(e)}")
            return None 