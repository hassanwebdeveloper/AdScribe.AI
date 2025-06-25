from typing import Dict, Any, Optional, List
import logging

from app.services.prompt_template_service import PromptTemplateService
from app.services.openai_service import openai_service

logger = logging.getLogger(__name__)

class DynamicPromptService:
    """Service for getting dynamic prompts and making AI calls with them"""
    
    def __init__(self):
        # Use the global openai_service instance instead of creating our own client
        self.openai_service = openai_service
    
    async def get_prompt_and_settings(self, prompt_key: str) -> tuple[Optional[str], str, float, Optional[int]]:
        """
        Get prompt text and settings for a given prompt key.
        
        Returns:
            tuple: (prompt_text, model, temperature, max_tokens)
        """
        template = await PromptTemplateService.get_prompt_template(prompt_key)
        if template:
            return template.prompt_text, template.model, template.temperature, template.max_tokens
        else:
            logger.warning(f"Prompt template '{prompt_key}' not found, using defaults")
            return None, "gpt-4o", 0.4, None
    
    async def format_prompt(self, prompt_key: str, **kwargs) -> Optional[str]:
        """
        Format a prompt template with the given variables.
        
        Args:
            prompt_key: The key of the prompt template
            **kwargs: Variables to format the prompt with
            
        Returns:
            Formatted prompt text or None if template not found
        """
        prompt_text, _, _, _ = await self.get_prompt_and_settings(prompt_key)
        if prompt_text:
            try:
                return prompt_text.format(**kwargs)
            except KeyError as e:
                logger.error(f"Missing variable {e} for prompt '{prompt_key}'")
                return None
        return None
    
    async def make_chat_completion(
        self,
        prompt_key: str,
        messages: Optional[List[Dict[str, Any]]] = None,
        prompt_variables: Optional[Dict[str, Any]] = None,
        cancellation_token: Optional[Dict[str, bool]] = None,
        **override_settings
    ) -> Optional[str]:
        """
        Make a chat completion using dynamic prompt settings.
        
        Args:
            prompt_key: The key of the prompt template to use
            messages: List of messages (if None, will create from prompt)
            prompt_variables: Variables to format the prompt with
            cancellation_token: Optional cancellation token to check for job cancellation
            **override_settings: Override model settings (model, temperature, max_tokens)
            
        Returns:
            Response content or None if failed
        """
        try:
            # Get prompt and settings
            prompt_text, model, temperature, max_tokens = await self.get_prompt_and_settings(prompt_key)
            
            if not prompt_text:
                logger.error(f"No prompt found for key '{prompt_key}'")
                return None
            
            # Apply overrides
            model = override_settings.get('model', model)
            temperature = override_settings.get('temperature', temperature)
            max_tokens = override_settings.get('max_tokens', max_tokens)
            
            # Prepare messages
            if messages is None:
                # Format prompt if variables provided
                if prompt_variables:
                    formatted_prompt = prompt_text.format(**prompt_variables)
                else:
                    formatted_prompt = prompt_text
                
                messages = [{"role": "user", "content": formatted_prompt}]
            
            # Use the openai_service with rate limiting and error handling
            return await self.openai_service._make_chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                cancellation_token=cancellation_token
            )
            
        except Exception as e:
            logger.error(f"Error in dynamic chat completion for '{prompt_key}': {e}")
            return None
    
    async def make_chat_completion_with_context(
        self,
        prompt_key: str,
        user_message: str,
        previous_messages: Optional[List[Dict[str, Any]]] = None,
        system_prompt_variables: Optional[Dict[str, Any]] = None,
        cancellation_token: Optional[Dict[str, bool]] = None,
        **override_settings
    ) -> Optional[str]:
        """
        Make a chat completion with conversation context and dynamic system prompt.
        
        Args:
            prompt_key: The key of the prompt template to use as system prompt
            user_message: Current user message
            previous_messages: Previous conversation messages
            system_prompt_variables: Variables to format the system prompt with
            cancellation_token: Optional cancellation token to check for job cancellation
            **override_settings: Override model settings
            
        Returns:
            Response content or None if failed
        """
        try:
            # Get system prompt and settings
            system_prompt_text, model, temperature, max_tokens = await self.get_prompt_and_settings(prompt_key)
            
            if not system_prompt_text:
                logger.error(f"No system prompt found for key '{prompt_key}'")
                return None
            
            # Apply overrides
            model = override_settings.get('model', model)
            temperature = override_settings.get('temperature', temperature)
            max_tokens = override_settings.get('max_tokens', max_tokens)
            
            # Format system prompt if variables provided
            if system_prompt_variables:
                formatted_system_prompt = system_prompt_text.format(**system_prompt_variables)
            else:
                formatted_system_prompt = system_prompt_text
            
            # Build messages
            messages = []
            
            # Add system message
            messages.append({
                "role": "system",
                "content": formatted_system_prompt
            })
            
            # Add previous conversation context
            if previous_messages:
                for msg in previous_messages:
                    # Map 'bot' role to 'assistant' for OpenAI API compatibility
                    role = msg.get("role", "user")
                    if role == "bot":
                        role = "assistant"
                    
                    messages.append({
                        "role": role,
                        "content": msg.get("content", "")
                    })
            
            # Add current user message
            messages.append({
                "role": "user",
                "content": user_message
            })
            
            # Use the openai_service with rate limiting and error handling
            return await self.openai_service._make_chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                cancellation_token=cancellation_token
            )
            
        except Exception as e:
            logger.error(f"Error in dynamic chat completion with context for '{prompt_key}': {e}")
            return None

# Global instance for use across nodes
dynamic_prompt_service = DynamicPromptService() 