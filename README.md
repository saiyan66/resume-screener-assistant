# Resume Screener Assistant

An internal tool for HR that compares a job description with a candidate
resume and returns a structured match report: score, top matching skills,
gaps, and suggested interview questions.

> Built as the Synthweb AI Product Engineer assessment.

## Planned stack

| Layer | Choice |
|---|---|
| Backend | FastAPI + Pydantic |
| Database | SQLite |
| Frontend | React (Vite) |
| LLM | TBD |

## Planned features

- [ ] Input screen for job description and resume (paste or upload)
- [ ] LLM analysis returning schema-validated JSON
- [ ] Persistent history with search by candidate name and score range
- [ ] Graceful handling of API failures, empty, malformed, and oversized input
- [ ] Prompt-injection defense, with tests
- [ ] Privacy handling for candidate personal data

