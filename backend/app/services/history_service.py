"""Query operations for past screening analyses.
"""

from typing import Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.analysis import Analysis


def _escape_like_wildcards(val: str) -> str:
    """
    Escape SQL LIKE wildcards (%, _) and backslashes.
    Ensures a search for 'C++' or '50%' treats '%' as a literal character.
    """
    return val.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_analyses(
    db: Session,
    search: Optional[str] = None,
    min_score: Optional[int] = None,
    max_score: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[list[Analysis], int]:
    """
    Retrieve paginated analyses matching optional search and score filters.

    Returns:
        Tuple[list[Analysis], int]: (matching_rows, total_matching_count)
    """
    base_query = select(Analysis)
    count_query = select(func.count(Analysis.id))

    if search and search.strip():
        escaped = _escape_like_wildcards(search.strip())
        pattern = f"%{escaped}%"
        filter_clause = Analysis.candidate_name.ilike(pattern, escape="\\")
        base_query = base_query.where(filter_clause)
        count_query = count_query.where(filter_clause)

    if min_score is not None:
        base_query = base_query.where(Analysis.match_score >= min_score)
        count_query = count_query.where(Analysis.match_score >= min_score)

    if max_score is not None:
        base_query = base_query.where(Analysis.match_score <= max_score)
        count_query = count_query.where(Analysis.match_score <= max_score)

    # Deterministic sorting: newest first, using id as strict tiebreaker (Problem 11)
    base_query = (
        base_query.order_by(Analysis.created_at.desc(), Analysis.id.desc())
        .offset(offset)
        .limit(limit)
    )

    total = db.scalar(count_query) or 0
    items = list(db.scalars(base_query).all())
    return items, total


def get_analysis_by_id(db: Session, analysis_id: int) -> Optional[Analysis]:
    """Retrieve a single analysis record by ID, or None if not found."""
    return db.scalars(select(Analysis).where(Analysis.id == analysis_id)).first()


def delete_analysis_by_id(db: Session, analysis_id: int) -> bool:
    """Delete an analysis record by ID. Returns True if deleted, False if not found."""
    row = get_analysis_by_id(db, analysis_id)
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True

