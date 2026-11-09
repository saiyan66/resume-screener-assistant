"""Business logic for resume screening.

Orchestrates:
  1. Input truncation to max_input_chars_per_doc with truncation tracking.
  2. Prompt generation via app.prompts.screener.
  3. LLM invocation via app.services.llm_client.
  4. Response validation against app.schemas.analysis.MatchReport.
  5. Self-correcting retry loop (up to settings.llm_max_retries) on validation errors.
  6. Persistence of successful analyses to the SQLite database.
"""

import logging
from typing import Tuple

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.analysis import Analysis
from app.prompts.screener import SYSTEM_PROMPT, build_retry_prompt, build_user_prompt
from app.schemas.analysis import AnalysisCreate, MatchReport
from app.services.llm_client import call_groq

logger = logging.getLogger(__name__)



class AnalysisServiceError(Exception):
    """Base exception for analysis service errors."""


class AnalysisValidationError(AnalysisServiceError):
    """Raised when the LLM output fails schema validation after all retry attempts."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__(f"LLM output failed schema validation: {'; '.join(problems)}")




def _truncate_text(text: str, max_chars: int) -> Tuple[str, bool]:
    """Truncate text if it exceeds max_chars; return (truncated_text, was_truncated)."""
    if len(text) > max_chars:
        return text[:max_chars], True
    return text, False


def _extract_validation_problems(err: ValidationError) -> list[str]:
    """Extract readable location and error messages from Pydantic ValidationError."""
    problems = []
    for error in err.errors():
        loc = ".".join(str(item) for item in error.get("loc", []))
        msg = error.get("msg", "invalid value")
        problems.append(f"{loc}: {msg}" if loc else msg)
    return problems




def screen_candidate(
    payload: AnalysisCreate,
    db: Session,
) -> Tuple[Analysis, bool]:
    """
    Execute the resume screening pipeline:
      - Truncates input documents to respect token budgets.
      - Calls Groq with structured JSON output.
      - Validates output with MatchReport; retries with error feedback if invalid.
      - Saves the record into the database.

    Returns:
      Tuple[Analysis, bool]: The persisted ORM instance and a flag indicating if truncation occurred.

    Raises:
      AnalysisValidationError: If LLM output fails schema validation across all retries.
      LLMClientError: On network, rate-limit, timeout, or provider failure.
    """
    settings = get_settings()
    max_chars = settings.max_input_chars_per_doc

    # 1. Truncate inputs and track if either was truncated
    truncated_jd, jd_truncated = _truncate_text(payload.job_description, max_chars)
    truncated_resume, resume_truncated = _truncate_text(payload.resume_text, max_chars)
    was_truncated = jd_truncated or resume_truncated

    if was_truncated:
        logger.info(
            "Input truncated: jd_truncated=%s, resume_truncated=%s (limit=%d chars)",
            jd_truncated,
            resume_truncated,
            max_chars,
        )

    # 2. Build initial user prompt
    user_prompt = build_user_prompt(truncated_jd, truncated_resume)

    max_retries = settings.llm_max_retries
    attempts = 0
    report: MatchReport | None = None
    last_problems: list[str] = []

    # 3. LLM call & self-correcting validation loop
    while attempts <= max_retries:
        attempts += 1
        response = call_groq(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)

        try:
            report = MatchReport.model_validate_json(response.text)
            break
        except ValidationError as val_err:
            last_problems = _extract_validation_problems(val_err)
            logger.warning(
                "LLM output validation failed (attempt %d/%d): %s",
                attempts,
                max_retries + 1,
                last_problems,
            )

            if attempts <= max_retries:
                # Prepare self-correcting retry prompt passing the error details
                user_prompt = build_retry_prompt(user_prompt, last_problems)
            else:
                raise AnalysisValidationError(last_problems) from val_err

    if report is None:
        raise AnalysisValidationError(last_problems)

    # 4. Resolve candidate name (explicit HR override > LLM-extracted name > "Candidate")
    candidate_name = (
        payload.candidate_name.strip()
        or (report.candidate_name.strip() if report.candidate_name else "")
        or "Candidate"
    )

    # 5. Persist to database (candidate_name, job_title, JD snapshot, score, and JSON report)
    # Notice: resume_text is intentionally omitted from the database to preserve privacy.
    analysis_row = Analysis(
        candidate_name=candidate_name,
        job_title=payload.job_title.strip(),
        job_description=truncated_jd,
        match_score=report.match_score,
        report=report.model_dump(),
    )

    try:
        db.add(analysis_row)
        db.commit()
        db.refresh(analysis_row)
    except Exception as db_err:
        db.rollback()
        logger.error("Failed to persist analysis to database: error_type=%s", type(db_err).__name__)
        raise

    logger.info(
        "Successfully saved analysis id=%d with score=%d (truncated=%s)",
        analysis_row.id,
        analysis_row.match_score,
        was_truncated,
    )

    return analysis_row, was_truncated

