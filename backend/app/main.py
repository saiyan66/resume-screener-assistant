from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.analyses import router as analyses_router
from app.core.config import get_settings
from app.db.database import Base, engine



# initialize SQLite database tables on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield



# FastAPI App Instance
settings = get_settings()

app = FastAPI(
    title="Resume Screener Assistant",
    description="Internal HR tool for evaluating resumes against job descriptions via LLM.",
    version="0.1.0",
    lifespan=lifespan,
)



app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Input-Truncated"],
)



app.include_router(analyses_router, prefix="/api")



# Health Check Endpoint
@app.get("/api/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
