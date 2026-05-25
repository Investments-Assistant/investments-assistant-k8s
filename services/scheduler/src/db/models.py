from __future__ import annotations
from datetime import UTC, datetime
import uuid
from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from src.db.database import Base


def _now() -> datetime:
    return datetime.now(UTC)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title: Mapped[str] = mapped_column(String(256))
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    html_content: Mapped[str] = mapped_column(Text)
    pdf_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    total_pnl_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
