"""Low-level client for Groq chat completions.

Strict boundaries:
  - Does NOT validate JSON schema with Pydantic.
  - Does NOT retry on validation failure.
  - Does NOT build prompts, truncate text, or access the database.
  - Never logs prompt content, resume text, or API secrets.
"""

import logging
import time
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
    def __init__(self, retry_after: str | None = None, is_daily_quota: bool = False):
        self.retry_after = retry_after
        self.is_daily_quota = is_daily_quota
        suffix = f" (retry-after: {retry_after}s)" if retry_after else ""
        quota_msg = "Daily AI quota exhausted" if is_daily_quota else "AI service temporarily rate-limited"
        super().__init__(f"{quota_msg}{suffix}")


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


def _execute_chat_completion(client: Groq, model: str, system_prompt: str, user_prompt: str, temperature: float):
    return client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        response_format=_RESPONSE_FORMAT,
        max_completion_tokens=MAX_OUTPUT_TOKENS,
        reasoning_effort="low",
    )


def call_groq(system_prompt: str, user_prompt: str) -> LLMResponse:
    settings = get_settings()
    client = _get_client()

    try:
        completion = _execute_chat_completion(
            client=client,
            model=settings.groq_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=settings.llm_temperature,
        )
    except RateLimitError as e:
        retry_after_str = e.response.headers.get("retry-after") if e.response is not None else None
        err_msg = str(e).lower()
        is_daily = any(term in err_msg for term in ["per day", "rpd", "tpd", "daily", "quota", "day limit"])

        # Avoid blind retries on daily quota exhaustion (Point 5)
        if is_daily:
            logger.warning("Groq daily quota exhausted; aborting without retry")
            raise LLMRateLimitError(retry_after=retry_after_str, is_daily_quota=True) from None

        # Parse retry delay for temporary TPM/RPM rate limits
        delay = None
        if retry_after_str:
            try:
                delay = float(retry_after_str)
            except ValueError:
                delay = None

        # If temporary and short wait (<= 5s), back off and retry ONCE (Point 1)
        if delay is not None and delay <= 5.0:
            logger.info("Temporary Groq 429 encountered; backing off for %.2fs before 1 retry", delay)
            time.sleep(delay)
            try:
                completion = _execute_chat_completion(
                    client=client,
                    model=settings.groq_model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=settings.llm_temperature,
                )
            except RateLimitError as retry_err:
                new_retry_after = (
                    retry_err.response.headers.get("retry-after")
                    if retry_err.response is not None
                    else retry_after_str
                )
                logger.warning("Groq retry also failed: rate_limited, retry_after=%s", new_retry_after)
                raise LLMRateLimitError(retry_after=new_retry_after, is_daily_quota=False) from None
        else:
            logger.warning("Groq rate limit exceeded (delay=%s, is_daily=%s)", retry_after_str, is_daily)
            raise LLMRateLimitError(retry_after=retry_after_str, is_daily_quota=False) from None
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
