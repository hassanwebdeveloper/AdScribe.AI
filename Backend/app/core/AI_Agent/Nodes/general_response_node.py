"""
General Response Node for LangGraph AI Agent

This node handles general queries and default responses using OpenAI.
"""

from typing import Dict, List, Any
from openai import AsyncOpenAI
import logging
from app.core.config import settings

# Set up logging
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = AsyncOpenAI(api_key=settings.openai_api_key)

class GeneralResponseNode:
    """
    Node responsible for handling general queries and providing default responses.
    """
    
    def __init__(self):
        """Initialize the general response node."""
        pass
    
    async def generate_general_response(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a general OpenAI response for queries that don't require ad script generation.
        
        Args:
            state: Agent state containing user_message, previous_messages, and other data
            
        Returns:
            Updated state with general response
        """
        try:
            # Prepare messages for OpenAI
            messages = []
            
            # Add previous conversation context
            if state.get("previous_messages"):
                for msg in state["previous_messages"]:
                    messages.append({
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", "")
                    })
            
            # Add current user message
            messages.append({
                "role": "user",
                "content": state["user_message"]
            })
            
            # If no previous context, add a system message
            if not state.get("previous_messages"):
                messages.insert(0, {
                    "role": "system",
                    "content": "You are a helpful AI assistant. Respond to the user's query in a helpful and informative manner."
                })
            
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=1000,
                temperature=0.7
            )
            
            general_response = response.choices[0].message.content
            state["final_response"] = general_response
            
            logger.info(f"Generated general OpenAI response successfully")
            return state
            
        except Exception as e:
            logger.error(f"Error generating general response: {str(e)}")
            state["final_response"] = f"Sorry, I encountered an error while processing your request: {str(e)}"
            state["error"] = f"General response error: {str(e)}"
            return state 