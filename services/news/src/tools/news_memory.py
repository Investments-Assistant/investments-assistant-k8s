"""Full-text search over the persisted news article store."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging

from sqlalchemy import desc, select, text

from src.db.database import async_session
from src.db.models import NewsArticle

logger = logging.getLogger(__name__)


async def search_stored_news(
    query: str,
    days_back: int = 30,
    sources: list[str] | None = None,
    sentiment: str | None = None,
    limit: int = 20,
) -> dict:
    try:
        async with async_session() as session:
            stmt = select(NewsArticle)
            if days_back > 0:
                since = datetime.now(UTC) - timedelta(days=days_back)
                stmt = stmt.where(NewsArticle.published_at >= since)
            if sources:
                stmt = stmt.where(NewsArticle.source.in_(sources))
            if sentiment:
                stmt = stmt.where(NewsArticle.sentiment_label == sentiment)
            # PostgreSQL full-text search
            ts_query = " & ".join(query.split())
            stmt = stmt.where(
                text(
                    "to_tsvector('english', coalesce(title,'') || ' ' || coalesce(summary,'')) "
                    "@@ to_tsquery('english', :q)"
                ).bindparams(q=ts_query)
            )
            stmt = stmt.order_by(desc(NewsArticle.published_at)).limit(limit)
            rows = (await session.execute(stmt)).scalars().all()
            return {
                "query": query,
                "count": len(rows),
                "articles": [
                    {
                        "title": r.title,
                        "summary": r.summary[:300],
                        "source": r.source,
                        "url": r.url,
                        "published_at": r.published_at.isoformat()
                        if r.published_at
                        else None,
                        "sentiment": r.sentiment_label,
                        "sentiment_score": r.sentiment_score,
                        "tags": r.tags,
                    }
                    for r in rows
                ],
            }
    except Exception as exc:
        logger.exception("search_stored_news failed")
        return {"query": query, "error": str(exc), "articles": []}


async def get_latest_news(limit: int = 20) -> dict:
    try:
        async with async_session() as session:
            rows = (
                (
                    await session.execute(
                        select(NewsArticle)
                        .order_by(desc(NewsArticle.fetched_at))
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )
            return {
                "count": len(rows),
                "articles": [
                    {
                        "title": r.title,
                        "source": r.source,
                        "published_at": r.published_at.isoformat()
                        if r.published_at
                        else None,
                        "sentiment": r.sentiment_label,
                        "url": r.url,
                    }
                    for r in rows
                ],
            }
    except Exception as exc:
        logger.exception("get_latest_news failed")
        return {"error": str(exc), "articles": []}
