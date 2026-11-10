"""Integration tests for API reliability, validation, retries, and error contracts.

Tests:
a. Happy path: POST -> GET by id -> GET list.
b. Empty or whitespace-only inputs return 422 without calling LLM.
c. Input exceeding hard request limit returns 422 without calling LLM.
d. Input over max_input_chars_per_doc is truncated and signals truncation.
e. Malformed first LLM reply recovers on second attempt (2 calls, 201).
f. Malformed on every attempt returns 502, saves nothing, calls llm_max_retries + 1 times.
g. Parametrized provider errors (429 with Retry-After, 504, 502).
h. History search, score filters, min > max validation, wildcard escaping, ordering.
i. DELETE returns 204 then GET returns 404; missing DELETE returns 404.
j. Document upload endpoint: valid txt, 415 unsupported, 413 oversized, 422 empty.
"""

import io
import json
import re
import pytest
from app.core.config import get_settings
from app.models.analysis import Analysis
from app.services.llm_client import (
    LLMAPIError,
    LLMConnectionError,
    LLMOutputTruncatedError,
    LLMRateLimitError,
)
from tests.conftest import FakeLLM, make_match_report_json


def test_happy_path_lifecycle(client, fake_llm: FakeLLM):
    """Happy path: POST returns 201 with report and id; GET by id returns it; list contains it."""
    fake_llm.set_default(make_match_report_json(candidate_name="Alice Smith", match_score=90))

    # 1. Create analysis
    payload = {
        "job_description": "We need a Senior Python Engineer.",
        "resume_text": "Alice Smith: Python, FastAPI, SQL, Docker, Git.",
        "job_title": "Senior Python Engineer",
    }
    post_resp = client.post("/api/analyses", json=payload)
    assert post_resp.status_code == 201, post_resp.text
    data = post_resp.json()
    assert data["candidate_name"] == "Alice Smith"
    assert data["match_score"] == 90
    assert "id" in data
    analysis_id = data["id"]

    # 2. Retrieve by ID
    get_resp = client.get(f"/api/analyses/{analysis_id}")
    assert get_resp.status_code == 200
    detail = get_resp.json()
    assert detail["id"] == analysis_id
    assert detail["candidate_name"] == "Alice Smith"
    assert detail["report"]["match_score"] == 90

    # 3. Verify present in list
    list_resp = client.get("/api/analyses")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] >= 1
    matching_ids = [item["id"] for item in list_data["items"] if item["id"] == analysis_id]
    assert len(matching_ids) == 1


@pytest.mark.parametrize(
    "invalid_payload",
    [
        {"job_description": "", "resume_text": "Valid resume text"},
        {"job_description": "   ", "resume_text": "Valid resume text"},
        {"job_description": "Valid JD", "resume_text": ""},
        {"job_description": "Valid JD", "resume_text": "   "},
    ],
)
def test_empty_or_whitespace_inputs_rejected(client, fake_llm: FakeLLM, invalid_payload):
    """Empty or whitespace-only JD or resume returns 422 and LLM is never called."""
    resp = client.post("/api/analyses", json=invalid_payload)
    assert resp.status_code == 422
    assert len(fake_llm.calls) == 0


def test_hard_request_limit_rejected(client, fake_llm: FakeLLM):
    """Input exceeding the hard request limit (100,000 chars) returns 422 without calling LLM."""
    huge_text = "A" * 100_001
    resp = client.post(
        "/api/analyses",
        json={"job_description": "Valid JD", "resume_text": huge_text},
    )
    assert resp.status_code == 422
    assert len(fake_llm.calls) == 0


