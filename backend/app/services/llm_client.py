"""Low-level client for Groq chat completions.

Strict boundaries:
  - Does NOT validate JSON schema with Pydantic.
  - Does NOT retry on validation failure.
  - Does NOT build prompts, truncate text, or access the database.
  - Never logs prompt content, resume text, or API secrets.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from groq import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    Groq,
    GroqError,
    RateLimitError,
)

from app.core.config import get_settings
from app.schemas.analysis import provider_schema

logger = logging.getLogger(__name__)




@dataclass(frozen=True)
class LLMTokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class LLMResponse:
    text: str
    usage: LLMTokenUsage



class LLMClientError(Exception):
    """Base exception for all low-level LLM client errors."""


class LLMRateLimitError(LLMClientError):
    """Raised when Groq returns an HTTP 429 rate limit error."""

    def __init__(self, retry_after: Optional[str] = None):
        self.retry_after = retry_after
        msg = (
            f"Groq rate limit exceeded (retry-after: {retry_after}s)"
            if retry_after
            else "Groq rate limit exceeded"
        )
        super().__init__(msg)


class LLMConnectionError(LLMClientError):
    """Raised on network connection errors or request timeouts."""


class LLMAPIError(LLMClientError):
    """Raised when Groq returns a non-200 HTTP response or server error."""

    def __init__(self, status_code: Optional[int] = None, message: str = "Groq API error"):
        self.status_code = status_code
        full_msg = f"Groq API error ({status_code}): {message}" if status_code else message
        super().__init__(full_msg)


class LLMEmptyResponseError(LLMClientError):
    """Raised when Groq returns a response with missing or empty message content."""





def call_groq(system_prompt: str, user_prompt: str) -> LLMResponse:
    """
    Send system and user prompts to Groq and return raw response text and usage.

    Raises:
        LLMRateLimitError: When Groq returns a 429.
        LLMConnectionError: On timeout or connection failure.
        LLMAPIError: On unexpected HTTP or API errors.
        LLMEmptyResponseError: When response text is absent or empty.
    """
    settings = get_settings()

    # Secret unwrapped strictly at the boundary of client construction
    client = Groq(
        api_key=settings.groq_api_key.get_secret_value(),
        timeout=float(settings.llm_timeout_seconds),
    )

    schema = provider_schema()

    try:
        completion = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=settings.llm_temperature,
            stream=False,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "MatchReport",
                    "schema": schema,
                    "strict": True,
                },
            },
            max_completion_tokens=2048,
            reasoning_effort="low",
        )
    except RateLimitError as e:
        retry_after: Optional[str] = None
        if e.response is not None and hasattr(e.response, "headers"):
            retry_after = e.response.headers.get("retry-after")
        logger.warning(
            "Groq call failed: rate_limited, model=%s, retry_after=%s",
            settings.groq_model,
            retry_after,
        )
        raise LLMRateLimitError(retry_after=retry_after) from None

    except (APITimeoutError, APIConnectionError) as e:
        logger.warning(
            "Groq call failed: connection_error, model=%s, error_type=%s",
            settings.groq_model,
            type(e).__name__,
        )
        raise LLMConnectionError("Connection to Groq timed out or failed") from None

    except APIStatusError as e:
        logger.warning(
            "Groq call failed: status_error, model=%s, status_code=%s",
            settings.groq_model,
            e.status_code,
        )
        # Never forward raw provider response bodies as they may echo prompt fragments
        raise LLMAPIError(
            status_code=e.status_code,
            message=f"HTTP {e.status_code} from Groq API",
        ) from None

    except GroqError as e:
        logger.warning(
            "Groq call failed: general_error, model=%s, error_type=%s",
            settings.groq_model,
            type(e).__name__,
        )
        raise LLMAPIError(message=f"Groq SDK error: {type(e).__name__}") from None

    # Inspect choices and extract content
    if not completion.choices or completion.choices[0].message.content is None:
        logger.warning("Groq call failed: empty_content, model=%s", settings.groq_model)
        raise LLMEmptyResponseError("Groq returned an empty response with no content")

    raw_text = completion.choices[0].message.content.strip()
    if not raw_text:
        logger.warning("Groq call failed: blank_content, model=%s", settings.groq_model)
        raise LLMEmptyResponseError("Groq returned blank content")

 
    usage_info = completion.usage
    if usage_info is not None:
        usage = LLMTokenUsage(
            prompt_tokens=usage_info.prompt_tokens or 0,
            completion_tokens=usage_info.completion_tokens or 0,
            total_tokens=usage_info.total_tokens or 0,
        )
    else:
        usage = LLMTokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)


    logger.info(
        "Groq call succeeded: status=200, model=%s, prompt_tokens=%d, completion_tokens=%d, total_tokens=%d",
        settings.groq_model,
        usage.prompt_tokens,
        usage.completion_tokens,
        usage.total_tokens,
    )

    return LLMResponse(text=raw_text, usage=usage)

