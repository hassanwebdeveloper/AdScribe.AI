import asyncio
import logging
import random
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from openai import OpenAI
from openai import RateLimitError, APITimeoutError, APIError
from app.core.config import settings

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
        self._client = None
        self._last_request_time = 0  # Track last request time
        
        logger.info("Initializing OpenAIService with rate limiting")
    
    @property
    def client(self):
        """Get or create OpenAI client."""
        if self._client is None:
            self._client = OpenAI(api_key=settings.openai_api_key)
        return self._client
    
    def cleanup(self):
        """Clean up resources."""
        if self._client is not None:
            try:
                self._client.close()
                logger.debug("OpenAI client closed successfully")
            except Exception as e:
                logger.debug(f"Error closing OpenAI client: {e}")
            finally:
                self._client = None
    
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
        model: str = "gpt-4o",
        temperature: float = 0.4,
        max_tokens: Optional[int] = None,
        retry_count: int = 0,
        cancellation_token: Optional[Dict[str, bool]] = None
    ) -> Optional[str]:
        """
        Make a chat completion request with proper error handling and rate limiting.
        
        Args:
            messages: List of message dictionaries
            model: OpenAI model to use
            temperature: Temperature for response generation
            max_tokens: Maximum tokens for response
            retry_count: Current retry attempt (internal use)
            cancellation_token: Optional cancellation token to check for job cancellation
        
        Returns:
            Response content or None if failed
        """
        # Check for cancellation before making request
        if cancellation_token and cancellation_token.get("cancelled", False):
            logger.info("OpenAI chat completion request cancelled before execution")
            raise ValueError("Request cancelled")
        
        try:
            # Increment and track global request count
            self.__class__._request_count += 1
            self._track_request_rate()
            
            # Wait for rate limit before making the request
            now = time.time()
            if hasattr(self, '_last_request_time'):
                time_since_last = now - self._last_request_time
                if time_since_last < self.REQUEST_DELAY:
                    wait_time = self.REQUEST_DELAY - time_since_last
                    logger.debug(f"Rate limiting: waiting {wait_time:.2f} seconds before OpenAI request")
                    await asyncio.sleep(wait_time)
            
            # Check for cancellation after rate limit wait
            if cancellation_token and cancellation_token.get("cancelled", False):
                logger.info("OpenAI chat completion request cancelled after rate limit wait")
                raise ValueError("Request cancelled")
            
            self._last_request_time = time.time()
            
            # Log the request details
            logger.debug(f"Making OpenAI chat completion request with model {model}")
            request_start = time.time()
            
            # Prepare request parameters
            request_params = {
                "model": model,
                "messages": messages,
                "temperature": temperature
            }
            if max_tokens:
                request_params["max_tokens"] = max_tokens
            
            # Make the API call in thread pool to prevent blocking the event loop
            def _make_chat_request():
                """Make chat completion in thread pool to avoid blocking event loop."""
                return self.client.chat.completions.create(**request_params)
            
            # Run API call in thread pool to prevent blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, _make_chat_request)
            
            # Check for cancellation after receiving response
            if cancellation_token and cancellation_token.get("cancelled", False):
                logger.info("OpenAI chat completion request cancelled after receiving response")
                raise ValueError("Request cancelled")
            
            # Log response time
            request_time = time.time() - request_start
            logger.debug(f"OpenAI response received in {request_time:.2f}s")
            
            return response.choices[0].message.content
            
        except ValueError as e:
            # Don't retry for cancellation errors
            if "cancelled" in str(e).lower():
                raise e
            # Re-raise other ValueError exceptions
            raise e
        except RateLimitError as e:
            if retry_count < self.MAX_RETRIES:
                # Exponential backoff with jitter for rate limits
                delay = (self.RATE_LIMIT_DELAY * (2 ** retry_count)) + random.uniform(0, 2)
                logger.warning(f"OpenAI rate limit hit, retrying in {delay:.2f} seconds... (Attempt {retry_count + 1}/{self.MAX_RETRIES})")
                await asyncio.sleep(delay)
                return await self._make_chat_completion(messages, model, temperature, max_tokens, retry_count + 1, cancellation_token)
            else:
                error_msg = f"Max retries reached for OpenAI rate limit: {str(e)}"
                logger.error(error_msg)
                raise ValueError(error_msg)
        except APITimeoutError as e:
            # Check if timeout was due to cancellation
            if cancellation_token and cancellation_token.get("cancelled", False):
                logger.info("OpenAI request timeout - job was cancelled")
                raise ValueError("Request cancelled")
            
            if retry_count < self.MAX_RETRIES:
                # Use a longer delay for timeouts
                delay = (self.RETRY_DELAY * 2 * (2 ** retry_count)) + random.uniform(1, 3)
                logger.warning(f"OpenAI request timeout, retrying in {delay:.2f} seconds... (Attempt {retry_count + 1}/{self.MAX_RETRIES})")
                await asyncio.sleep(delay)
                return await self._make_chat_completion(messages, model, temperature, max_tokens, retry_count + 1, cancellation_token)
            else:
                error_msg = f"Max retries reached after OpenAI timeouts: {str(e)}"
                logger.error(error_msg)
                raise ValueError(error_msg)
        except APIError as e:
            error_msg = f"OpenAI API error: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error in OpenAI request: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    async def _make_transcription(
        self,
        audio_file_path: str,
        model: str = "whisper-1",
        language: str = "ur",
        prompt: Optional[str] = None,
        retry_count: int = 0,
        cancellation_token: Optional[Dict[str, bool]] = None
    ) -> Optional[str]:
        """
        Make a transcription request with proper error handling and rate limiting.
        
        Args:
            audio_file_path: Path to the audio file
            model: Whisper model to use
            language: Language code for transcription
            prompt: Optional prompt for better transcription
            retry_count: Current retry attempt (internal use)
            cancellation_token: Optional cancellation token to check for job cancellation
        
        Returns:
            Transcription text or None if failed
        """
        # Check for cancellation before making request
        if cancellation_token and cancellation_token.get("cancelled", False):
            logger.info("OpenAI transcription request cancelled before execution")
            raise ValueError("Request cancelled")
        
        try:
            # Increment and track global request count
            self.__class__._request_count += 1
            self._track_request_rate()
            
            # Wait for rate limit before making the request
            now = time.time()
            if hasattr(self, '_last_request_time'):
                time_since_last = now - self._last_request_time
                if time_since_last < self.REQUEST_DELAY:
                    wait_time = self.REQUEST_DELAY - time_since_last
                    logger.debug(f"Rate limiting: waiting {wait_time:.2f} seconds before OpenAI transcription")
                    await asyncio.sleep(wait_time)
            
            # Check for cancellation after rate limit wait
            if cancellation_token and cancellation_token.get("cancelled", False):
                logger.info("OpenAI transcription request cancelled after rate limit wait")
                raise ValueError("Request cancelled")
            
            self._last_request_time = time.time()
            
            # Log the request details
            logger.debug(f"Making OpenAI transcription request for file: {audio_file_path}")
            request_start = time.time()
            
            # Prepare request parameters
            request_params = {
                "model": model,
                "language": language
            }
            if prompt:
                request_params["prompt"] = prompt
            
            # Make the API call with non-blocking file I/O to prevent server hanging
            def _read_and_transcribe():
                """Read file and make transcription in thread pool to avoid blocking event loop."""
                with open(audio_file_path, "rb") as audio_file:
                    return self.client.audio.transcriptions.create(
                        file=audio_file,
                        **request_params
                    )
            
            # Run file I/O and API call in thread pool to prevent blocking the event loop
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, _read_and_transcribe)
            
            # Check for cancellation after receiving response
            if cancellation_token and cancellation_token.get("cancelled", False):
                logger.info("OpenAI transcription request cancelled after receiving response")
                raise ValueError("Request cancelled")
            
            # Log response time
            request_time = time.time() - request_start
            logger.debug(f"OpenAI transcription response received in {request_time:.2f}s")
            
            return response.text.strip()
            
        except ValueError as e:
            # Don't retry for cancellation errors
            if "cancelled" in str(e).lower():
                raise e
            # Re-raise other ValueError exceptions
            raise e
        except RateLimitError as e:
            if retry_count < self.MAX_RETRIES:
                # Exponential backoff with jitter for rate limits
                delay = (self.RATE_LIMIT_DELAY * (2 ** retry_count)) + random.uniform(0, 2)
                logger.warning(f"OpenAI transcription rate limit hit, retrying in {delay:.2f} seconds... (Attempt {retry_count + 1}/{self.MAX_RETRIES})")
                await asyncio.sleep(delay)
                return await self._make_transcription(audio_file_path, model, language, prompt, retry_count + 1, cancellation_token)
            else:
                error_msg = f"Max retries reached for OpenAI transcription rate limit: {str(e)}"
                logger.error(error_msg)
                raise ValueError(error_msg)
        except APITimeoutError as e:
            # Check if timeout was due to cancellation
            if cancellation_token and cancellation_token.get("cancelled", False):
                logger.info("OpenAI transcription timeout - job was cancelled")
                raise ValueError("Request cancelled")
            
            if retry_count < self.MAX_RETRIES:
                # Use a longer delay for timeouts
                delay = (self.RETRY_DELAY * 2 * (2 ** retry_count)) + random.uniform(1, 3)
                logger.warning(f"OpenAI transcription timeout, retrying in {delay:.2f} seconds... (Attempt {retry_count + 1}/{self.MAX_RETRIES})")
                await asyncio.sleep(delay)
                return await self._make_transcription(audio_file_path, model, language, prompt, retry_count + 1, cancellation_token)
            else:
                error_msg = f"Max retries reached after OpenAI transcription timeouts: {str(e)}"
                logger.error(error_msg)
                raise ValueError(error_msg)
        except APIError as e:
            error_msg = f"OpenAI transcription API error: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error in OpenAI transcription: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

# Global instance for use across nodes
openai_service = OpenAIService() 