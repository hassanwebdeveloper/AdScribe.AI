import json
import logging
import httpx
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class FacebookAdService:
    """
    Service to interact with Facebook Marketing API
    """
    
    base_url = "https://graph.facebook.com/v18.0"  # Using latest stable version
    
    def __init__(self, ad_account_id: str, access_token: str):
        """
        Initialize Facebook Ad Service
        
        Args:
            ad_account_id: Facebook Ad Account ID
            access_token: Facebook Access Token
        """
        # Ensure ad_account_id starts with 'act_'
        if not ad_account_id.startswith('act_'):
            self.ad_account_id = f"act_{ad_account_id}"
        else:
            self.ad_account_id = ad_account_id
            
        self.access_token = access_token

    async def get_ad_insights(
        self,
        start_date: str,
        end_date: str,
        time_increment: int = 1,
        fields: List[str] = None,
        level: str = "account"
    ) -> List[Dict[str, Any]]:
        """
        Fetch ad insights from Facebook
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            time_increment: Time increment for data breakdown (1 = daily)
            fields: List of fields to fetch
            level: Level of data (account, campaign, adset, ad)
            
        Returns:
            List of insight objects
        """
        if fields is None:
            fields = [
                "spend", "impressions", "clicks", "actions",
                "action_values", "date_start"
            ]
            
        # Add id and name fields based on the level
        if level == "campaign":
            fields.extend(["campaign_id", "campaign_name"])
        elif level == "adset":
            fields.extend(["adset_id", "adset_name"])
        elif level == "ad":
            fields.extend(["ad_id", "ad_name"])
        
        try:
            # Build the endpoint URL
            endpoint = f"{self.ad_account_id}/insights"
            
            # Prepare parameters
            params = {
                "time_range": json.dumps({
                    "since": start_date,
                    "until": end_date
                }),
                "time_increment": time_increment,
                "level": level,
                "fields": ",".join(fields),
                "access_token": self.access_token
            }
            
            # Make the request
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    f"{self.base_url}/{endpoint}",
                    params=params
                )
                
                # Check for errors
                if response.status_code != 200:
                    logger.error(f"Facebook API error: {response.text}")
                    return []
                
                data = response.json()
                
                # Handle pagination
                insights = data.get("data", [])
                paging = data.get("paging", {})
                
                # If there's a next page, fetch it
                while "next" in paging:
                    async with httpx.AsyncClient(timeout=60.0) as next_client:
                        next_response = await next_client.get(paging["next"])
                        
                        if next_response.status_code != 200:
                            break
                        
                        next_data = next_response.json()
                        insights.extend(next_data.get("data", []))
                        paging = next_data.get("paging", {})
                
                return insights
                
        except Exception as e:
            logger.error(f"Error fetching ad insights: {str(e)}")
            return [] 