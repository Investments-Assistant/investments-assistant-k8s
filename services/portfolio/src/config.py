from __future__ import annotations
from functools import lru_cache
from typing import Literal
from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )
    environment: str = "production"
    log_level: str = "INFO"
    external_api_access: bool = False

    # Trading safety limits
    trading_mode: Literal["recommend", "auto"] = "recommend"
    auto_max_trade_usd: float = 500.0
    auto_daily_loss_limit_usd: float = 1000.0
    auto_allowed_symbols: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def auto_allowed_symbols_set(self) -> set[str]:
        if not self.auto_allowed_symbols.strip():
            return set()
        return {s.strip().upper() for s in self.auto_allowed_symbols.split(",")}

    # Database
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "investment_assistant"
    postgres_user: str = "ia_user"
    postgres_password: str = "change_me"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Redis (for trading_mode shared state)
    redis_url: str = "redis://redis:6379/0"

    # Brokers
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_paper: bool = True
    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 4002
    ibkr_client_id: int = 1
    ibkr_enabled: bool = False
    coinbase_api_key: str = ""
    coinbase_api_secret: str = ""
    binance_api_key: str = ""
    binance_secret_key: str = ""
    binance_testnet: bool = True

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
