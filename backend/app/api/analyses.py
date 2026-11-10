"""
api/analyses.py – REST API router for resume screening operations.

Endpoints:
  POST   /api/analyses       – Run an analysis, persist report, return detailed result.
  GET    /api/analyses       – List past analyses (search by candidate name, filter by score).
  GET    /api/analyses/{id}  – Retrieve a single detailed analysis by ID.
  DELETE /api/analyses/{id}  – Delete a past analysis record.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.analysis import (
    AnalysisCreate,
    AnalysisDetail,
    AnalysisListResponse,
    AnalysisSummary,
)
from app.services.analysis_service import (
    AnalysisValidationError,
    screen_candidate,
)
from app.services.document_parser import (
    DocumentParserError,
    EmptyDocumentError,
    FileTooLargeError,
    UnsupportedFileTypeError,
    extract_text_from_bytes,
    read_file_safely,
)
from app.services.history_service import (
    delete_analysis_by_id,
    get_analysis_by_id,
    list_analyses as fetch_analyses,
)
from app.services.llm_client import (
    LLMAPIError,
    LLMClientError,
    LLMConnectionError,
    LLMOutputTruncatedError,
    LLMRateLimitError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analyses", tags=["analyses"])


class ResumeUploadResponse(BaseModel):
    """Response returned after parsing an uploaded resume file."""

    filename: str
    text: str
    char_count: int


# ---------------------------------------------------------------------------
# POST /api/analyses/upload – Stream & Extract Text from File
# ---------------------------------------------------------------------------


@router.post(
    "/upload",
    response_model=ResumeUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract text from an uploaded resume (.pdf, .docx, .txt)",
)
async def upload_resume(
    file: UploadFile = File(..., description="Resume file (.pdf, .docx, or .txt)"),
) -> ResumeUploadResponse:
    """
    Accept an uploaded resume, stream bytes safely (capped at 5 MB), and extract text.
    Does not run the LLM or persist to DB, allowing HR to inspect extracted text first.
    """
    try:
        content = await read_file_safely(file)
        extracted = extract_text_from_bytes(file.filename or "unknown", content)
    except UnsupportedFileTypeError as err:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(err),
        ) from None
    except FileTooLargeError as err:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(err),
        ) from None
    except EmptyDocumentError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(err),
        ) from None
    except DocumentParserError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from None

    return ResumeUploadResponse(
        filename=file.filename or "unknown",
        text=extracted,
        char_count=len(extracted),
    )


# ---------------------------------------------------------------------------
# POST /api/analyses – Run Screening
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=AnalysisDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Screen a candidate resume against a job description",
)
def create_analysis(
    payload: AnalysisCreate,
    response: Response,
    db: Session = Depends(get_db),
) -> AnalysisDetail:
    """
    Evaluate candidate qualifications against the job description using Groq LLM.
    Returns the validated structured match report and saves the row in the database.

    Sets response header `X-Input-Truncated: true` and includes `input_truncated: true`
    in the response body if the input exceeded character limits.
    """
    try:
        analysis_row, was_truncated, token_usage = screen_candidate(payload=payload, db=db)
    except LLMRateLimitError as err:
        headers = {"Retry-After": str(err.retry_after)} if err.retry_after else None
        if err.is_daily_quota:
            friendly_msg = "Daily AI screening limit reached. The quota will reset tomorrow."
        elif err.retry_after:
            friendly_msg = f"AI service temporarily rate-limited. Please try again in {err.retry_after}s."
        else:
            friendly_msg = "AI service temporarily rate-limited. Please try again shortly."

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=friendly_msg,
            headers=headers,
        ) from None
    except LLMConnectionError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Connection to LLM provider timed out or failed. Please try again.",
        ) from None
    except LLMOutputTruncatedError as err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(err),
        ) from None
    except AnalysisValidationError:
        # Map to 502 Bad Gateway: upstream model failed to produce valid output (Problem 7)
        # Avoid echoing internal schema problem lists to the client
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI model failed to produce a valid report. Please try again.",
        ) from None
    except (LLMAPIError, LLMClientError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM provider returned an upstream error. Please try again later.",
        ) from None
    except Exception as exc:
        # Log only the exception class name to avoid parameter reflection (Problem 4)
        logger.error("Unexpected error during screening analysis: error_type=%s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected internal error occurred during screening.",
        ) from None

    if was_truncated:
        response.headers["X-Input-Truncated"] = "true"

    detail = AnalysisDetail.model_validate(analysis_row)
    detail.input_truncated = was_truncated
    detail.token_usage = token_usage
    return detail


# ---------------------------------------------------------------------------
# GET /api/analyses – List / Search / Filter History
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=AnalysisListResponse,
    status_code=status.HTTP_200_OK,
    summary="List past analyses with search and score filtering",
)
def list_analyses(
    search: Optional[str] = Query(
        None,
        description="Filter by candidate name (case-insensitive substring)",
    ),
    min_score: Optional[int] = Query(
        None,
        ge=0,
        le=100,
        description="Minimum match score (0-100)",
    ),
    max_score: Optional[int] = Query(
        None,
        ge=0,
        le=100,
        description="Maximum match score (0-100)",
    ),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Records offset for pagination"),
    db: Session = Depends(get_db),
) -> AnalysisListResponse:
    """Retrieve history of past screenings with search, score filters, and total count."""
    # Validate score range (Problem 10)
    if min_score is not None and max_score is not None and min_score > max_score:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="min_score cannot be greater than max_score.",
        )

    # Delegate SQL queries to history_service (Problem 8)
    rows, total = fetch_analyses(
        db=db,
        search=search,
        min_score=min_score,
        max_score=max_score,
        limit=limit,
        offset=offset,
    )

    items = [AnalysisSummary.model_validate(row) for row in rows]
    return AnalysisListResponse(items=items, total=total)


# ---------------------------------------------------------------------------
# GET /api/analyses/{id} – Retrieve Single Analysis
# ---------------------------------------------------------------------------


@router.get(
    "/{analysis_id}",
    response_model=AnalysisDetail,
    status_code=status.HTTP_200_OK,
    summary="Get detailed match report for a specific analysis",
)
def get_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
) -> AnalysisDetail:
    """Retrieve the full detailed match report for a given analysis ID."""
    analysis_row = get_analysis_by_id(db, analysis_id)

    if analysis_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis with ID {analysis_id} not found.",
        )

    return AnalysisDetail.model_validate(analysis_row)


# ---------------------------------------------------------------------------
# DELETE /api/analyses/{id} – Delete Analysis Record
# ---------------------------------------------------------------------------


@router.delete(
    "/{analysis_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a past analysis record",
)
def delete_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Permanently delete an analysis record from the database."""
    deleted = delete_analysis_by_id(db, analysis_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis with ID {analysis_id} not found.",
        )
