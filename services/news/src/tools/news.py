"""Live news search tool: NewsAPI + sentiment analysis."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from src.config import settings

logger = logging.getLogger(__name__)

_POSITIVE = {
    "surge",
    "rally",
    "gain",
    "rise",
    "soar",
    "boom",
    "bull",
    "strong",
    "beat",
    "record",
    "growth",
    "profit",
    "upbeat",
    "upgrade",
    "buy",
    "outperform",
    "recovery",
}
_NEGATIVE = {
    "fall",
    "drop",
    "crash",
    "plunge",
    "decline",
    "loss",
    "bear",
    "weak",
    "miss",
    "low",
    "recession",
    "downgrade",
    "sell",
    "underperform",
    "concern",
    "risk",
    "fear",
    "inflation",
    "default",
    "bankruptcy",
    "layoff",
    "cut",
}


def _sentiment(text: str) -> tuple[str, float]:
    words = set(re.findall(r"\b\w+\b", text.lower()))
    pos, neg = len(words & _POSITIVE), len(words & _NEGATIVE)
    total = pos + neg
    if total == 0:
        return "neutral", 0.0
    score = round((pos - neg) / total, 3)
    if score > 0.15:
        return "bullish", score
    if score < -0.15:
        return "bearish", score
    return "neutral", score


def search_market_news(
    query: str,
    max_articles: int = 10,
    sources: list[str] | None = None,
) -> dict:
    """Search NewsAPI for financial news with sentiment analysis."""
    articles: list[dict] = []

    if settings.newsapi_key:
        try:
            from newsapi import NewsApiClient

            client = NewsApiClient(api_key=settings.newsapi_key)
            kwargs: dict = {
                "q": query,
                "language": "en",
                "sort_by": "publishedAt",
                "page_size": min(max_articles, 20),
            }
            if sources:
                kwargs["sources"] = ",".join(sources)
            resp = client.get_everything(**kwargs)
            for art in resp.get("articles", [])[:max_articles]:
                text = f"{art.get('title', '')} {art.get('description', '')} {art.get('content', '')}"
                label, score = _sentiment(text)
                articles.append(
                    {
                        "title": art.get("title", ""),
                        "summary": art.get("description", ""),
                        "source": art.get("source", {}).get("name", ""),
                        "url": art.get("url", ""),
                        "published_at": art.get("publishedAt", ""),
                        "sentiment": label,
                        "sentiment_score": score,
                    }
                )
        except Exception as exc:
            logger.warning("NewsAPI failed: %s", exc)

    if not articles:
        articles.append(
            {
                "title": f"News search: {query}",
                "summary": "NewsAPI key not configured or request failed.",
                "source": "system",
                "url": "",
                "published_at": datetime.now(UTC).isoformat(),
                "sentiment": "neutral",
                "sentiment_score": 0.0,
            }
        )

    return {
        "query": query,
        "count": len(articles),
        "articles": articles,
        "timestamp": datetime.now(UTC).isoformat(),
    }
