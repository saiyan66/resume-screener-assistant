"""One row per saved analysis. Stores the validated report, not the resume text."""

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Analysis(Base):
    __tablename__ = "analysis"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Typed by HR; never sent to the LLM.
    candidate_name: Mapped[str] = mapped_column(String(255), index=True)
    job_title: Mapped[str] = mapped_column(String(255), default="")
    job_description: Mapped[str] = mapped_column(Text)

    # Validated LLM output. match_score duplicates report["score"] as a real indexed column
    match_score: Mapped[int] = mapped_column(Integer, index=True)
    report: Mapped[dict] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self) -> str:
        return f"<Analysis id={self.id} score={self.match_score}>"