Decision log for the Resume Screener Assistant.

## 1. Backend framework

**Status:** Decided  
**Decision:** FastAPI with Pydantic.  
**Alternatives considered:** Node backend with Zod.  
**Why:** Pydantic is built in, so the LLM's JSON output can be validated without a second validation library.  
**Tradeoff or limitation:** —

---

## 2. Frontend

**Status:** Decided  
**Decision:** React (Vite), three views (Analyze, History, Detail), no state library.  
**Alternatives considered:** Streamlit (would blur the API layer and make FastAPI redundant); server-rendered templates.  
**Why:** A clear client/server split with an explicit REST API.  
**Tradeoff or limitation:** —

---

## 3. Deployment shape

**Status:** Decided  
**Decision:** Frontend and backend deployed separately — static frontend host plus a separate API host. CORS is required; uses an exact origin allow-list read from settings, never a wildcard. Credentials are off because the app has no login or cookies.  
**Alternatives considered:** FastAPI serving the built frontend as one service (no CORS needed, but requires a build pipeline and a fallback route for client-side routing).  
**Why:** Separate deployment is the simpler default for free-tier hosting.  
**Tradeoff or limitation:** A free-tier backend may sleep when idle, so the first request after idle can be slow.

---

## 4. Database access

**Status:** Decided; production database choice is Open (see Open questions).  
**Decision:** SQLAlchemy with the database URL from an environment variable. SQLite for local development and review.  
**Alternatives considered:** —  
**Why:** The task says SQLite is fine. A reviewer can run it with zero setup. The same code can switch to Postgres by changing the URL.  
**Tradeoff or limitation:** On free hosting with an ephemeral disk, SQLite data is lost on redeploy.

---

## 5. LLM provider

**Status:** Decided  
**Decision:** Groq free tier, model `openai/gpt-oss-120b`. Strict JSON Schema structured output verified live with project key.  
**Alternatives considered:** —  
**Why:** Free, fast, and strict JSON Schema (`response_format` with `strict: True`) is verified working natively on `openai/gpt-oss-120b`. A representative screening run generated 698 prompt tokens and 313 completion tokens (~1,011 total tokens).  
**Tradeoff or limitation:** Groq free-tier limits: 30 requests/min, 1,000 requests/day, 8,000 tokens/min, 200,000 tokens/day. Per-document caps and retries must fit within 8,000 TPM.

---

## 6. LLM treated as untrusted

**Status:** Decided (design); not yet implemented.  
**Decision:** Validate the LLM's output against a Pydantic schema on the server even when the provider enforces a schema. Planned: one retry that feeds the validation error back to the model, then a graceful fallback message.  
**Alternatives considered:** —  
**Why:** Schema enforcement guarantees shape, not truthfulness.  
**Tradeoff or limitation:** —

---

## 7. Input limit

**Status:** Decided  
**Decision:** Per-document cap of 8,000 characters (`max_input_chars_per_doc`, roughly 2,000 tokens each), with truncation and a visible UI notice. Output cap (`max_completion_tokens`) set to 2,048.  
**Alternatives considered:** Higher caps (e.g., 12,000 characters per document).  
**Why:** Two 8,000-character documents (~4,000 tokens) + system prompt (~500 tokens) + output (~330 observed tokens, capped at 2,048) totals ~4,830 tokens under worst-case input, fitting safely inside Groq's 8,000 TPM limit.  
**Tradeoff or limitation:** Long resumes or lengthy job specs will be truncated with a notice.

---

## 8. Retries and timeout

**Status:** Decided  
**Decision:** 1 retry and a 30-second timeout, both configurable by environment variable.  
**Alternatives considered:** —  
**Why:** Each retry spends from a small token budget.  
**Tradeoff or limitation:** —

---

## 9. Configuration

**Status:** Decided  
**Decision:** pydantic-settings reads environment variables and a git-ignored `.env` file. The API key is stored as `SecretStr` so it is masked if the settings object is printed. The app refuses to start if the key is missing or looks like a placeholder.  
**Alternatives considered:** Stricter mode that rejects unknown environment variables instead of ignoring them.  
**Why:** —  
**Tradeoff or limitation:** Unknown environment variables are ignored, so a misnamed variable silently falls back to its default.

---

## 10. Project layout

**Status:** Decided  
**Decision:** Monorepo with `backend/` and `frontend/`. Backend layers: `api` (HTTP only) → `services` (logic) → `db` (storage). `schemas` (Pydantic, API and LLM contracts) are kept separate from `models` (SQLAlchemy tables) because they change for different reasons. Prompts live in their own folder.  
**Alternatives considered:** —  
**Why:** Each layer has one responsibility; schema and model separation avoids coupling API changes to DB migrations.  
**Tradeoff or limitation:** —

---

## 11. Dependencies

**Status:** Decided  
**Decision:** Pinned versions of direct dependencies only, taken from my own fresh install rather than from generated suggestions. Development inside a project-local virtual environment. Note: `requirements.txt` currently also lists `pytest` and `httpx`.  
**Alternatives considered:** —  
**Why:** Reproducible installs without over-constraining transitive dependencies.  
**Tradeoff or limitation:** —

---

## 12. Automated tests

**Status:** Decided for now; revisit if time allows.  
**Decision:** Skipped to keep scope small.  
**Alternatives considered:** Adding tests, particularly for prompt-injection defense and validation.  
**Why:** Scope constraint.  
**Tradeoff or limitation:** Prompt-injection defense and validation will be demonstrated manually unless tests are added later.

---

## 13. Resume input method

**Status:** Open  
**Decision:** Open — paste-only versus paste plus file upload (PDF/DOCX).  
**Alternatives considered:** File upload would add: a multipart dependency, a document parser, file-size limits, and file-safety handling.  
**Why:** —  
**Tradeoff or limitation:** —

---

## 14. Privacy and personal data

**Status:** Open — no decisions made yet.  
**Decision:** To be determined.  
**Alternatives considered:** —  
**Why:** —  
**Tradeoff or limitation:** —