def test_document_truncation_before_llm(client, fake_llm: FakeLLM):
    """Input over max_input_chars_per_doc is truncated before LLM and response signals truncation."""
    settings = get_settings()
    cap = settings.max_input_chars_per_doc

    fake_llm.set_default(make_match_report_json())

    # Send resume text larger than cap
    oversized_resume = "X" * (cap + 1500)
    resp = client.post(
        "/api/analyses",
        json={"job_description": "Short valid JD", "resume_text": oversized_resume},
    )
    assert resp.status_code == 201
    assert resp.headers.get("X-Input-Truncated") == "true"
    assert resp.json()["input_truncated"] is True

    # Inspect what the fake LLM actually received in the user prompt
    assert len(fake_llm.calls) == 1
    _, user_prompt = fake_llm.calls[0]

    # Extract text between <resume_TAG> and </resume_TAG>
    match = re.search(r"<resume_[a-f0-9]+>\s*(.*?)\s*</resume_[a-f0-9]+>", user_prompt, re.DOTALL)
    assert match, "User prompt must contain delimited resume block"
    delivered_resume = match.group(1)
    assert len(delivered_resume) == cap, f"Delivered resume must be truncated to exactly {cap} chars"


def test_malformed_llm_first_reply_recovers_on_retry(client, fake_llm: FakeLLM):
    """First LLM reply is malformed JSON, second is valid: result is 201 and LLM called twice."""
    fake_llm.queue_response("MALFORMED NOT JSON {broken")
    fake_llm.queue_response(make_match_report_json(candidate_name="Recovered Candidate"))

    resp = client.post(
        "/api/analyses",
        json={"job_description": "Python JD", "resume_text": "Python resume"},
    )
    assert resp.status_code == 201
    assert resp.json()["candidate_name"] == "Recovered Candidate"
    assert len(fake_llm.calls) == 2


def test_malformed_llm_on_every_attempt_returns_502(client, fake_llm: FakeLLM, db_session):
    """Malformed on every attempt returns 502, saves nothing, and calls llm_max_retries + 1 times."""
    settings = get_settings()
    expected_calls = settings.llm_max_retries + 1

    fake_llm.set_default("STILL NOT JSON")

    resp = client.post(
        "/api/analyses",
        json={"job_description": "Python JD", "resume_text": "Python resume"},
    )
    assert resp.status_code == 502
    assert len(fake_llm.calls) == expected_calls
    # Verify nothing was saved in the database
    assert db_session.query(Analysis).count() == 0


@pytest.mark.parametrize(
    "exception_to_raise, expected_status, expected_retry_header",
    [
        (LLMRateLimitError(retry_after="7"), 429, "7"),
        (LLMConnectionError("Connection timeout"), 504, None),
        (LLMAPIError(status_code=500, code="internal_error"), 502, None),
        (LLMOutputTruncatedError("Token cap hit"), 502, None),
    ],
)
def test_parametrized_provider_failures(
    client, fake_llm: FakeLLM, db_session, exception_to_raise, expected_status, expected_retry_header
):
    """Provider failures map to proper HTTP status, omit provider text, and save nothing."""
    fake_llm.set_default(exception_to_raise)

    resp = client.post(
        "/api/analyses",
        json={"job_description": "JD text", "resume_text": "Resume text"},
    )
    assert resp.status_code == expected_status

    if expected_retry_header:
        assert resp.headers.get("Retry-After") == expected_retry_header

    # Response body must not leak provider internals (e.g. "Groq")
    assert "Groq" not in resp.text
    # Nothing must be saved
    assert db_session.query(Analysis).count() == 0


