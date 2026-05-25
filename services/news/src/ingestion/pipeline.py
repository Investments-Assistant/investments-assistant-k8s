"""Ingestion pipeline: fetch from all sources and persist to PostgreSQL."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.db.database import async_session
from src.db.models import NewsArticle
from src.ingestion.sources import fetch_all

logger = logging.getLogger(__name__)


async def ingest_articles(articles: list[dict[str, Any]]) -> int:
    if not articles:
        return 0
    rows = [
        {
            "title": a["title"],
            "summary": a.get("summary", ""),
            "content": a.get("content"),
            "source": a["source"],
            "url": a["url"],
            "published_at": a.get("published_at"),
            "sentiment_label": a.get("sentiment_label", "neutral"),
            "sentiment_score": a.get("sentiment_score", 0.0),
            "tags": a.get("tags", []),
        }
        for a in articles
        if a.get("url")
    ]
    if not rows:
        return 0
    async with async_session() as session:
        stmt = (
            pg_insert(NewsArticle)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["url"])
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount or 0


async def run_ingestion(days_back: int = 1) -> dict:
    logger.info("News ingestion started (days_back=%d)", days_back)
    try:
        articles = await fetch_all(days_back=days_back)
        inserted = await ingest_articles(articles)
        logger.info("Ingestion done: fetched=%d new=%d", len(articles), inserted)
        return {"fetched": len(articles), "inserted": inserted}
    except Exception as exc:
        logger.error("Ingestion failed: %s", exc)
        return {"fetched": 0, "inserted": 0, "error": str(exc)}
