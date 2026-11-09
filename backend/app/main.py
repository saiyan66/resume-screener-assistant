from fastapi import FastAPI

app = FastAPI(title="Resume Screener Assistant", version="0.1.0")


@app.get("/api/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}