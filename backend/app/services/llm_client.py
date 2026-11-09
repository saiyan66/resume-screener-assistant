"""Low-level client for Groq chat completions.

Strict boundaries:
  - Does NOT validate JSON schema with Pydantic.
  - Does NOT retry on validation failure.
  - Does NOT build prompts, truncate text, or access the database.
  - Never logs prompt content, resume text, or API secrets.
"""

import logging
from dataclasses import dataclass
from functools import lru_cache

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


MAX_OUTPUT_TOKENS = 2048

_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {"name": "MatchReport", "strict": True, "schema": provider_schema()},
}


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
    """Base class for all errors raised by this module."""


class LLMRateLimitError(LLMClientError):
    def __init__(self, retry_after: str | None = None):
        self.retry_after = retry_after
        suffix = f" (retry-after: {retry_after}s)" if retry_after else ""
        super().__init__(f"Groq rate limit exceeded{suffix}")


class LLMConnectionError(LLMClientError):
    """Network failure or timeout."""


class LLMAPIError(LLMClientError):
    def __init__(self, status_code: int | None = None, code: str | None = None):
        self.status_code = status_code
        self.code = code
        detail = f" [{code}]" if code else ""
        super().__init__(f"Groq API error (HTTP {status_code}){detail}")


class LLMEmptyResponseError(LLMClientError):
    """The reply had no usable content."""


class LLMOutputTruncatedError(LLMClientError):
    """The output hit the token cap; retrying with the same cap would fail again."""


@lru_cache(maxsize=1)
def _get_client() -> Groq:
    settings = get_settings()
    return Groq(
        api_key=settings.groq_api_key.get_secret_value(),  # the only place the key is unwrapped
        timeout=float(settings.llm_timeout_seconds),
        max_retries=0,  # the service layer owns retry policy; SDK retries would hide token cost
    )


def call_groq(system_prompt: str, user_prompt: str) -> LLMResponse:
    settings = get_settings()
    try:
        completion = _get_client().chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=settings.llm_temperature,
            response_format=_RESPONSE_FORMAT,
            max_completion_tokens=MAX_OUTPUT_TOKENS,
            reasoning_effort="low",
        )
    except RateLimitError as e:
        retry_after = e.response.headers.get("retry-after") if e.response is not None else None
        logger.warning("Groq call failed: rate_limited, retry_after=%s", retry_after)
        raise LLMRateLimitError(retry_after) from None
    except (APITimeoutError, APIConnectionError) as e:
        logger.warning("Groq call failed: connection, error_type=%s", type(e).__name__)
        raise LLMConnectionError("Connection to Groq timed out or failed") from None
    except APIStatusError as e:
        # Only a short error code is kept; response bodies may echo prompt text.
        code = getattr(e, "code", None)
        code = code if isinstance(code, str) and len(code) <= 64 else None
        logger.warning("Groq call failed: status=%s, code=%s", e.status_code, code)
        raise LLMAPIError(e.status_code, code) from None
    except GroqError as e:
        logger.warning("Groq call failed: sdk_error, error_type=%s", type(e).__name__)
        raise LLMAPIError() from None

    if not completion.choices:
        raise LLMEmptyResponseError("Groq returned no choices")
    choice = completion.choices[0]
    if choice.finish_reason == "length":
        logger.warning("Groq output truncated at max_completion_tokens=%d", MAX_OUTPUT_TOKENS)
        raise LLMOutputTruncatedError("Output hit the token cap before the JSON finished")

    text = (choice.message.content or "").strip()
    if not text:
        raise LLMEmptyResponseError("Groq returned blank content")

    u = completion.usage
    usage = (
        LLMTokenUsage(u.prompt_tokens or 0, u.completion_tokens or 0, u.total_tokens or 0)
        if u
        else LLMTokenUsage(0, 0, 0)
    )
    logger.info(
        "Groq call ok: model=%s, prompt_tokens=%d, completion_tokens=%d",
        settings.groq_model,
        usage.prompt_tokens,
        usage.completion_tokens,
    )
    return LLMResponse(text=text, usage=usage)
