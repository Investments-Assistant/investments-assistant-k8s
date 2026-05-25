from __future__ import annotations
from datetime import UTC, datetime
import uuid
from sqlalchemy import JSON, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from src.db.database import Base


def _now() -> datetime:
    return datetime.now(UTC)


class SimulationResult(Base):
    __tablename__ = "simulation_results"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(256))
    strategy: Mapped[dict] = mapped_column(JSON)
    initial_capital: Mapped[float] = mapped_column(Float)
    final_value: Mapped[float] = mapped_column(Float)
    total_return_pct: Mapped[float] = mapped_column(Float)
    sharpe_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    trades_count: Mapped[int] = mapped_column(Integer, default=0)
    period_start: Mapped[str] = mapped_column(String(10))
    period_end: Mapped[str] = mapped_column(String(10))
    equity_curve: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
