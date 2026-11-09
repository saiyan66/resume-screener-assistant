"""Pydantic schemas: the LLM output contract, API requests, and API responses."""

from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


MAX_REQUEST_CHARS = 100_000


N_SKILLS = 5
N_GAPS = 3
N_QUESTIONS = 3

# strict=True: reject non-strings instead of coercing them.
ShortText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300, strict=True)
]


class MatchReport(BaseModel):


    model_config = ConfigDict(extra="forbid")

    match_score: int = Field(ge=0, le=100)
    matching_skills: list[ShortText] = Field(min_length=N_SKILLS, max_length=N_SKILLS)
    gaps: list[ShortText] = Field(min_length=N_GAPS, max_length=N_GAPS)
    interview_questions: list[ShortText] = Field(min_length=N_QUESTIONS, max_length=N_QUESTIONS)



_ALLOWED_KEYWORDS = {
    "type", "properties", "required", "additionalProperties",
    "items", "enum", "anyOf", "$defs", "$ref",
}


def _strip(node):
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            if key not in _ALLOWED_KEYWORDS:
                continue
            if key in ("properties", "$defs"):
                # these map names to schemas; keep the names, clean each schema
                out[key] = {name: _strip(sub) for name, sub in value.items()}
            else:
                out[key] = _strip(value)
        return out
    if isinstance(node, list):
        return [_strip(item) for item in node]
    return node


def provider_schema() -> dict:
    return _strip(MatchReport.model_json_schema())


class AnalysisCreate(BaseModel):

    model_config = ConfigDict(extra="forbid")

    candidate_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    job_title: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] = ""
    job_description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_REQUEST_CHARS)
    ]
    resume_text: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_REQUEST_CHARS)
    ]


class AnalysisSummary(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: int
    candidate_name: str
    job_title: str
    match_score: int
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _assume_utc(cls, v: datetime) -> datetime:
        # SQLite drops timezone info; stored times are always UTC.
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)


class AnalysisDetail(AnalysisSummary):

    job_description: str
    report: MatchReport