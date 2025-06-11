"""
General Response Node for LangGraph AI Agent

This node handles general queries and default responses using OpenAI.
"""

from typing import Dict, List, Any
import logging
from app.services.dynamic_prompt_service import dynamic_prompt_service

# Set up logging
logger = logging.getLogger(__name__)

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
            # Use dynamic prompt service for general response
            general_response = await dynamic_prompt_service.make_chat_completion_with_context(
                prompt_key="general_response",
                user_message=state["user_message"],
                previous_messages=state.get("previous_messages")
            )
            
            if general_response:
                state["final_response"] = general_response
            else:
                state["final_response"] = "Sorry, I encountered an error while processing your request."
                state["error"] = "Failed to generate general response using dynamic prompt service"
            
            logger.info(f"Generated general OpenAI response successfully")
            return state
            
        except Exception as e:
            logger.error(f"Error generating general response: {str(e)}")
            state["final_response"] = f"Sorry, I encountered an error while processing your request: {str(e)}"
            state["error"] = f"General response error: {str(e)}"
            return state 