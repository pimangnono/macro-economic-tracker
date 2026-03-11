from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    app_name: str = "Macro Economic Tracker API"
    app_env: str = "development"
    log_level: str = "INFO"
    log_json: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    web_base_url: str = "http://localhost:3000"
    database_url: str = "postgresql+asyncpg://macro_user:macro_password@localhost:5432/macro_tracker"
    redis_url: str = "redis://localhost:6379/0"
    cors_allowed_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    session_duration_hours: int = 24
    invite_expiry_days: int = 7
    sse_ping_seconds: int = 15
    sse_poll_seconds: float = 2.0
    ingestion_http_timeout_seconds: float = 20.0
    ingestion_http_user_agent: str = "macro-economic-tracker/0.1"
    ingestion_schedule_interval_seconds: int = 900
    ingestion_startup_delay_seconds: int = 10
    ingestion_pull_limit: int = 10
    ingestion_schedule_sources: list[str] = []
    s3_endpoint: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_bucket: str = ""
    sentry_dsn: str = ""

    # LLM / OpenRouter settings
    openai_api_key: str = ""
    openai_base_url: str = "https://openrouter.ai/api/v1"
    openai_default_model: str = "openai/gpt-4o-mini"
    openai_complex_model: str = "openai/gpt-5-mini"
    openai_summary_model: str = "gpt-5-mini"
    openai_extract_model: str = "gpt-5-nano"
    openai_embedding_model: str = "openai/text-embedding-3-small"
    openai_embedding_dimensions: int = 1536
    openai_max_retries: int = 3
    openai_timeout_seconds: float = 60.0

    # Pipeline settings
    pipeline_enabled: bool = True
    pipeline_batch_size: int = 10

    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", ROOT_DIR / ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("ingestion_schedule_sources", mode="before")
    @classmethod
    def parse_schedule_sources(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
