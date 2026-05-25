from __future__ import annotations
from functools import lru_cache
from urllib.parse import quote

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )
    environment: str = "production"
    log_level: str = "INFO"
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "investment_assistant"
    postgres_user: str = "ia_user"
    postgres_password: str = "change_me"
    postgres_ssl_mode: str = "disable"
    reports_dir: str = "/app/reports"
    market_data_refresh_minutes: int = 5
    weekly_report_day: int = 6
    weekly_report_hour: int = 18
    weekly_report_minute: int = 0

    # Service URLs
    gateway_url: str = "http://gateway:8000"
    news_url: str = "http://news:8002"
    market_data_url: str = "http://market-data:8001"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        user = quote(self.postgres_user, safe="")
        password = quote(self.postgres_password, safe="")
        return (
            f"postgresql+asyncpg://{user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
