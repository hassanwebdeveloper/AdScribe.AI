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
    
    # Retrieve ad analyses from the database
    db = get_database()
    ad_analyses = await db.ad_analyses.find({"user_id": str(current_user.id)}).to_list(length=100)
    
    # Extract relevant data from ad analyses (video_id, audio_description, video_description)
    ad_analyses_data = []
    video_ids = []
    for analysis in ad_analyses:
        if analysis.get("video_id") is not None:
            ad_analyses_data.append({
                "video_id": analysis.get("video_id"),
                "audio_description": analysis.get("audio_description"),
                "video_description": analysis.get("video_description"),
                "video_url": analysis.get("video_url"),
                "ad_description": analysis.get("ad_message")
            })
            video_ids.append(analysis.get("video_id"))
    
    logger.info(f"Retrieved {len(ad_analyses_data)} ad analyses for user {current_user.id}")
    
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
        "adAnalyses": ad_analyses_data,  # Add ad analyses data
        "videoIds": video_ids  # Add just the video IDs as a separate object
    }
    
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
                
                # Add ad content if found
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