import httpx
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timedelta
import asyncio
import random
import time
from app.services.facebook_quota import FacebookQuotaManager
import json
from app.core.config import settings

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
                    purchases_value = 0
                    
                    if "actions" in insights:
                        for action in insights["actions"]:
                            if action.get("action_type") == "purchase":
                                purchases = int(action.get("value", 0))
                                break
                    
                    # Extract purchase value from action_values
                    if "action_values" in insights:
                        for action_value in insights["action_values"]:
                            if action_value.get("action_type") == "purchase":
                                purchases_value = float(action_value.get("value", 0))
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
                        "ad_account_id": self.account_id,
                        "campaign_id": ad.get("campaign_id"),
                        "campaign_name": ad.get("campaign", {}).get("name"),
                        "adset_id": ad.get("adset_id"),
                        "adset_name": ad.get("adset", {}).get("name"),
                        "video_id": video_id,
                        "ad_name": ad.get("name"),
                        "purchases": purchases,
                        "additional_metrics": {
                            "impressions": int(insights.get("impressions", 0)),
                            "clicks": int(insights.get("clicks", 0)),
                            "spend": float(insights.get("spend", 0)),
                            "purchases_value": purchases_value,
                            "ctr": float(insights.get("ctr", 0)),
                            "cpc": float(insights.get("cpc", 0)),
                            "cpm": float(insights.get("cpm", 0)),
                            "roas": 0,  # Default value, will be set properly below
                            "reach": int(insights.get("reach", 0)),
                            **video_metrics
                        },
                        "collected_at": datetime.utcnow()
                    }
                    
                    # Handle ROAS calculation properly
                    purchase_roas = insights.get("purchase_roas", [])
                    if purchase_roas and isinstance(purchase_roas, list) and len(purchase_roas) > 0:
                        # Facebook returns purchase_roas as an array of objects with 'value' field
                        if isinstance(purchase_roas[0], dict) and "value" in purchase_roas[0]:
                            metrics["additional_metrics"]["roas"] = float(purchase_roas[0]["value"])
                    else:
                        # Calculate ROAS manually if not provided
                        spend = metrics["additional_metrics"]["spend"]
                        metrics["additional_metrics"]["roas"] = metrics["additional_metrics"]["purchases_value"] / spend if spend > 0 else 0
                    
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
    
    async def _make_api_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make a request to the Facebook Graph API."""
        if params is None:
            params = {}
        
        # Add access token to params
        params["access_token"] = self.access_token
        
        # Make async request
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(f"{self.base_url}/{endpoint}", params=params)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                error_info = ""
                try:
                    error_data = e.response.json()
                    error_info = f": {json.dumps(error_data)}"
                except Exception:
                    pass
                    
                logger.error(f"Facebook API HTTP error {e.response.status_code}{error_info}")
                raise ValueError(f"Facebook API Error: {e.response.status_code}{error_info}")
            except httpx.RequestError as e:
                logger.error(f"Facebook API request error: {str(e)}")
                raise ValueError(f"Facebook API Request Error: {str(e)}")
    
    async def get_ads(self) -> List[Dict[str, Any]]:
        """Get all ads in the account."""
        try:
            endpoint = f"act_{self.account_id}/ads"
            params = {
                "fields": "id,name,campaign_id,campaign{name},adset_id,adset{name},creative{id,video_id,object_story_spec{page_id,video_data{video_id,image_url,image_hash,title,message}}},status",
                "limit": 100
            }
            
            response = await self._make_api_request(endpoint, params)
            
            if "data" not in response:
                logger.error(f"Unexpected Facebook API response: {json.dumps(response)}")
                return []
            
            return response["data"]
        except Exception as e:
            logger.error(f"Error fetching ads: {str(e)}")
            raise
    
    async def get_ad_insights(self, ad_id: str, date_preset: str = "yesterday") -> Dict[str, Any]:
        """Get insights for a specific ad."""
        try:
            endpoint = f"{ad_id}/insights"
            params = {
                "fields": "impressions,clicks,spend,actions,action_values,ctr,cpc,cpm,purchase_roas",
                "date_preset": date_preset,
                "level": "ad"
            }
            
            response = await self._make_api_request(endpoint, params)
            
            if "data" not in response or not response["data"]:
                logger.info(f"No insights data available for ad {ad_id}")
                return {}
            
            return response["data"][0]  # Return first (and usually only) result
        except Exception as e:
            logger.error(f"Error fetching insights for ad {ad_id}: {str(e)}")
            return {}
    
    async def get_ad_insights_with_daterange(
        self, 
        ad_id: str, 
        start_date: str, 
        end_date: str,
        time_increment: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Get insights for a specific ad within a date range with daily breakdown.
        
        Args:
            ad_id: Facebook ad ID
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            time_increment: Breakdown by days (1=daily, 7=weekly, etc.)
        
        Returns:
            List of insights data, one entry per day
        """
        try:
            endpoint = f"{ad_id}/insights"
            params = {
                "fields": "impressions,clicks,spend,actions,action_values",
                "time_range": json.dumps({
                    "since": start_date,
                    "until": end_date
                }),
                "time_increment": time_increment,
                "level": "ad"
            }
            
            response = await self._make_api_request(endpoint, params)
            
            if "data" not in response or not response["data"]:
                logger.info(f"No insights data available for ad {ad_id} in date range {start_date} to {end_date}")
                return []
            
            return response["data"]
        except Exception as e:
            logger.error(f"Error fetching insights for ad {ad_id} with date range: {str(e)}")
            return []
    
    async def get_ad_creatives(self, ad_id: str) -> Dict[str, Any]:
        """Get creative details for a specific ad."""
        try:
            endpoint = f"{ad_id}/"
            params = {
                "fields": "creative{id,object_story_spec{page_id,video_data{video_id,image_url,image_hash,title,message}}}"
            }
            
            response = await self._make_api_request(endpoint, params)
            
            if "creative" not in response:
                logger.info(f"No creative data available for ad {ad_id}")
                return {}
            
            return response["creative"]
        except Exception as e:
            logger.error(f"Error fetching creative for ad {ad_id}: {str(e)}")
            return {}
    
    async def get_video_details(self, video_id: str) -> Dict[str, Any]:
        """Get details for a specific video."""
        try:
            endpoint = f"{video_id}/"
            params = {
                "fields": "id,source,created_time,description,title,thumbnails,captions,picture"
            }
            
            return await self._make_api_request(endpoint, params)
        except Exception as e:
            logger.error(f"Error fetching video details for {video_id}: {str(e)}")
            return {}
    
    async def get_adset_details(self, adset_id: str) -> Dict[str, Any]:
        """Get targeting and other details for an ad set."""
        try:
            endpoint = f"{adset_id}/"
            params = {
                "fields": "id,name,targeting,optimization_goal,bid_strategy,billing_event,status"
            }
            
            return await self._make_api_request(endpoint, params)
        except Exception as e:
            logger.error(f"Error fetching adset details for {adset_id}: {str(e)}")
            return {}
    
    async def collect_ad_metrics_for_range(
        self,
        user_id: str,
        start_date: str,
        end_date: str,
        time_increment: int = 1
    ) -> List[Dict[str, Any]]:
        """Collect metrics for all ads in the specified date range with time increment."""
        try:
            # Get all ads first
            ads = await self.get_ads()
            
            if not ads:
                logger.info(f"No ads found for user {user_id}")
                return []
            
            # Create a lookup of ad details for faster access
            ad_lookup = {}
            for ad in ads:
                ad_id = ad.get("id")
                if ad_id:
                    ad_lookup[ad_id] = {
                        "name": ad.get("name"),
                        "campaign_id": ad.get("campaign_id"),
                        "campaign_name": ad.get("campaign", {}).get("name") if "campaign" in ad else None,
                        "adset_id": ad.get("adset_id"),
                        "adset_name": ad.get("adset", {}).get("name") if "adset" in ad else None,
                        "creative": ad.get("creative", {})
                    }
            
            # Make a single API call to get insights for all ads
            logger.info(f"Fetching account-level insights for {user_id} from {start_date} to {end_date} with time_increment={time_increment}")
            
            endpoint = f"act_{self.account_id}/insights"
            params = {
                "level": "ad",
                "fields": "ad_id,ad_name,campaign_id,campaign_name,adset_id,adset_name,date_start,impressions,clicks,spend,actions,action_values,ctr,cpc,cpm,purchase_roas",
                "time_range": json.dumps({
                    "since": start_date,
                    "until": end_date
                }),
                "time_increment": time_increment,
                "limit": 500  # Increase limit to get more results in one call
            }
            
            response = await self._make_api_request(endpoint, params)
            
            if "data" not in response or not response["data"]:
                logger.info(f"No insights data available in date range {start_date} to {end_date}")
                return []
            
            logger.info(f"Retrieved {len(response['data'])} insight records from account-level API call")
            
            # Log the raw data for debugging
            if len(response["data"]) > 0:
                sample_insight = response["data"][0]
                logger.debug(f"Sample insight date_start: {sample_insight.get('date_start')}")
                logger.debug(f"Sample insight: {json.dumps(sample_insight, default=str)[:200]}...")
            
            # Process all insights data
            metrics_list = []
            for insight in response.get("data", []):
                ad_id = insight.get("ad_id")
                
                if not ad_id:
                    continue
                
                # Get ad details from lookup
                ad_details = ad_lookup.get(ad_id, {})
                
                # Get the date from the insights
                date_start = insight.get("date_start")
                if not date_start:
                    logger.warning(f"Missing date_start in insight for ad {ad_id}")
                    continue
                    
                # Parse the date
                try:
                    logger.debug(f"Processing insight with date_start: {date_start}")
                    collected_at = datetime.strptime(date_start, "%Y-%m-%d")
                    logger.debug(f"Parsed collected_at date: {collected_at.isoformat()} for ad {ad_id}")
                except ValueError as e:
                    logger.error(f"Error parsing date '{date_start}': {str(e)}")
                    collected_at = datetime.utcnow()
                    logger.warning(f"Using current time as fallback: {collected_at.isoformat()}")
                
                # Get creative and video ID
                creative = ad_details.get("creative", {})
                video_id = None
                if creative and "object_story_spec" in creative:
                    video_data = creative.get("object_story_spec", {}).get("video_data", {})
                    if video_data:
                        video_id = video_data.get("video_id")
                
                # Process purchases/conversions from actions
                purchases = 0
                purchases_value = 0
                
                actions = insight.get("actions", [])
                for action in actions:
                    if action.get("action_type") == "purchase":
                        purchases += int(action.get("value", 0))
                
                action_values = insight.get("action_values", [])
                for action_value in action_values:
                    if action_value.get("action_type") == "purchase":
                        purchases_value += float(action_value.get("value", 0))
                
                # Create additional metrics
                impressions = int(insight.get("impressions", 0))
                clicks = int(insight.get("clicks", 0))
                spend = float(insight.get("spend", 0))
                
                # Get metrics directly from Facebook where available
                additional_metrics = {
                    "impressions": impressions,
                    "clicks": clicks,
                    "spend": spend,
                    "purchases_value": purchases_value,
                    "ctr": float(insight.get("ctr", 0)),
                    "cpc": float(insight.get("cpc", 0)),
                    "cpm": float(insight.get("cpm", 0)),
                }
                
                # Extract ROAS from purchase_roas if available, otherwise calculate
                purchase_roas = insight.get("purchase_roas", [])
                if purchase_roas and len(purchase_roas) > 0:
                    # Facebook returns purchase_roas as an array of objects with 'value' field
                    roas_value = float(purchase_roas[0].get("value", 0))
                    additional_metrics["roas"] = roas_value
                else:
                    additional_metrics["roas"] = purchases_value / spend if spend > 0 else 0
                
                # Create metrics object
                metrics_data = {
                    "user_id": user_id,
                    "ad_id": ad_id,
                    "campaign_id": insight.get("campaign_id") or ad_details.get("campaign_id"),
                    "campaign_name": insight.get("campaign_name") or ad_details.get("campaign_name"),
                    "adset_id": insight.get("adset_id") or ad_details.get("adset_id"),
                    "adset_name": insight.get("adset_name") or ad_details.get("adset_name"),
                    "video_id": video_id,
                    "ad_name": insight.get("ad_name") or ad_details.get("name"),
                    "purchases": purchases,
                    "additional_metrics": additional_metrics,
                    "collected_at": collected_at
                }
                
                metrics_list.append(metrics_data)
            
            return metrics_list
            
        except Exception as e:
            logger.error(f"Error collecting ad metrics for user {user_id}: {str(e)}")
            raise
    
    # async def collect_ad_metrics(self, user_id: str) -> List[Dict[str, Any]]:
    #     """Collect metrics for all ads in the account."""
    #     try:
    #         # Get all ads first
    #         ads = await self.get_ads()
            
    #         if not ads:
    #             logger.info(f"No ads found for user {user_id}")
    #             return []
            
    #         # Process each ad in parallel
    #         result_tasks = []
    #         for ad in ads:
    #             task = self._process_ad(ad, user_id)
    #             result_tasks.append(task)
            
    #         # Await all tasks
    #         results = await asyncio.gather(*result_tasks)
            
    #         # Filter out None values
    #         metrics_list = [result for result in results if result]
            
    #         return metrics_list
            
    #     except Exception as e:
    #         logger.error(f"Error collecting ad metrics for user {user_id}: {str(e)}")
    #         raise
    
    async def _process_ad(self, ad: Dict[str, Any], user_id: str) -> Optional[Dict[str, Any]]:
        """Process an ad to collect its metrics."""
        ad_id = ad.get("id")
        if not ad_id:
            return None
        
        # Get insights
        insights = await self.get_ad_insights(ad_id)
        
        if not insights:
            # No insights available
            return None
        
        # Get creative
        creative = ad.get("creative", {})
        
        # Get video ID if applicable
        video_id = None
        if creative and "object_story_spec" in creative:
            video_data = creative.get("object_story_spec", {}).get("video_data", {})
            if video_data:
                video_id = video_data.get("video_id")
        
        # Extract campaign and adset info
        campaign_id = ad.get("campaign_id")
        campaign_name = ad.get("campaign", {}).get("name") if "campaign" in ad else None
        adset_id = ad.get("adset_id")
        adset_name = ad.get("adset", {}).get("name") if "adset" in ad else None
        
        # Get adset targeting
        adset_targeting = None
        if adset_id:
            adset_details = await self.get_adset_details(adset_id)
            adset_targeting = adset_details.get("targeting")
        
        # Process purchases/conversions from actions
        purchases = 0
        purchases_value = 0
        
        actions = insights.get("actions", [])
        for action in actions:
            if action.get("action_type") == "purchase":
                purchases += int(action.get("value", 0))
        
        action_values = insights.get("action_values", [])
        for action_value in action_values:
            if action_value.get("action_type") == "purchase":
                purchases_value += float(action_value.get("value", 0))
        
        # Create additional metrics
        additional_metrics = {
            "impressions": int(insights.get("impressions", 0)),
            "clicks": int(insights.get("clicks", 0)),
            "spend": float(insights.get("spend", 0)),
            "purchases_value": purchases_value,
            "ctr": float(insights.get("ctr", 0)),
            "cpc": float(insights.get("cpc", 0)),
            "cpm": float(insights.get("cpm", 0)),
        }
        
        # Extract ROAS from purchase_roas if available, otherwise calculate
        purchase_roas = insights.get("purchase_roas", [])
        if purchase_roas and len(purchase_roas) > 0:
            # Facebook returns purchase_roas as an array of objects with 'value' field
            roas_value = float(purchase_roas[0].get("value", 0))
            additional_metrics["roas"] = roas_value
        else:
            additional_metrics["roas"] = purchases_value / float(insights.get("spend", 1)) if float(insights.get("spend", 0)) > 0 else 0
        
        # Get the date from insights rather than using current time
        collected_at = datetime.utcnow()  # Default fallback
        
        # Try to extract date from insights data
        date_start = insights.get("date_start")
        if date_start:
            try:
                logger.debug(f"Processing regular insight with date_start: {date_start} for ad {ad_id}")
                collected_at = datetime.strptime(date_start, "%Y-%m-%d")
                logger.debug(f"Parsed collected_at date: {collected_at.isoformat()} for ad {ad_id}")
            except ValueError as e:
                logger.warning(f"Could not parse date from insights: {date_start}, error: {str(e)}")
                logger.warning(f"Using current time as fallback: {collected_at.isoformat()}")
        
        # Create metrics object
        metrics_data = {
            "user_id": user_id,
            "ad_id": ad_id,
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "adset_id": adset_id,
            "adset_name": adset_name,
            "adset_targeting": adset_targeting,
            "video_id": video_id,
            "ad_name": ad.get("name"),
            "purchases": purchases,
            "additional_metrics": additional_metrics,
            "collected_at": collected_at
        }
        
        return metrics_data 