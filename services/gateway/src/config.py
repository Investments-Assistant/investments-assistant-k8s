"""Gateway service configuration."""

from __future__ import annotations

import ipaddress
from functools import lru_cache
from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────────
    environment: Literal["development", "production"] = "production"
    log_level: str = "INFO"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # ── Security — IP whitelist ────────────────────────────────────────────────
    allowed_ips: str = "127.0.0.1/32"  # override via ALLOWED_IPS env var

    @computed_field  # type: ignore[prop-decorator]
    @property
    def allowed_networks(self) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
        networks = []
        for entry in self.allowed_ips.split(","):
            entry = entry.strip()
            if not entry:
                continue
            try:
                networks.append(ipaddress.ip_network(entry, strict=False))
            except ValueError:
                pass
        return networks

    def is_ip_allowed(self, ip: str) -> bool:
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        return any(addr in net for net in self.allowed_networks)

    # ── Self-hosted LLM ───────────────────────────────────────────────────────
    llm_base_url: str = "http://llm:11434/v1"
    llm_api_key: str = ""
    llm_model_name: str = "llama3.1:8b-instruct"
    agent_max_tokens: int = 4096
    agent_temperature: float = 0.1
    agent_max_context_messages: int = 20
    agent_max_tool_iterations: int = 8
    llm_request_timeout_seconds: int = 300

    # ── Trading ────────────────────────────────────────────────────────────────
    trading_mode: Literal["recommend", "auto"] = "recommend"
    auto_max_trade_usd: float = 500.0
    auto_daily_loss_limit_usd: float = 1000.0
    auto_allowed_symbols: str = ""

    # ── Database ───────────────────────────────────────────────────────────────
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

    # ── Redis ──────────────────────────────────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"

    # ── Internal service URLs (K8s DNS) ───────────────────────────────────────
    market_data_url: str = "http://market-data:8001"
    news_url: str = "http://news:8002"
    portfolio_url: str = "http://portfolio:8003"
    simulation_url: str = "http://simulation:8004"
    scheduler_url: str = "http://scheduler:8005"
    forex_url: str = "http://forex:8006"

    # ── Reports ────────────────────────────────────────────────────────────────
    reports_dir: str = "/app/reports"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
