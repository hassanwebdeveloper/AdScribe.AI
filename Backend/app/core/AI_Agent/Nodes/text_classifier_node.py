"""
Text Classification Node for LangGraph AI Agent

This node classifies user queries into different categories based on provided class definitions.
"""

from typing import Dict, List, Any
from openai import AsyncOpenAI
import logging
from app.core.config import settings

# Set up logging
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = AsyncOpenAI(api_key=settings.openai_api_key)

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
            
            classification_prompt = f"""
            You are a text classifier that determines the intent of user queries.
            
            Classes:
            {classes_description}
            
            Classification Guidelines:
            - Analyze the user query carefully and determine which category it best fits into
            - If the query doesn't clearly fit into any specific category, classify it as "{self.default_class}"
            - Only respond with the exact class name from the list above
            
            User Query: "{state["user_message"]}"
            
            Respond with only the classification (class name):
            """
            
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": classification_prompt
                    }
                ],
                max_tokens=20,
                temperature=0
            )
            
            classification = response.choices[0].message.content.strip().lower()
            
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