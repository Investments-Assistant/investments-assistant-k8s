from __future__ import annotations
from datetime import UTC, datetime
import uuid
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from src.db.database import Base


def _now() -> datetime:
    return datetime.now(UTC)


class Trade(Base):
    __tablename__ = "trades"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    broker: Mapped[str] = mapped_column(String(32))
    symbol: Mapped[str] = mapped_column(String(20))
    side: Mapped[str] = mapped_column(String(8))
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    order_type: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    broker_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mode: Mapped[str] = mapped_column(String(16))  # auto | manual | simulated
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    pnl_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
    filled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class DailyPnL(Base):
    __tablename__ = "daily_pnl"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(10), unique=True)
    realized_usd: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_usd: Mapped[float] = mapped_column(Float, default=0.0)
    auto_trading_halted: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
