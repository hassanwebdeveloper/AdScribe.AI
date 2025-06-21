import asyncio
import logging
import random
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from openai import OpenAI
from openai import RateLimitError, APITimeoutError, APIError
from app.core.config import settings
import openai

logger = logging.getLogger(__name__)

class OpenAIService:
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds
    RATE_LIMIT_DELAY = 5  # seconds
    REQUEST_DELAY = 0.5  # Delay between requests to respect rate limits
    
    # Global tracking of requests to help debug rate limits
    _request_times = []
    _request_count = 0
    
    def __init__(self):
        self.client = None
        self._initialize_client()
        self._last_request_time = 0  # Track last request time
        
        logger.info("Initializing OpenAIService with rate limiting")
    
    def _initialize_client(self):
        """Initialize OpenAI client with API key."""
        try:
            # Check for API key in settings (multiple possible names)
            api_key = None
            
            if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
                api_key = settings.OPENAI_API_KEY
            elif hasattr(settings, 'openai_api_key') and settings.openai_api_key:
                api_key = settings.openai_api_key
            
            if api_key:
                openai.api_key = api_key
                self.client = OpenAI(api_key=api_key)  # Use new OpenAI client
                logger.info("OpenAI client initialized successfully")
            else:
                logger.warning("OpenAI API key not found in settings")
        except Exception as e:
            logger.error(f"Error initializing OpenAI client: {str(e)}")
    
    def cleanup(self):
        """Clean up resources."""
        if self.client is not None:
            try:
                self.client.close()
                logger.debug("OpenAI client closed successfully")
            except Exception as e:
                logger.debug(f"Error closing OpenAI client: {e}")
            finally:
                self.client = None
    
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
            logger.warning(f"OpenAI API request rate: {requests_per_minute} requests in the last minute")
    
    async def _make_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        cancellation_token: Optional[Dict[str, bool]] = None
    ) -> Optional[str]:
        """
        Core method for making chat completions with retry logic and rate limiting.
        This is the method used throughout the existing codebase.
        
        Args:
            messages: List of message objects
            model: OpenAI model to use
            temperature: Creativity level (0-1)
            max_tokens: Maximum tokens in response
            cancellation_token: Optional cancellation token
        
        Returns:
            AI generated response or None if failed
        """
        if not self.client:
            logger.error("OpenAI client not initialized")
            return None
        
        # Check for cancellation
        if cancellation_token and cancellation_token.get("cancelled", False):
            logger.info("Request cancelled before making OpenAI call")
            return None
        
        # Track request rate
        self._track_request_rate()
        
        # Rate limiting - ensure we don't exceed request limits
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time
        
        if time_since_last_request < self.REQUEST_DELAY:
            delay = self.REQUEST_DELAY - time_since_last_request
            logger.debug(f"Rate limiting: waiting {delay:.2f} seconds")
            await asyncio.sleep(delay)
        
        self._last_request_time = time.time()
        
        for attempt in range(self.MAX_RETRIES):
            try:
                # Check for cancellation before each attempt
                if cancellation_token and cancellation_token.get("cancelled", False):
                    logger.info(f"Request cancelled during attempt {attempt + 1}")
                    return None
                
                logger.debug(f"Making OpenAI request (attempt {attempt + 1}/{self.MAX_RETRIES})")
                
                # Use the new OpenAI client
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        timeout=30
                    )
                )
                
                result = response.choices[0].message.content
                logger.debug(f"OpenAI request successful (attempt {attempt + 1})")
                
                return result.strip() if result else None
                
            except RateLimitError as e:
                logger.warning(f"Rate limit error (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RATE_LIMIT_DELAY * (2 ** attempt) + random.uniform(0, 1)
                    logger.info(f"Waiting {delay:.2f} seconds before retry...")
                    await asyncio.sleep(delay)
                else:
                    logger.error("Max retries exceeded for rate limit error")
                    raise ValueError("Rate limit exceeded after max retries")
                    
            except APITimeoutError as e:
                logger.warning(f"Timeout error (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_DELAY * (attempt + 1)
                    await asyncio.sleep(delay)
                else:
                    logger.error("Max retries exceeded for timeout error")
                    return None
                    
            except APIError as e:
                logger.error(f"OpenAI API error (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_DELAY * (attempt + 1)
                    await asyncio.sleep(delay)
                else:
                    logger.error("Max retries exceeded for API error")
                    return None
                    
            except Exception as e:
                logger.error(f"Unexpected error (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_DELAY * (attempt + 1)
                    await asyncio.sleep(delay)
                else:
                    logger.error("Max retries exceeded for unexpected error")
                    return None
        
        return None
    
    async def get_completion(
        self,
        prompt: str,
        model: str = "gpt-3.5-turbo",
        max_tokens: int = 1000,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Get completion from OpenAI API.
        
        Args:
            prompt: User prompt
            model: OpenAI model to use
            max_tokens: Maximum tokens in response
            temperature: Creativity level (0-1)
            system_prompt: Optional system prompt
        
        Returns:
            AI generated response
        """
        if not self.client:
            logger.error("OpenAI client not initialized")
            return "OpenAI service not available"
        
        try:
            messages = []
            
            if system_prompt:
                messages.append({
                    "role": "system", 
                    "content": system_prompt
                })
            
            messages.append({
                "role": "user",
                "content": prompt
            })
            
            # Use the existing _make_chat_completion method
            result = await self._make_chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            return result if result else "Error generating response"
            
        except Exception as e:
            logger.error(f"Error getting OpenAI completion: {str(e)}")
            return f"Error generating AI recommendation: {str(e)}"
    
    async def analyze_creative_performance(
        self,
        creative_data: Dict[str, Any],
        performance_data: Dict[str, Any],
        goal: str
    ) -> Dict[str, Any]:
        """
        Analyze creative performance and provide structured insights.
        
        Args:
            creative_data: Creative metadata
            performance_data: Performance metrics
            goal: Improvement goal
        
        Returns:
            Structured analysis with insights and recommendations
        """
        
        system_prompt = """
        You are an expert Facebook ads analyst specializing in creative performance optimization.
        Analyze the provided data and return insights in a structured format.
        Focus on actionable recommendations that can improve ad performance.
        """
        
        prompt = f"""
        Analyze this Facebook ad creative and performance data:

        Creative Elements:
        {self._format_creative_data(creative_data)}

        Performance Metrics:
        {self._format_performance_data(performance_data)}

        Goal: {goal}

        Provide analysis in this structure:
        1. Key Issues: What's limiting performance?
        2. Opportunities: What's working that can be leveraged?
        3. Specific Changes: Exact modifications to make
        4. Expected Impact: Quantified improvement expectations
        5. Implementation Priority: Order of changes to make

        Be specific and actionable.
        """
        
        try:
            response = await self.get_completion(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.6
            )
            
            return {
                "analysis": response,
                "confidence": 0.8,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in creative performance analysis: {str(e)}")
            return {
                "analysis": "Analysis unavailable",
                "confidence": 0.0,
                "error": str(e)
            }
    
    def _format_creative_data(self, creative_data: Dict[str, Any]) -> str:
        """Format creative data for AI prompt."""
        formatted = []
        
        for key, value in creative_data.items():
            if value is not None:
                if isinstance(value, list):
                    formatted.append(f"- {key.replace('_', ' ').title()}: {', '.join(value)}")
                else:
                    formatted.append(f"- {key.replace('_', ' ').title()}: {value}")
        
        return '\n'.join(formatted) if formatted else "No creative data available"
    
    def _format_performance_data(self, performance_data: Dict[str, Any]) -> str:
        """Format performance data for AI prompt."""
        formatted = []
        
        for key, value in performance_data.items():
            if value is not None and value != 0:
                if key in ['roas', 'ctr', 'conversion_rate']:
                    formatted.append(f"- {key.upper()}: {value:.3f}")
                elif key in ['cpc', 'cpm', 'spend', 'revenue']:
                    formatted.append(f"- {key.upper()}: ${value:.2f}")
                else:
                    formatted.append(f"- {key.upper()}: {value}")
        
        return '\n'.join(formatted) if formatted else "No performance data available"

# Global instance for use across nodes
openai_service = OpenAIService() 