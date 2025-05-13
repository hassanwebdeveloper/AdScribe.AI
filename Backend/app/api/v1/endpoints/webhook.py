from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from app.core.config import settings
from app.core.security import get_current_user_email
from app.core.deps import get_current_user
from app.services.user_service import get_user_by_email
from app.models.user import User
import httpx
import os
import re
import json
import logging
from dotenv import load_dotenv
from app.core.database import get_database

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

# Get the N8N webhook URL from environment variables
N8N_WEBHOOK_URL = settings.N8N_WEBHOOK_URL

router = APIRouter()

class DateRange(BaseModel):
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    daysToAnalyze: Optional[str] = None

class UserInfo(BaseModel):
    fbGraphApiKey: Optional[str] = None
    fbAdAccountId: Optional[str] = None

class Message(BaseModel):
    role: str
    content: str

class WebhookRequest(BaseModel):
    userMessage: str
    previousMessages: List[Message] = []
    dateRange: Optional[DateRange] = None
    userInfo: Optional[UserInfo] = None

@router.post("/chat")
async def process_webhook(
    request: WebhookRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Process a chat message by forwarding it to the N8N webhook
    and returning the response.
    
    This endpoint acts as a proxy to protect sensitive tokens.
    """
    # Make sure we have the webhook URL
    if not N8N_WEBHOOK_URL:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="N8N webhook URL not configured"
        )
    
    # Clean the user message from any existing date range information
    # This pattern will match formats like (Analysis date range: YYYY-MM-DD to YYYY-MM-DD) or (Analysis period: YYYY-MM-DD to YYYY-MM-DD)
    cleaned_message = re.sub(r'\s*\(Analysis (?:date range|period): \d{4}-\d{2}-\d{2} to \d{4}-\d{2}-\d{2}\)\s*', '', request.userMessage)
    
    # Debug logging
    logger.info(f"Original user message: '{request.userMessage}'")
    logger.info(f"Cleaned user message: '{cleaned_message}'")
    
    if request.dateRange and request.dateRange.startDate and request.dateRange.endDate:
        logger.info(f"Date range: {request.dateRange.startDate} to {request.dateRange.endDate}")
    else:
        logger.info("No date range provided")
    
    # Get the date range information to include it with the message
    date_range_info = ""
    if request.dateRange and request.dateRange.startDate and request.dateRange.endDate:
        date_range_info = f"(Analysis date range: {request.dateRange.startDate} to {request.dateRange.endDate})"
    
    # Get the current date range or use default
    start_date = request.dateRange.startDate if request.dateRange and request.dateRange.startDate else None
    end_date = request.dateRange.endDate if request.dateRange and request.dateRange.endDate else None
    
    # Use default dates if not specified
    if not start_date or not end_date:
        # Use last 30 days as default
        from datetime import datetime, timedelta
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    # Find best ad using frequency approach
    best_ad_id = None
    result = None
    
    try:
        # Use the get_best_performing_ad function from prediction router
        from app.routers.prediction import get_best_performing_ad
        
        logger.info(f"Finding best ad using frequency approach and filtering to only analyzed ads")
        
        # Call the function directly (it has the same parameters as the router endpoint)
        result = await get_best_performing_ad(
            start_date=start_date,
            end_date=end_date,
            days_to_predict=7,
            use_time_series=False,  # Use frequency approach
            force_refresh=False,    # Don't force refresh
            use_only_analyzed_ads=True,  # Only use ads that have entries in ad_analyses
            current_user=current_user
        )
        
        # Extract the best ad ID if available
        if result["success"] and result["best_ad"]:
            best_ad_id = result["best_ad"]["ad_id"]
            logger.info(f"Found best ad with ID: {best_ad_id}")
        else:
            logger.warning("No best ad found in prediction results")
    except Exception as e:
        logger.error(f"Error finding best ad: {str(e)}", exc_info=True)
        best_ad_id = None
        result = None
    
    # Retrieve ad analyses from the database
    db = get_database()
    ad_analyses = await db.ad_analyses.find({"user_id": str(current_user.id)}).to_list(length=100)
    
    if not ad_analyses or len(ad_analyses) == 0:
        logger.warning(f"No ad analyses found for user {current_user.id}")
        ad_analyses = []
    
    # If we have a best ad, we need to find related video analyses
    # Create a mapping from ad_id to video_id
    ad_to_video_mapping = {}
    
    # Try to find ad_id to video_id mappings from ad_metrics collection
    if best_ad_id:
        try:
            # First, see if the ad_id is directly present in the historical data
            if result and result.get("historical") and len(result["historical"]) > 0:
                first_historical = result["historical"][0]
                if "ad_id" in first_historical and first_historical["ad_id"] == best_ad_id:
                    logger.info(f"Found direct match in historical data for best ad {best_ad_id}")
                    
                    # Now check if this matches one of our ad_analyses by video_id
                    for analysis in ad_analyses:
                        if analysis.get("video_id") == best_ad_id:
                            ad_to_video_mapping[best_ad_id] = best_ad_id
                            logger.info(f"Found direct mapping: video_id {best_ad_id} is the same as ad_id")
                            break
            
            # Only proceed with the other approaches if we haven't found a mapping yet
            if not ad_to_video_mapping:
                # Simplify the approach - first check if there's a direct match between ad_id and video_id
                for analysis in ad_analyses:
                    ad_id = analysis.get("ad_id") 
                    campaign_id = analysis.get("campaign_id")
                    video_id = analysis.get("video_id")
                    
                    # Direct match with ad_id if it exists
                    if ad_id and ad_id == best_ad_id and video_id:
                        ad_to_video_mapping[best_ad_id] = video_id
                        logger.info(f"Found direct video_id {video_id} match for best ad {best_ad_id}")
                        break
                    
                    # If no direct match, try matching via campaign_id
                    if not ad_to_video_mapping and campaign_id and video_id:
                        # See if we can find the campaign_id in the ad_metrics collection
                        ad_metrics = await db.ad_metrics.find({"user_id": str(current_user.id), "ad_id": best_ad_id, "campaign_id": campaign_id}).limit(1).to_list(length=1)
                        if ad_metrics and len(ad_metrics) > 0:
                            ad_to_video_mapping[best_ad_id] = video_id
                            logger.info(f"Found campaign match video_id {video_id} for best ad {best_ad_id}")
                            break
                
                # If no mapping found yet, try the fallback approach with campaign_id lookup
                if not ad_to_video_mapping:
                    # Query ad_metrics to get the campaign_id for the best ad
                    ad_metrics = await db.ad_metrics.find({"user_id": str(current_user.id), "ad_id": best_ad_id}).limit(1).to_list(length=1)
                    
                    if ad_metrics and len(ad_metrics) > 0:
                        campaign_id = ad_metrics[0].get("campaign_id")
                        
                        # Then find video_ids in ad_analyses that match this campaign_id
                        if campaign_id:
                            for analysis in ad_analyses:
                                if analysis.get("campaign_id") == campaign_id and analysis.get("video_id"):
                                    ad_to_video_mapping[best_ad_id] = analysis.get("video_id")
                                    logger.info(f"Found campaign_id match video_id {analysis.get('video_id')} for best ad {best_ad_id}")
                                    break
                                    
        except Exception as e:
            logger.error(f"Error mapping ad_id to video_id: {str(e)}")
            
    # If still no mapping found, just use the first ad analysis's video_id
    if best_ad_id and not ad_to_video_mapping and ad_analyses and len(ad_analyses) > 0:
        first_video_id = ad_analyses[0].get("video_id")
        if first_video_id:
            ad_to_video_mapping[best_ad_id] = first_video_id
            logger.info(f"No mapping found, using first available video_id {first_video_id} for best ad {best_ad_id}")
    
    # Extract relevant data from ad analyses (video_id, audio_description, video_description)
    ad_analyses_data = []
    video_ids = []
    
    # If we have a best ad and found a mapping to video_id, filter to only include that one
    best_video_id = ad_to_video_mapping.get(best_ad_id) if best_ad_id else None
    
    # Flag to track if we found any matching ad analyses
    found_matching_analyses = False
    
    # Get best ad metrics if available
    best_ad_metrics = {}
    if best_ad_id and result and result.get("best_ad"):
        best_ad_metrics = result["best_ad"].get("average_metrics", {})
        logger.info(f"Found best ad metrics: {best_ad_metrics}")
        
        # Get the best ad's historical data if available
        best_ad_historical = result.get("historical", [])
        if best_ad_historical and len(best_ad_historical) > 0:
            # Extract additional information from historical data
            first_historical = best_ad_historical[0]
            if "ad_name" in first_historical:
                logger.info(f"Best ad name from historical data: {first_historical['ad_name']}")
    else:
        logger.warning("No best ad metrics found to include in payload")
    
    for analysis in ad_analyses:
        video_id = analysis.get("video_id")
        
        # Skip if no video_id is present
        if video_id is None:
            continue
            
        # Filter for best video if we have one
        if best_video_id and video_id != best_video_id:
            continue
            
        # We found a match
        found_matching_analyses = True
        
        # Create the ad analysis data with additional fields
        ad_data = {
            "video_id": video_id,
            "audio_description": analysis.get("audio_description"),
            "video_description": analysis.get("video_description"),
            "video_url": analysis.get("video_url"),
            "ad_description": analysis.get("ad_message"),
            "video_title": analysis.get("ad_title", "")  # Add video title from ad_title
        }
        
        # Add best ad metrics to the ad analysis data
        if best_ad_metrics:
            ad_data["metrics"] = best_ad_metrics
        
        ad_analyses_data.append(ad_data)
        video_ids.append(video_id)
    
    # If we didn't find any matching analyses but have ad analyses available, use the first one as fallback
    if not found_matching_analyses and ad_analyses and len(ad_analyses) > 0:
        for analysis in ad_analyses:
            video_id = analysis.get("video_id")
            if video_id is not None:
                # Create the ad analysis data with additional fields
                ad_data = {
                    "video_id": video_id,
                    "audio_description": analysis.get("audio_description"),
                    "video_description": analysis.get("video_description"),
                    "video_url": analysis.get("video_url"),
                    "ad_description": analysis.get("ad_message"),
                    "video_title": analysis.get("ad_title", "")  # Add video title from ad_title
                }
                
                # Add best ad metrics to the ad analysis data
                if best_ad_metrics:
                    ad_data["metrics"] = best_ad_metrics
                
                ad_analyses_data.append(ad_data)
                video_ids.append(video_id)
                logger.info(f"Using fallback ad analysis with video_id {video_id}")
                break
    
    if best_video_id and found_matching_analyses:
        logger.info(f"Filtered to {len(ad_analyses_data)} ad analyses for best ad video_id {best_video_id}")
    elif found_matching_analyses:
        logger.info(f"No specific video mapping found, using {len(ad_analyses_data)} ad analyses")
    else:
        logger.info(f"Using fallback ad analysis, total: {len(ad_analyses_data)}")
    
    # Create the payload for the N8N webhook
    payload = {
        "userMessage": cleaned_message,  # Use the cleaned message without the date range
        "previousMessages": [
            {"role": msg.role, "content": msg.content}
            for msg in request.previousMessages
        ],
        "dateRange": request.dateRange.model_dump() if request.dateRange else {},
        "userInfo": {
            "fbGraphApiKey": current_user.fb_graph_api_key,
            "fbAdAccountId": current_user.fb_ad_account_id,
        },
        "analysisContext": date_range_info,  # Add date range as separate field
        "adAnalyses": ad_analyses_data,  # Already filtered to include only the best ad's analysis
        "videoIds": video_ids  # Add just the video IDs as a separate object (also filtered to best ad)
    }
    
    # Log payload structure for debugging (excluding sensitive data)
    logger.info(f"Sending payload with {len(ad_analyses_data)} ad analyses")
    if ad_analyses_data:
        first_ad = ad_analyses_data[0]
        logger.info(f"First ad has fields: {list(first_ad.keys())}")
        if "metrics" in first_ad:
            logger.info(f"Metrics included: {list(first_ad['metrics'].keys())}")
    
    # Note: We don't include a separate 'bestAd' property as requested,
    # since the adAnalyses array contains only the best ad's data
    
    try:
        # Forward the request to N8N
        async with httpx.AsyncClient(timeout=120.0) as client:  # Extended timeout for AI processing
            response = await client.post(
                N8N_WEBHOOK_URL, 
                json=payload
            )
            
            # Check if the request was successful
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"N8N webhook returned error: {response.text}"
                )
            
            # Get the response data
            try:
                response_data = response.json()
                logger.info(f"N8N response: {response_data}")
                
                # Check for ad content in the response
                ad_content = None
                output_content = None
                
                # Handle different response formats
                if isinstance(response_data, dict):
                    # Extract output content
                    if "output" in response_data:
                        output_content = response_data["output"]
                    elif "result" in response_data:
                        output_content = response_data["result"]
                    elif "message" in response_data:
                        output_content = response_data["message"]
                    
                    # Look for ad property
                    if "ad" in response_data:
                        ad_content = response_data["ad"]
                        logger.info(f"Found ad content in response: {ad_content}")
                elif isinstance(response_data, list) and len(response_data) > 0:
                    # Extract from the first item if it's a list
                    if isinstance(response_data[0], dict):
                        if "output" in response_data[0]:
                            output_content = response_data[0]["output"]
                        if "ad" in response_data[0]:
                            ad_content = response_data[0]["ad"]
                            logger.info(f"Found ad content in list response: {ad_content}")
                
                # If no structured output was found, use the whole response
                if output_content is None:
                    output_content = response_data
                
                # Construct the final response with output and ad content
                result = {"output": output_content}
                
                # If ad content is not found in response, create it from database
                if not ad_content and ad_analyses_data and len(ad_analyses_data) > 0:
                    logger.info("No ad content in N8N response, creating from database")
                    try:
                        # Get the first (and should be only) ad analysis
                        ad_analysis = ad_analyses_data[0]
                        
                        # Get title from multiple potential sources
                        title = ad_analysis.get("video_title", "")
                        if not title and best_ad_id and result and result.get("best_ad"):
                            # Try to get title from best_ad data
                            title = result["best_ad"].get("ad_title", "")
                            if not title:
                                title = result["best_ad"].get("ad_name", "")
                                
                            # If still no title, try from historical data
                            if not title and result.get("historical") and len(result["historical"]) > 0:
                                first_historical = result["historical"][0]
                                title = first_historical.get("ad_name", "")
                                if not title:
                                    title = first_historical.get("ad_title", "")
                        
                        if not title:
                            title = "Ad"
                            
                        logger.info(f"Using title: {title} for ad content")
                        
                        # Create ad content from database information
                        ad_content = {
                            "title": title,
                            "description": ad_analysis.get("ad_description", ""),
                            "video_url": ad_analysis.get("video_url", ""),
                            "is_active": True,  # Default to active
                            "purchases": 0      # Default to 0
                        }
                        
                        # Add metrics if available
                        if "metrics" in ad_analysis:
                            ad_metrics = ad_analysis["metrics"]
                            # Add relevant metrics
                            if "conversions" in ad_metrics:
                                try:
                                    ad_content["purchases"] = int(float(ad_metrics["conversions"]))
                                except (ValueError, TypeError):
                                    ad_content["purchases"] = 0
                            
                            if "revenue" in ad_metrics:
                                try:
                                    ad_content["revenue"] = float(ad_metrics["revenue"])
                                except (ValueError, TypeError):
                                    ad_content["revenue"] = 0.0
                            
                            # Add more metrics that might be useful
                            if "roas" in ad_metrics:
                                try:
                                    ad_content["roas"] = float(ad_metrics["roas"])
                                except (ValueError, TypeError):
                                    ad_content["roas"] = 0.0
                            
                            if "ctr" in ad_metrics:
                                try:
                                    ad_content["ctr"] = float(ad_metrics["ctr"])
                                except (ValueError, TypeError):
                                    ad_content["ctr"] = 0.0
                        
                        # Add video descriptions if available
                        if "video_description" in ad_analysis and ad_analysis["video_description"]:
                            ad_content["video_description"] = ad_analysis["video_description"]
                        
                        if "audio_description" in ad_analysis and ad_analysis["audio_description"]:
                            ad_content["audio_description"] = ad_analysis["audio_description"]
                            
                        # Add video ID for reference
                        if "video_id" in ad_analysis and ad_analysis["video_id"]:
                            ad_content["video_id"] = ad_analysis["video_id"]
                            
                        logger.info(f"Created ad content from database: {ad_content}")
                    except Exception as e:
                        logger.error(f"Error creating ad content from database: {str(e)}", exc_info=True)
                        # Create a basic fallback ad if all else fails
                        ad_content = {
                            "title": "Ad",
                            "description": "Advertisement",
                            "video_url": "",
                            "is_active": True,
                            "purchases": 0
                        }
                
                # Add ad content if found or created
                if ad_content:
                    logger.info(f"Processing ad content of type: {type(ad_content)}")
                    
                    # If ad is a string, ensure it's valid JSON and properly structured
                    if isinstance(ad_content, str):
                        logger.info(f"Ad content is a string: {ad_content[:100]}")
                        
                        # Check if it's a JSON-like string but not properly formatted
                        # Example: {"title": Cash refund if not satisfied, "description":100% Pure White...}
                        if ad_content.startswith('{') and '"title":' in ad_content and not ad_content.startswith('{"'):
                            logger.info("Found malformed JSON-like string, attempting to fix")
                            try:
                                # Try to fix common issues with the JSON string
                                # 1. Add quotes around property names if missing
                                fixed_json = re.sub(r'([{,])\s*([a-zA-Z_]+):', r'\1"\2":', ad_content)
                                # 2. Ensure values have quotes if they're strings without quotes
                                fixed_json = re.sub(r':\s*([^",\d{}\[\]]+)([,}])', r':"\1"\2', fixed_json)
                                
                                logger.info(f"Attempting to parse fixed JSON: {fixed_json[:100]}")
                                try:
                                    parsed_ad = json.loads(fixed_json)
                                    logger.info("Successfully parsed fixed JSON")
                                    result["ad"] = parsed_ad
                                except json.JSONDecodeError as e:
                                    logger.warning(f"Still failed to parse fixed JSON: {e}")
                                    # Fallback to manual field extraction
                                    ad_obj = {}
                                    # Extract fields using regex
                                    title_match = re.search(r'"title":\s*([^,}]+)', ad_content)
                                    if title_match:
                                        ad_obj["title"] = title_match.group(1).strip().strip('"\'')
                                    
                                    desc_match = re.search(r'"description":\s*([^,}]+)', ad_content)
                                    if desc_match:
                                        ad_obj["description"] = desc_match.group(1).strip().strip('"\'')
                                    
                                    video_match = re.search(r'"video_url":\s*([^,}]+)', ad_content)
                                    if video_match:
                                        ad_obj["video_url"] = video_match.group(1).strip().strip('"\'')
                                    
                                    active_match = re.search(r'"is_active":\s*([^,}]+)', ad_content)
                                    if active_match:
                                        active_val = active_match.group(1).strip().lower()
                                        ad_obj["is_active"] = active_val == "true"
                                    
                                    purchases_match = re.search(r'"purchases":\s*(\d+)', ad_content)
                                    if purchases_match:
                                        ad_obj["purchases"] = int(purchases_match.group(1))
                                    
                                    logger.info(f"Manual extraction created: {ad_obj}")
                                    result["ad"] = ad_obj
                            except Exception as e:
                                logger.error(f"Error fixing malformed JSON: {e}")
                                # Fallback to simple structure
                                result["ad"] = {
                                    "title": "Sponsored Content",
                                    "description": ad_content,
                                    "video_url": "",
                                    "is_active": True,
                                    "purchases": 0
                                }
                        else:
                            try:
                                # First, try to parse the JSON string normally
                                parsed_ad = json.loads(ad_content)
                                logger.info(f"Successfully parsed ad JSON: {parsed_ad}")
                                
                                # Check if this is already the expected format
                                if isinstance(parsed_ad, dict) and all(key in parsed_ad for key in ["title", "description"]):
                                    # It's already in the right format, use it directly
                                    logger.info("Ad data is in the expected format")
                                    result["ad"] = parsed_ad
                                else:
                                    # Not in the right format, but we have JSON
                                    logger.warning(f"Ad data JSON doesn't have expected structure: {parsed_ad}")
                                    result["ad"] = parsed_ad
                            except json.JSONDecodeError as e:
                                # If JSON parsing fails, maybe it's a quoted string - try to clean and parse
                                logger.warning(f"JSON decode error for ad data: {e}")
                                try:
                                    # Remove leading/trailing quotes and try parsing again if it looks like JSON
                                    cleaned_json = ad_content.strip('"\'')
                                    if cleaned_json.startswith('{') and cleaned_json.endswith('}'):
                                        logger.info(f"Trying to parse cleaned JSON: {cleaned_json[:100]}")
                                        parsed_ad = json.loads(cleaned_json)
                                        logger.info(f"Successfully parsed cleaned ad JSON: {parsed_ad}")
                                        result["ad"] = parsed_ad
                                    else:
                                        # Not JSON, keep it as a string
                                        logger.warning("Ad data is not valid JSON, keeping as string")
                                        result["ad"] = {"title": "Ad", "description": ad_content, "video_url": "", "is_active": True, "purchases": 0}
                                except Exception as inner_e:
                                    logger.error(f"Error processing cleaned ad data: {inner_e}")
                                    # Fallback to simple structure if all else fails
                                    result["ad"] = {"title": "Ad", "description": ad_content, "video_url": "", "is_active": True, "purchases": 0}
                    elif isinstance(ad_content, dict):
                        # It's already a dict, ensure it has the expected format
                        logger.info(f"Ad content is a dict: {ad_content}")
                        
                        # Check if all required fields are present
                        required_fields = ["title", "description", "video_url", "is_active", "purchases"]
                        if all(field in ad_content for field in required_fields):
                            logger.info("Ad dict has all required fields")
                            result["ad"] = ad_content
                        else:
                            # Missing required fields, create a structure with what we have
                            logger.warning(f"Ad dict missing required fields. Available: {ad_content.keys()}")
                            
                            # Create a valid ad structure with defaults for missing fields
                            valid_ad = {
                                "title": ad_content.get("title", "Ad"),
                                "description": ad_content.get("description", str(ad_content)),
                                "video_url": ad_content.get("video_url", ""),
                                "is_active": ad_content.get("is_active", True),
                                "purchases": ad_content.get("purchases", 0)
                            }
                            result["ad"] = valid_ad
                    else:
                        # Not a string or dict, convert to string representation
                        logger.warning(f"Ad content is not a string or dict: {type(ad_content)}")
                        result["ad"] = {
                            "title": "Ad", 
                            "description": str(ad_content), 
                            "video_url": "", 
                            "is_active": True, 
                            "purchases": 0
                        }
                    
                    logger.info(f"Final ad content in result: {result['ad']}")
                
                return result
                
            except Exception as e:
                logger.error(f"Error processing N8N response: {str(e)}", exc_info=True)
                # If we can't parse the JSON or encounter another error, return the raw text
                return {"output": response.text}
    
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error communicating with N8N webhook: {str(e)}"
        ) 

@router.post("/callback", response_model=Dict[str, Any])
async def webhook_callback(
    data: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user)
):
    """
    Handle webhook callbacks from external services
    """
    # ... existing code ... 