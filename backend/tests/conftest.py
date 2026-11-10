"""Shared test configuration, fixtures, and safety nets.

Strict rules enforced here:
- Sets test environment variables BEFORE importing application modules.
- Hard safety net: attempts to construct the real Groq client fail loudly with AssertionError.
- In-memory SQLite with StaticPool and check_same_thread=False for FastAPI TestClient thread safety.
- Dependency override for get_db yielding isolated test sessions.
- FakeLLM fixture patching app.services.analysis_service.call_groq.
- Synchronous FastAPI TestClient.
"""

import json
import os
from typing import Generator
import pytest

# 1. Set environment variables BEFORE importing any app code
os.environ["GROQ_API_KEY"] = "TEST-SECRET-KEY-DO-NOT-LEAK"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.core.config import get_settings
# Clear cached settings so it picks up the test environment variables
get_settings.cache_clear()

from app.db.database import Base, get_db
from app.main import app
from app.services.llm_client import LLMResponse, LLMTokenUsage


# 2. In-memory database engine with StaticPool for cross-thread memory sharing
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_database():
    """Create all database tables before each test and drop them after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a direct database session for seeding or asserting rows in tests."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Synchronous FastAPI TestClient with the get_db dependency overridden."""
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# 3. Safety net: prevent any test path from touching the real Groq API
@pytest.fixture(autouse=True)
def no_real_llm(monkeypatch):
    """Loudly fail any unmocked call that tries to create a real Groq client."""
    def boom(*args, **kwargs):
        raise AssertionError("A test tried to reach the real Groq client")

    monkeypatch.setattr("app.services.llm_client._get_client", boom)


# 4. Fake LLM for recording calls and scripting responses/exceptions
class FakeLLM:
    """Records received (system_prompt, user_prompt) tuples and returns scripted responses."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.scripted_responses: list[LLMResponse | Exception] = []
        self.default_response: LLMResponse | Exception | None = None

    def queue_response(self, text_or_exception: str | Exception, prompt_tokens: int = 100, completion_tokens: int = 50):
        """Queue a specific response or exception for subsequent calls."""
        if isinstance(text_or_exception, Exception):
            self.scripted_responses.append(text_or_exception)
        else:
            self.scripted_responses.append(
                LLMResponse(
                    text=text_or_exception,
                    usage=LLMTokenUsage(
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=prompt_tokens + completion_tokens,
                    ),
                )
            )

    def set_default(self, text_or_exception: str | Exception, prompt_tokens: int = 100, completion_tokens: int = 50):
        """Set a default response if the queue is exhausted."""
        if isinstance(text_or_exception, Exception):
            self.default_response = text_or_exception
        else:
            self.default_response = LLMResponse(
                text=text_or_exception,
                usage=LLMTokenUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                ),
            )

    def __call__(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        self.calls.append((system_prompt, user_prompt))
        if self.scripted_responses:
            item = self.scripted_responses.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        if self.default_response is not None:
            if isinstance(self.default_response, Exception):
                raise self.default_response
            return self.default_response
        raise RuntimeError("FakeLLM received a call but no scripted or default response was set.")


@pytest.fixture
def fake_llm(monkeypatch) -> FakeLLM:
    """Mock the LLM where it is used (in analysis_service.call_groq)."""
    fake = FakeLLM()
    monkeypatch.setattr("app.services.analysis_service.call_groq", fake)
    return fake


# 5. Helper that builds a valid MatchReport JSON string
def make_match_report_json(
    candidate_name: str = "Alice Candidate",
    match_score: int = 85,
    skills: list[str] | None = None,
    gaps: list[str] | None = None,
    questions: list[str] | None = None,
    **extra,
) -> str:
    """Construct a schema-valid JSON string matching app.schemas.analysis.MatchReport."""
    skills = skills or ["Python", "FastAPI", "SQLAlchemy", "PostgreSQL", "Docker"]
    gaps = gaps or ["Kubernetes", "AWS", "Kafka"]
    questions = questions or [
        "How do you handle Kubernetes deployments?",
        "Describe your experience with AWS services.",
        "Explain event streaming with Kafka.",
    ]
    data = {
        "candidate_name": candidate_name,
        "match_score": match_score,
        "matching_skills": skills,
        "gaps": gaps,
        "interview_questions": questions,
        **extra,
    }
    return json.dumps(data)

