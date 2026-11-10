# AI Usage

How AI tools were used while building the Resume Screener Assistant (Synthweb AI Product Engineer assessment).

## Tools used

| Tool | Role |
|---|---|
| Claude (web) | Design review, layering rules, prompt drafting, critique of generated code (retries, privacy, schema) |
| Antigravity | File-by-file implementation assistance under strict “one file at a time / defend every line” rules |

No secrets were pasted into prompts. API keys stayed in a git-ignored `.env`; only placeholders appear in `.env.example`.

## Working style with AI

I did not ask for a whole app in one shot. Each request was scoped to a single file, required a short “what/why” before code, and required rejected alternatives to be named. I reviewed and edited every generated file before keeping it.

---

## Three key prompts

### Prompt 1 — Process / guardrails (Claude / Antigravity)

> You are assisting on a hiring assessment where I must understand and be able to defend every line. 
> Rules: 
> (1) Never run git commit or git push; I commit manually. 
> (2) Work on one file at a time. Before writing it, state in 2–3 sentences what it does and why it’s needed; after writing it, explain the non-obvious parts. 
> (3) Do not generate multiple files in one step. 
> (4) Never write real secrets; use placeholders in `.env.example`. 
> (5) When you make a design choice, name the alternative you rejected and why. 
> (6) If you are unsure about a library’s API, say so instead of guessing.

**Why this mattered:** Kept ownership with me, forced readable layering, and stopped the model from inventing APIs or committing on my behalf.

### Prompt 2 — Groq client boundary (`llm_client.py`)

> Create only `backend/app/services/llm_client.py`. First read `docs/DECISIONS.md` and follow it.
>
> Purpose: one function that sends a system prompt and a user prompt to Groq and returns the raw reply text plus token usage. It must NOT validate the report, retry validation failures, build prompts, truncate input, or touch the database; those belong to other layers.
>
> Use the groq Python SDK (1.7.0). Translate failures into small custom exceptions (rate limit with retry-after, timeout/connection, other API error, empty content). No exception message may contain prompt text, resume text, or the API key. Never log prompts or responses—only status, model name, and token counts. Before writing, state which Groq SDK exception classes you will catch and how you verified they exist.

**Why this mattered:** Produced a thin transport layer. Validation retries and DB writes stayed in `analysis_service.py`.

### Prompt 3 — Structured LLM contract (`schemas/analysis.py`)

> Create only `backend/app/schemas/analysis.py`. Define one Pydantic v2 model for the JSON an LLM returns: score 0–100, exactly 5 matching skills, exactly 3 gaps, exactly 3 interview questions. Before writing, explain each constraint and the failure it guards against. After writing, list every JSON-schema keyword stripped from `provider_schema()` and why, and list assumptions about Groq that were not given.

**Why this mattered:** Forced an explicit contract (“validate before display”) and made provider-schema stripping a conscious choice instead of copy-paste.

---

## Two places AI was wrong (and how I fixed it)

### 1. Groq client looked “done” but violated our retry/token budget

**What AI produced:** A usable-looking Groq wrapper that still relied on SDK defaults / weak operational details.

**What was wrong (simplified):**

| Issue | Plain meaning |
|---|---|
| SDK auto-retries | Groq’s client can retry 429/5xx/connection failures on its own. That bypasses `LLM_MAX_RETRIES=1` and can burn tokens/time silently. |
| New `Groq()` every call | Extra connection pools; no reuse. |
| No `finish_reason` check | If output hits the token cap, you get truncated JSON. Treating that as “malformed” and retrying the same call fails again. |
| Vague HTTP errors | A 400 could be bad schema, bad key, or dead model—generic “HTTP 400” is hard to debug. |
| Magic `2048` | Output token cap affects rate limits; it needed a named constant and a comment. |

**How I fixed it:** Set `max_retries=0` on the SDK client; cache one client with `lru_cache`; raise `LLMOutputTruncatedError` when `finish_reason == "length"`; keep a short provider error code on `LLMAPIError`; name `MAX_OUTPUT_TOKENS = 2048`. Service-layer retries remain the only validation retry policy.

### 2. Schema / persistence drafts that didn’t match Groq strict mode or privacy goals

**What AI produced (earlier drafts):**

- An `AnalysisResult`-style model that evolved into `MatchReport`, including a later `candidate_name` field with a Pydantic default.
- Ideas that persisted full `resume_text`, stored reports as raw JSON strings, and kept failed runs with `status` / `error_message`.

**What was wrong:**

1. **Strict JSON Schema break:** Groq `strict: true` requires every property in `required`. A defaulted `candidate_name` was omitted from `required`, so live screening returned HTTP 400 from Groq (surfaced as 502) until `candidate_name` was made required (`Field(...)`).
2. **Privacy / DB shape:** Storing resume text and failed half-records increased PII retention for no product value.

**How I fixed it:**

| Earlier idea | Final choice |
|---|---|
| Store `resume_text` | Removed — resume stays in memory for the request only |
| `report_json: str` | `report: Mapped[dict]` via SQLAlchemy `JSON` |
| Persist failed runs | Success-only — failures return HTTP errors, nothing saved |
| Nullable `match_score` | Non-null `match_score` after validated `MatchReport` |

### 3. Pydantic v2 Type Coercion: String numbers silently bypassed integer schema

**What happened:**
When defining the `MatchReport` schema, the score field was declared as:
```python
match_score: int = Field(ge=0, le=100)
```
While `ShortText` had strict string constraints, `match_score` lacked `strict=True`.

**The Failing Test Proof:**
In our contract test suite (`tests/test_schemas_and_prompts.py`), we wrote an explicit test asserting that passing a string for the match score must raise a `ValidationError`:
```python
@pytest.mark.parametrize(
    "patch_dict, description",
    [
        ({"match_score": "70"}, "score as string instead of integer"),
        ...
    ],
)
def test_invalid_match_report_rejected(patch_dict, description):
    with pytest.raises(ValidationError):
        MatchReport.model_validate(base_data)
```

**The Failure:**
The test failed with:
```text
FAILED tests/test_schemas_and_prompts.py::test_invalid_match_report_rejected[patch_dict1-score as string instead of integer]
E       Failed: DID NOT RAISE ValidationError
```
Because Pydantic v2 operates in default coercion mode unless told otherwise, it silently cast `"70"` (string) into `70` (integer). If the LLM returned numbers formatted as strings, the schema silently swallowed the deviation rather than enforcing strict JSON types.

**How I fixed it:**
Enforced `strict=True` on the field in `schemas/analysis.py`:
```python
match_score: int = Field(ge=0, le=100, strict=True)
```
Re-running `pytest` confirmed that string numbers are now properly rejected with `ValidationError`, bringing the test suite to **30 passed / 0 failed (100% green)**.

---

## Honest takeaway

AI was fast at scaffolding layered FastAPI code and explaining tradeoffs. It was weaker on provider edge cases (SDK retries, truncated completions, Groq strict-schema `required` rules) until I challenged those with live calls and a written problem list. Those corrections are what made the screening path reliable.
