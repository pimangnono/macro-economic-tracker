from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    app_name: str = "Macro Economic Tracker API"
    app_env: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "postgresql+asyncpg://macro_user:macro_password@localhost:5432/macro_tracker"
    redis_url: str = "redis://localhost:6379/0"
    cors_allowed_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    sse_ping_seconds: int = 15
    sse_poll_seconds: float = 2.0
    ingestion_http_timeout_seconds: float = 20.0
    ingestion_http_user_agent: str = "macro-economic-tracker/0.1"
    ingestion_schedule_interval_seconds: int = 900
    ingestion_startup_delay_seconds: int = 10
    ingestion_pull_limit: int = 10
    ingestion_schedule_sources: list[str] = []

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
