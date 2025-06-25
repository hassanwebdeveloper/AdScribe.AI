"""
Text Classification Node for LangGraph AI Agent

This node classifies user queries into different categories based on provided class definitions.
"""

from typing import Dict, List, Any
import logging
from app.services.dynamic_prompt_service import dynamic_prompt_service

# Set up logging
logger = logging.getLogger(__name__)

class TextClassifierNode:
    """
    A dynamic text classifier node that can classify user queries based on provided class definitions.
    """
    
    def __init__(self, classification_classes: Dict[str, str]):
        """
        Initialize the text classifier with class definitions.
        
        Args:
            classification_classes: Dictionary mapping class names to their descriptions
                Example: {
                    "ad_script": "If user wants to write new ad speech or video script or text but not code",
                    "default": "it is default category all remaining query should lie under this category"
                }
        """
        self.classification_classes = classification_classes
        self.default_class = "default"
    
    async def classify_text(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify the user query based on the provided class definitions.
        
        Args:
            state: Agent state containing user_message and other data
            
        Returns:
            Updated state with classification result
        """
        try:
            # Build the classification prompt dynamically
            classes_description = ""
            for class_name, description in self.classification_classes.items():
                classes_description += f'{class_name}: {description}\n'
            
            # Prepare variables for the dynamic prompt
            prompt_variables = {
                "classes_description": classes_description,
                "default_class": self.default_class,
                "user_message": state["user_message"]
            }
            
            # Use dynamic prompt service for classification
            classification_result = await dynamic_prompt_service.make_chat_completion(
                prompt_key="text_classifier",
                prompt_variables=prompt_variables
            )
            
            if classification_result:
                classification = classification_result.strip().lower()
            else:
                classification = self.default_class
                logger.warning("Failed to get classification from dynamic prompt service, using default")
            
            # Ensure valid classification - if not in our classes, default to default_class
            if classification not in [cls.lower() for cls in self.classification_classes.keys()]:
                classification = self.default_class
                logger.warning(f"Invalid classification '{classification}', defaulting to '{self.default_class}'")
            
            logger.info(f"Classified user query '{state['user_message']}' as: {classification}")
            
            state["classification"] = classification
            return state
            
        except Exception as e:
            logger.error(f"Error in text classification: {str(e)}")
            state["classification"] = self.default_class  # Default on error
            state["error"] = f"Classification error: {str(e)}"
            return state 