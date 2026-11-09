"""
REST API router

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
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.analysis import Analysis
from app.schemas.analysis import AnalysisCreate, AnalysisDetail, AnalysisSummary
from app.services.analysis_service import (
    AnalysisValidationError,
    screen_candidate,
)
from app.services.document_parser import (
    DocumentParserError,
    EmptyDocumentError,
    FileTooLargeError,
    UnsupportedFileTypeError,
    extract_text_from_file,
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
# POST /api/analyses/upload – Extract Text from File
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
    Accept an uploaded resume, extract its text in-memory, and return the text.
    Does not run the LLM or persist to the database, allowing HR to inspect the extracted text.
    """
    content = await file.read()

    try:
        extracted = extract_text_from_file(file.filename or "unknown", content)
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

    Sets response header `X-Input-Truncated: true` if the input exceeded character limits.
    """
    try:
        analysis_row, was_truncated = screen_candidate(payload=payload, db=db)
    except LLMRateLimitError as err:
        headers = {"Retry-After": str(err.retry_after)} if err.retry_after else None
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(err),
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
    except AnalysisValidationError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"LLM output could not be validated against schema: {'; '.join(err.problems)}",
        ) from None
    except (LLMAPIError, LLMClientError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM provider returned an upstream error. Please try again later.",
        ) from None
    except Exception as exc:
        logger.exception("Unexpected error during screening analysis: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected internal error occurred during screening.",
        ) from None

    if was_truncated:
        response.headers["X-Input-Truncated"] = "true"

    return AnalysisDetail.model_validate(analysis_row)


# ---------------------------------------------------------------------------
# GET /api/analyses – List / Search / Filter History
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=list[AnalysisSummary],
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
) -> list[AnalysisSummary]:
    """Retrieve history of past screenings with optional search and score range filters."""
    query = select(Analysis)

    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.where(Analysis.candidate_name.ilike(search_pattern))

    if min_score is not None:
        query = query.where(Analysis.match_score >= min_score)

    if max_score is not None:
        query = query.where(Analysis.match_score <= max_score)

    # Order newest first for the history view
    query = query.order_by(Analysis.created_at.desc()).offset(offset).limit(limit)

    rows = db.scalars(query).all()
    return [AnalysisSummary.model_validate(row) for row in rows]


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
    query = select(Analysis).where(Analysis.id == analysis_id)
    analysis_row = db.scalars(query).first()

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
    query = select(Analysis).where(Analysis.id == analysis_id)
    analysis_row = db.scalars(query).first()

    if analysis_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis with ID {analysis_id} not found.",
        )

    db.delete(analysis_row)
    db.commit()

