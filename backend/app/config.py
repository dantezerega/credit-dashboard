from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings, overridable via environment variables."""

    database_url: str = "postgresql+psycopg://dash:dash@localhost:5432/dash"
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 300
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000", "http://localhost:8080"]

    model_config = {"env_prefix": "DASH_"}

    @field_validator("database_url")
    @classmethod
    def normalize_db_scheme(cls, v: str) -> str:
        """Hosted Postgres (Neon, Supabase, Vercel Postgres) hands out
        postgres:// or postgresql:// URLs; SQLAlchemy needs the psycopg
        driver spelled out."""
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+psycopg://", 1)
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+psycopg://", 1)
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
