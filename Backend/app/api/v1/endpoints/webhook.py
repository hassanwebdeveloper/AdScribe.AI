from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from app.core.config import settings
from app.core.security import get_current_user_email
from app.services.user_service import get_user_by_email
import httpx
import os
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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
    email: str = Depends(get_current_user_email)
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
    
    # Get the user (to ensure they are authenticated)
    user = await get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Clean the user message from any existing date range information
    # This pattern will match formats like (Analysis date range: YYYY-MM-DD to YYYY-MM-DD) or (Analysis period: YYYY-MM-DD to YYYY-MM-DD)
    cleaned_message = re.sub(r'\s*\(Analysis (?:date range|period): \d{4}-\d{2}-\d{2} to \d{4}-\d{2}-\d{2}\)\s*', '', request.userMessage)
    
    # Debug logging
    print(f"Original user message: '{request.userMessage}'")
    print(f"Cleaned user message: '{cleaned_message}'")
    
    if request.dateRange and request.dateRange.startDate and request.dateRange.endDate:
        print(f"Date range: {request.dateRange.startDate} to {request.dateRange.endDate}")
    else:
        print("No date range provided")
    
    # Get the date range information to include it with the message
    date_range_info = ""
    if request.dateRange and request.dateRange.startDate and request.dateRange.endDate:
        date_range_info = f"(Analysis date range: {request.dateRange.startDate} to {request.dateRange.endDate})"
    
    # Create the payload for the N8N webhook
    payload = {
        "userMessage": cleaned_message,  # Use the cleaned message without the date range
        "previousMessages": [
            {"role": msg.role, "content": msg.content}
            for msg in request.previousMessages
        ],
        "dateRange": request.dateRange.model_dump() if request.dateRange else {},
        "userInfo": {
            "fbGraphApiKey": user.fb_graph_api_key,
            "fbAdAccountId": user.fb_ad_account_id,
        },
        "analysisContext": date_range_info  # Add date range as separate field
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
                print(f"N8N response: {response_data}")
                
                # If the response is already properly formatted, return it
                if isinstance(response_data, dict) and ("output" in response_data or "result" in response_data or "message" in response_data):
                    return response_data
                
                # If the response is an array with objects containing output property, format it
                if isinstance(response_data, list) and len(response_data) > 0 and isinstance(response_data[0], dict) and "output" in response_data[0]:
                    return {"output": response_data[0]["output"]}
                
                # Otherwise, wrap the entire response in an output field
                return {"output": response_data}
            except Exception as e:
                print(f"Error processing N8N response: {str(e)}")
                # If we can't parse the JSON or encounter another error, return the raw text
                return {"output": response.text}
    
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error communicating with N8N webhook: {str(e)}"
        ) 