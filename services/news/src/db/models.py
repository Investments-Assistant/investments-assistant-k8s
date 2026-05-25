from __future__ import annotations
from datetime import UTC, datetime
import uuid
from sqlalchemy import JSON, DateTime, Float, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from src.db.database import Base


def _now() -> datetime:
    return datetime.now(UTC)


class NewsArticle(Base):
    __tablename__ = "news_articles"
    __table_args__ = (
        Index(
            "ix_news_articles_fts",
            func.to_tsvector(
                "english",
                func.coalesce(func.cast("title", Text), "")
                + " "
                + func.coalesce(func.cast("summary", Text), "")
                + " "
                + func.coalesce(func.cast("content", Text), ""),
            ),
            postgresql_using="gin",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(100), index=True)
    url: Mapped[str] = mapped_column(String(1000), unique=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
    sentiment_label: Mapped[str] = mapped_column(String(20), default="neutral")
    sentiment_score: Mapped[float] = mapped_column(Float, default=0.0)
    tags: Mapped[list] = mapped_column(JSON, default=list)
