import httpx
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timedelta
import asyncio
import random
import time
from app.services.facebook_quota import FacebookQuotaManager

logger = logging.getLogger(__name__)

class FacebookAdService:
    FB_API_VERSION = "v19.0"
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds
    RATE_LIMIT_DELAY = 5  # seconds
    REQUEST_DELAY = 1  # Delay between requests
    
    # Global tracking of requests to help debug rate limits
    _request_times = []
    _request_count = 0
    
    def __init__(self, access_token: str, account_id: str):
        self.access_token = access_token
        # Ensure account_id is in the correct format (remove 'act_' if present)
        self.account_id = account_id.replace('act_', '')
        self.base_url = f"https://graph.facebook.com/{self.FB_API_VERSION}"
        self._last_request_time = 0  # Track last request time
        self._client = None
        self.quota_manager = FacebookQuotaManager()
        
        # Log initialization with masked token
        masked_token = access_token[:5] + "..." + access_token[-4:] if len(access_token) > 10 else "***"
        logger.info(f"Initializing FacebookAdService for account: {self.account_id}, token: {masked_token}")
    
    @property
    async def client(self):
        """Get or create httpx client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(
                    max_keepalive_connections=5,
                    max_connections=10,
                    keepalive_expiry=30.0
                )
            )
        return self._client
    
    @classmethod
    def _track_request_rate(cls):
        """Track request rate to help debug rate limiting."""
        now = time.time()
        cls._request_count += 1
        
        # Add current time to the list
        cls._request_times.append(now)
        
        # Remove times older than 1 minute
        one_minute_ago = now - 60
        cls._request_times = [t for t in cls._request_times if t > one_minute_ago]
        
        # Log request rate statistics every 10 requests
        if cls._request_count % 10 == 0:
            requests_per_minute = len(cls._request_times)
            logger.warning(f"Facebook API request rate: {requests_per_minute} requests in the last minute")
    
    async def _make_request(self, url: str, params: Dict[str, Any], retry_count: int = 0) -> Dict[str, Any]:
        """Make a request to Facebook API with improved rate limiting."""
        # Check quota before making request
        user_id = params.get("user_id", "unknown")
        
        # First, track our own request rate
        self._track_request_rate()
        
        # Wait for quota if needed (max 2 minutes)
        if not await self.quota_manager.wait_for_quota(user_id, max_wait_seconds=120):
            raise ValueError(f"Facebook API quota exceeded, please try again later")
        
        try:
            # Add delay between requests
            current_time = datetime.utcnow().timestamp()
            time_since_last_request = current_time - self._last_request_time
            if time_since_last_request < self.REQUEST_DELAY:
                delay = self.REQUEST_DELAY - time_since_last_request
                logger.debug(f"Adding delay of {delay:.2f}s between requests")
                await asyncio.sleep(delay)
            
            self._last_request_time = datetime.utcnow().timestamp()
            
            # Log the request details
            logger.debug(f"Making request to {url} params: {params.get('fields', '')[:50]}...")
            request_start = time.time()
            
            client = await self.client
            
            # Use a timeout that increases with retry count
            timeout = 30.0 * (retry_count + 1)
            response = await client.get(url, params=params, timeout=timeout)
            
            # Log response time
            request_time = time.time() - request_start
            logger.debug(f"Response received in {request_time:.2f}s with status {response.status_code}")
            
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutError:
            if retry_count < self.MAX_RETRIES:
                # Use a longer delay for timeouts
                delay = (self.RATE_LIMIT_DELAY * 2 * (2 ** retry_count)) + random.uniform(1, 5)
                logger.warning(f"Request timeout for URL {url.split('?')[0]}, retrying in {delay:.2f} seconds... (Attempt {retry_count + 1}/{self.MAX_RETRIES})")
                await asyncio.sleep(delay)
                return await self._make_request(url, params, retry_count + 1)
            else:
                error_msg = f"Max retries reached after timeouts: {url.split('?')[0]}"
                logger.error(error_msg)
                raise ValueError(error_msg)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403 and "Application request limit reached" in e.response.text:
                if retry_count < self.MAX_RETRIES:
                    # Exponential backoff with jitter
                    delay = (self.RATE_LIMIT_DELAY * (2 ** retry_count)) + random.uniform(0, 1)
                    logger.warning(f"Rate limit hit for URL {url.split('?')[0]}, retrying in {delay:.2f} seconds... (Attempt {retry_count + 1}/{self.MAX_RETRIES})")
                    logger.warning(f"Rate limit response: {e.response.text[:200]}")
                    await asyncio.sleep(delay)
                    return await self._make_request(url, params, retry_count + 1)
                else:
                    error_msg = f"Max retries reached for rate limit: {url.split('?')[0]}"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
            error_msg = f"HTTP {e.response.status_code} error: {e.response.text[:200]}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Error making request to {url.split('?')[0]}: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    async def get_ad_accounts(self) -> List[Dict[str, Any]]:
        """Get all ad accounts for the user."""
        url = f"{self.base_url}/me/adaccounts"
        params = {
            "access_token": self.access_token,
            "fields": "id,name,account_status"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json().get("data", [])
    
    async def get_ads_with_insights(self) -> List[Dict[str, Any]]:
        """Get all ads with their insights in a single call."""
        url = f"{self.base_url}/act_{self.account_id}/ads"
        
        # Calculate date range (yesterday to today)
        end_date = datetime.utcnow().strftime('%Y-%m-%d')
        start_date = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        logger.info(f"Getting ads with insights for account {self.account_id} from {start_date} to {end_date}")
        
        params = {
            "access_token": self.access_token,
            "fields": "id,name,campaign_id,campaign{name},adset_id,adset{name},creative{id,video_id,effective_object_story_id,object_story_spec},status,insights.time_range({'since':'" + start_date + "','until':'" + end_date + "'}){actions,action_values,video_p25_watched_actions,video_p50_watched_actions,video_p75_watched_actions,video_p95_watched_actions,video_p100_watched_actions,impressions,reach,clicks,spend,cpc,cpm,ctr,purchase_roas}",
            "limit": 100  # Reduced limit to prevent rate limiting
        }
        
        try:
            data = await self._make_request(url, params)
            if not data:
                logger.warning("No data returned from Facebook API")
                return []
            
            ads_count = len(data.get("data", []))
            logger.info(f"Retrieved {ads_count} ads from Facebook API")
            
            # Check if there's pagination
            if "paging" in data and "next" in data["paging"]:
                logger.info(f"Pagination detected in Facebook API response, but not fetching additional pages to avoid rate limits")
            
            return data.get("data", [])
        except Exception as e:
            error_msg = f"Error getting ads with insights: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    async def get_video_url(self, video_id: str) -> Optional[str]:
        """Get video URL for a specific video ID."""
        if not video_id:
            return None
            
        url = f"{self.base_url}/{video_id}"
        params = {
            "access_token": self.access_token,
            "fields": "source,permalink_url"
        }
        
        try:
            data = await self._make_request(url, params)
            return data.get("permalink_url") or data.get("source")
        except Exception as e:
            logger.error(f"Error getting video URL for {video_id}: {str(e)}")
            return None
    
    async def collect_ad_metrics(self, user_id: str) -> List[Dict[str, Any]]:
        """Collect metrics for all ads sequentially, similar to N8N's approach."""
        try:
            logger.info(f"Starting to collect ad metrics for user {user_id}")
            ads = await self.get_ads_with_insights()
            
            if not ads:
                logger.warning(f"No ads found for user {user_id}")
                return []
            
            logger.info(f"Processing {len(ads)} ads for user {user_id}")
            stored_metrics = []
            
            # Process ads one by one, like N8N does
            for i, ad in enumerate(ads):
                try:
                    logger.info(f"Processing ad {i+1}/{len(ads)} with ID {ad.get('id', 'unknown')}")
                    process_start = time.time()
                    
                    # Extract video_id from creative
                    video_id = None
                    if "creative" in ad and "object_story_spec" in ad["creative"]:
                        video_id = ad["creative"]["object_story_spec"].get("video_data", {}).get("video_id")
                    
                    # Extract insights
                    insights = ad.get("insights", {}).get("data", [{}])[0]
                    
                    # Extract purchases from actions
                    purchases = 0
                    if "actions" in insights:
                        for action in insights["actions"]:
                            if action.get("action_type") == "purchase":
                                purchases = int(action.get("value", 0))
                                break
                    
                    # Extract video watch metrics
                    video_metrics = {
                        "video_p25_watched": 0,
                        "video_p50_watched": 0,
                        "video_p75_watched": 0,
                        "video_p95_watched": 0,
                        "video_p100_watched": 0
                    }
                    
                    if "video_p25_watched_actions" in insights:
                        video_metrics["video_p25_watched"] = int(insights["video_p25_watched_actions"][0].get("value", 0))
                    if "video_p50_watched_actions" in insights:
                        video_metrics["video_p50_watched"] = int(insights["video_p50_watched_actions"][0].get("value", 0))
                    if "video_p75_watched_actions" in insights:
                        video_metrics["video_p75_watched"] = int(insights["video_p75_watched_actions"][0].get("value", 0))
                    if "video_p95_watched_actions" in insights:
                        video_metrics["video_p95_watched"] = int(insights["video_p95_watched_actions"][0].get("value", 0))
                    if "video_p100_watched_actions" in insights:
                        video_metrics["video_p100_watched"] = int(insights["video_p100_watched_actions"][0].get("value", 0))
                    
                    # Format metrics for storage
                    metrics = {
                        "user_id": user_id,
                        "ad_id": ad["id"],
                        "ad_name": ad.get("name"),
                        "video_id": video_id,
                        # Skip video URL, only store video ID
                        "campaign_id": ad.get("campaign_id"),
                        "campaign_name": ad.get("campaign", {}).get("name"),
                        "adset_id": ad.get("adset_id"),
                        "adset_name": ad.get("adset", {}).get("name"),
                        "ad_status": ad.get("status"),
                        "purchases": purchases,
                        "additional_metrics": {
                            "impressions": int(insights.get("impressions", 0)),
                            "reach": int(insights.get("reach", 0)),
                            "clicks": int(insights.get("clicks", 0)),
                            "spend": float(insights.get("spend", 0)),
                            "cpc": float(insights.get("cpc", 0)),
                            "cpm": float(insights.get("cpm", 0)),
                            "ctr": float(insights.get("ctr", 0)),
                            "purchase_roas": insights.get("purchase_roas", []),
                            **video_metrics
                        },
                        "collected_at": datetime.utcnow()
                    }
                    
                    # Calculate processing time
                    process_time = time.time() - process_start
                    logger.info(f"Processed ad {i+1}/{len(ads)} in {process_time:.2f}s")
                    
                    stored_metrics.append(metrics)
                    
                    # Add a delay between processing each ad to avoid overloading
                    if i < len(ads) - 1:  # Don't delay after the last ad
                        await asyncio.sleep(self.REQUEST_DELAY / 2)  # Use half the normal delay
                    
                except Exception as e:
                    logger.error(f"Error processing ad {ad.get('id', 'unknown')}: {str(e)}")
                    continue
            
            logger.info(f"Completed processing {len(stored_metrics)} ads for user {user_id}")
            return stored_metrics
            
        except Exception as e:
            error_msg = f"Error collecting metrics: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg) 