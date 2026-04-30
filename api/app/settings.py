"""Application settings — env-driven, validated via pydantic-settings.

The .env file at the repo root is the source of truth in development.
In production we read straight from process env (Vercel / Fly / Neon).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# api/app/settings.py -> api/app -> api -> repo root
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """All env-driven configuration for the InsightFinder API."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ─── Database ───────────────────────────────────────────────
    database_url: str = Field(..., description="Postgres connection URL")

    # ─── LLM / embeddings ───────────────────────────────────────
    openai_api_key: str = Field(default="", description="OpenAI API key")
    anthropic_api_key: str = Field(default="", description="Anthropic API key")
    embedding_model: str = "text-embedding-3-small"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    generator_model: str = "gpt-4o-mini"

    # ─── API server ─────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: str = "http://localhost:3000"

    # ─── Cost guards ────────────────────────────────────────────
    max_upload_mb: int = 5
    max_pages_per_pdf: int = 50
    rate_limit_per_ip_per_hour: int = 20
    # Daily OpenAI spend cap across all users. Reset at UTC midnight.
    # Set generously low for free demo; raise via env var if needed.
    daily_spend_cap_usd: float = 5.0
    # Disable the cross-encoder rerank in production environments where
    # the model + torch don't fit (e.g. Render free tier 512MB).
    # When false, hybrid_rerank silently falls back to hybrid.
    enable_rerank: bool = True

    # ─── Observability ──────────────────────────────────────────
    log_level: str = "INFO"
    sentry_dsn: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]


# Module-level singleton — instantiated once on import.
settings = Settings()
