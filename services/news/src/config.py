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
    external_api_access: bool = False
    newsapi_key: str = ""
    guardian_api_key: str = ""
    newsletter_imap_server: str = "imap.gmail.com"
    newsletter_imap_port: int = 993
    newsletter_email_user: str = ""
    newsletter_email_password: str = ""
    newsletter_sender_filter: str = ""
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "investment_assistant"
    postgres_user: str = "ia_user"
    postgres_password: str = "change_me"
    postgres_ssl_mode: str = "disable"

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