def test_history_filtering_search_and_ordering(client, db_session):
    """History: seed rows; case-insensitive substring search; score filters; % escaping; newest first."""
    # Seed 4 rows
    r1 = Analysis(candidate_name="Alice Smith", job_title="Dev", job_description="JD", match_score=95, report={})
    r2 = Analysis(candidate_name="Bob Jones", job_title="Dev", job_description="JD", match_score=60, report={})
    r3 = Analysis(candidate_name="Charlie Brown", job_title="Dev", job_description="JD", match_score=40, report={})
    r4 = Analysis(candidate_name="Dave 100% Match", job_title="Dev", job_description="JD", match_score=85, report={})
    db_session.add_all([r1, r2, r3, r4])
    db_session.commit()

    # 1. Case-insensitive substring search
    res_search_lower = client.get("/api/analyses?search=alice").json()
    assert res_search_lower["total"] == 1
    assert res_search_lower["items"][0]["candidate_name"] == "Alice Smith"

    res_search_upper = client.get("/api/analyses?search=SMITH").json()
    assert res_search_upper["total"] == 1
    assert res_search_upper["items"][0]["candidate_name"] == "Alice Smith"

    # 2. Score filters
    res_min = client.get("/api/analyses?min_score=80").json()
    assert res_min["total"] == 2
    names_min = {item["candidate_name"] for item in res_min["items"]}
    assert names_min == {"Alice Smith", "Dave 100% Match"}

    res_max = client.get("/api/analyses?max_score=50").json()
    assert res_max["total"] == 1
    assert res_max["items"][0]["candidate_name"] == "Charlie Brown"

    # 3. min_score > max_score returns 422
    res_invalid_range = client.get("/api/analyses?min_score=90&max_score=50")
    assert res_invalid_range.status_code == 422

    # 4. Searching for "%" must match only the literal "%" row, not every row
    res_wildcard = client.get("/api/analyses?search=%").json()
    assert res_wildcard["total"] == 1
    assert res_wildcard["items"][0]["candidate_name"] == "Dave 100% Match"

    # 5. Ordering: newest first (id descending)
    res_all = client.get("/api/analyses").json()
    assert res_all["total"] == 4
    ids = [item["id"] for item in res_all["items"]]
    assert ids == sorted(ids, reverse=True)


def test_delete_lifecycle(client, db_session):
    """DELETE returns 204 then GET returns 404; deleting a missing id returns 404."""
    # Seed a row
    row = Analysis(candidate_name="Delete Me", job_title="Dev", job_description="JD", match_score=70, report={})
    db_session.add(row)
    db_session.commit()
    target_id = row.id

    # DELETE existing row
    del_resp = client.delete(f"/api/analyses/{target_id}")
    assert del_resp.status_code == 204

    # GET must now return 404
    get_resp = client.get(f"/api/analyses/{target_id}")
    assert get_resp.status_code == 404

    # Deleting missing row must return 404
    del_missing = client.delete(f"/api/analyses/{target_id}")
    assert del_missing.status_code == 404


def test_upload_endpoint_validation_and_safety(client, fake_llm: FakeLLM, db_session):
    """Upload endpoint: valid txt returns text; 415 unsupported; 413 oversized; 422 empty; no LLM/DB calls."""
    # 1. Valid .txt
    txt_content = b"Candidate resume text in plain text format."
    resp_valid = client.post(
        "/api/analyses/upload",
        files={"file": ("resume.txt", io.BytesIO(txt_content), "text/plain")},
    )
    assert resp_valid.status_code == 200
    assert resp_valid.json()["text"] == "Candidate resume text in plain text format."

    # 2. Unsupported extension -> 415
    resp_unsupported = client.post(
        "/api/analyses/upload",
        files={"file": ("resume.exe", io.BytesIO(b"executable bytes"), "application/octet-stream")},
    )
    assert resp_unsupported.status_code == 415

    # 3. File over 5 MB limit -> 413
    huge_bytes = b"0" * (5 * 1024 * 1024 + 1024)
    resp_oversized = client.post(
        "/api/analyses/upload",
        files={"file": ("large.txt", io.BytesIO(huge_bytes), "text/plain")},
    )
    assert resp_oversized.status_code == 413

    # 4. Empty or whitespace-only file -> 422
    resp_empty = client.post(
        "/api/analyses/upload",
        files={"file": ("empty.txt", io.BytesIO(b"   \n  \t  "), "text/plain")},
    )
    assert resp_empty.status_code == 422

    # None of these upload calls should ever invoke the LLM or create database rows
    assert len(fake_llm.calls) == 0
    assert db_session.query(Analysis).count() == 0

