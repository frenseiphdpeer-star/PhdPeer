"""LLM Client wrapper for Groq API."""
import json
import logging
import re
import time
from typing import Any, Dict, Optional

from groq import Groq
from groq import APITimeoutError, APIConnectionError, RateLimitError, APIStatusError

from app.config import settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base exception for LLM-related errors."""
    pass


class LLMParseError(LLMError):
    """Raised when response cannot be parsed as JSON."""
    pass


class LLMTimeoutError(LLMError):
    """Raised when LLM request times out."""
    pass


class LLMRateLimitError(LLMError):
    """Raised when rate limit is exceeded."""
    pass


class LLMClient:
    """
    Wrapper around the Groq Python SDK.

    Provides:
    - API key loading from settings
    - call() method returning parsed JSON
    - Retry logic with exponential backoff (3 retries)
    - Markdown fence stripping before JSON parsing
    - Timeout handling
    """

    # Retry configuration
    MAX_RETRIES = 3
    BASE_DELAY = 1.0  # seconds
    MAX_DELAY = 30.0  # seconds

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None
    ):
        """
        Initialize the LLM client.

        Args:
            api_key: Groq API key (defaults to settings.LLM_API_KEY)
            model: Model to use (defaults to settings.LLM_MODEL)
            temperature: Temperature setting (defaults to settings.LLM_TEMPERATURE)
            max_tokens: Max tokens for response (defaults to settings.LLM_MAX_TOKENS)
            timeout: Request timeout in seconds (defaults to settings.LLM_TIMEOUT_SECONDS)
        """
        self.api_key = api_key or settings.LLM_API_KEY
        self.model = model or settings.LLM_MODEL
        self.temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
        self.default_max_tokens = max_tokens or settings.LLM_MAX_TOKENS
        self.timeout = timeout or settings.LLM_TIMEOUT_SECONDS

        if settings.LLM_PROVIDER.lower() != "groq":
            raise LLMError(
                f"Unsupported LLM_PROVIDER '{settings.LLM_PROVIDER}'. Expected 'groq'."
            )

        if not self.api_key:
            raise LLMError(
                "No API key provided. Set LLM_API_KEY in environment or pass api_key parameter."
            )

        # Initialize Groq client
        self.client = Groq(
            api_key=self.api_key,
            timeout=float(self.timeout)
        )

        logger.info(f"LLMClient initialized with model={self.model}, temperature={self.temperature}")

    def call(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Call the LLM and return parsed JSON response.

        Args:
            system_prompt: System prompt to set context
            user_prompt: User prompt with the request
            max_tokens: Max tokens for this call (defaults to self.default_max_tokens)

        Returns:
            Parsed JSON response as a dictionary

        Raises:
            LLMParseError: If response cannot be parsed as JSON
            LLMTimeoutError: If request times out after all retries
            LLMRateLimitError: If rate limit exceeded after all retries
            LLMError: For other API errors after all retries
        """
        max_tokens = max_tokens or self.default_max_tokens

        last_exception: Optional[Exception] = None

        for attempt in range(self.MAX_RETRIES):
            try:
                response = self._make_request(system_prompt, user_prompt, max_tokens)
                return self._parse_response(response)

            except APITimeoutError as e:
                last_exception = e
                logger.warning(
                    f"Timeout on attempt {attempt + 1}/{self.MAX_RETRIES}: {e}"
                )
                self._wait_before_retry(attempt)

            except RateLimitError as e:
                last_exception = e
                logger.warning(
                    f"Rate limit on attempt {attempt + 1}/{self.MAX_RETRIES}: {e}"
                )
                # Use longer delay for rate limits
                self._wait_before_retry(attempt, multiplier=2.0)

            except APIConnectionError as e:
                last_exception = e
                logger.warning(
                    f"Connection error on attempt {attempt + 1}/{self.MAX_RETRIES}: {e}"
                )
                self._wait_before_retry(attempt)

            except APIStatusError as e:
                # Don't retry on 4xx errors (except 429 which is RateLimitError)
                if 400 <= e.status_code < 500:
                    logger.error(f"Client error (non-retryable): {e}")
                    raise LLMError(f"API client error: {e}") from e

                last_exception = e
                logger.warning(
                    f"API error on attempt {attempt + 1}/{self.MAX_RETRIES}: {e}"
                )
                self._wait_before_retry(attempt)

            except LLMParseError:
                # Don't retry parse errors - the response won't change
                raise

        # All retries exhausted
        if isinstance(last_exception, APITimeoutError):
            raise LLMTimeoutError(
                f"Request timed out after {self.MAX_RETRIES} attempts"
            ) from last_exception
        elif isinstance(last_exception, RateLimitError):
            raise LLMRateLimitError(
                f"Rate limit exceeded after {self.MAX_RETRIES} attempts"
            ) from last_exception
        else:
            raise LLMError(
                f"LLM request failed after {self.MAX_RETRIES} attempts: {last_exception}"
            ) from last_exception

    def _make_request(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int
    ) -> str:
        """
        Make a request to the Groq API.

        Returns:
            Raw text response from the model
        """
        logger.debug(f"Making LLM request: model={self.model}, max_tokens={max_tokens}")

        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=self.temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        # Extract text from response
        if not response.choices:
            raise LLMError("Empty response from LLM")

        text_content = response.choices[0].message.content

        if text_content is None:
            raise LLMError("No text content in LLM response")

        logger.debug(f"LLM response received: {len(text_content)} chars")
        return text_content

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """
        Parse LLM response as JSON.

        Strips markdown code fences before parsing.

        Args:
            response: Raw response text from LLM

        Returns:
            Parsed JSON as dictionary

        Raises:
            LLMParseError: If response cannot be parsed as JSON
        """
        # Strip markdown code fences
        cleaned = self._strip_markdown_fences(response)

        try:
            result = json.loads(cleaned)
            if not isinstance(result, dict):
                raise LLMParseError(
                    f"Expected JSON object, got {type(result).__name__}"
                )
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Raw response: {response[:500]}...")
            raise LLMParseError(
                f"Failed to parse LLM response as JSON: {e}"
            ) from e

    def _strip_markdown_fences(self, text: str) -> str:
        """
        Strip markdown code fences from text.

        Handles:
        - ```json ... ```
        - ``` ... ```
        - Leading/trailing whitespace

        Args:
            text: Text potentially containing markdown fences

        Returns:
            Cleaned text with fences removed
        """
        text = text.strip()

        # Pattern to match code blocks: ```json or ``` at start and ``` at end
        # Captures the content between the fences
        pattern = r'^```(?:json)?\s*\n?(.*?)\n?```$'
        match = re.match(pattern, text, re.DOTALL)

        if match:
            return match.group(1).strip()

        # Also handle case where there's no newline after opening fence
        pattern_inline = r'^```(?:json)?\s*(.*?)\s*```$'
        match = re.match(pattern_inline, text, re.DOTALL)

        if match:
            return match.group(1).strip()

        return text

    def _wait_before_retry(self, attempt: int, multiplier: float = 1.0) -> None:
        """
        Wait with exponential backoff before retry.

        Args:
            attempt: Current attempt number (0-indexed)
            multiplier: Multiplier for the delay (e.g., 2.0 for rate limits)
        """
        delay = min(
            self.BASE_DELAY * (2 ** attempt) * multiplier,
            self.MAX_DELAY
        )
        logger.debug(f"Waiting {delay:.1f}s before retry")
        time.sleep(delay)

    def call_raw(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Call the LLM and return raw text response (no JSON parsing).

        Useful for non-JSON responses or debugging.

        Args:
            system_prompt: System prompt to set context
            user_prompt: User prompt with the request
            max_tokens: Max tokens for this call

        Returns:
            Raw text response from the model
        """
        max_tokens = max_tokens or self.default_max_tokens

        last_exception: Optional[Exception] = None

        for attempt in range(self.MAX_RETRIES):
            try:
                return self._make_request_raw(system_prompt, user_prompt, max_tokens)

            except (APITimeoutError, RateLimitError, APIConnectionError) as e:
                last_exception = e
                logger.warning(
                    f"Error on attempt {attempt + 1}/{self.MAX_RETRIES}: {e}"
                )
                multiplier = 2.0 if isinstance(e, RateLimitError) else 1.0
                self._wait_before_retry(attempt, multiplier)

            except APIStatusError as e:
                if 400 <= e.status_code < 500:
                    raise LLMError(f"API client error: {e}") from e
                last_exception = e
                self._wait_before_retry(attempt)

        raise LLMError(
            f"LLM request failed after {self.MAX_RETRIES} attempts: {last_exception}"
        ) from last_exception

    def _make_request_raw(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int
    ) -> str:
        """
        Make a request to the Groq API without JSON mode.

        Returns:
            Raw text response from the model
        """
        logger.debug(f"Making raw LLM request: model={self.model}, max_tokens={max_tokens}")

        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        if not response.choices:
            raise LLMError("Empty response from LLM")

        text_content = response.choices[0].message.content

        if text_content is None:
            raise LLMError("No text content in LLM response")

        logger.debug(f"LLM response received: {len(text_content)} chars")
        return text_content


# Singleton instance (lazy initialization)
_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """
    Get the singleton LLM client instance.

    Returns:
        LLMClient instance

    Raises:
        LLMError: If client cannot be initialized
    """
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
