"""Application settings, loaded from environment variables and backend/.env."""

import json
from functools import lru_cache
from typing import Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    groq_api_key: SecretStr
    groq_model: str = "openai/gpt-oss-120b"


    # LLM behaviour
    llm_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    llm_timeout_seconds: int = Field(default=30, gt=0)
    llm_max_retries: int = Field(default=1, ge=0, le=3)

    # Per-document cap in characters (~4 chars per token). Sized so that
    # JD + resume + prompt + output fit safely within the free tier's 8,000 TPM limit.
    max_input_chars_per_doc: int = Field(default=4_000, gt=0)


    database_url: str = "sqlite:///./app.db"


    cors_origins: list[str] | str = ["http://localhost:5173", "http://localhost:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("groq_api_key")
    @classmethod
    def key_must_not_be_placeholder(cls, v: SecretStr) -> SecretStr:
        raw = v.get_secret_value().strip().lower()
        if not raw or raw.startswith("your") or raw.endswith("_here"):
            raise ValueError("GROQ_API_KEY looks like a placeholder; set a real key in .env")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings instance (the .env file is read once)."""
    return Settings()