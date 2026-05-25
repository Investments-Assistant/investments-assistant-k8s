"""News source adapters: RSS, The Guardian API, web scraping."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging
import re
from typing import Any

import feedparser
import aiohttp

from src.config import settings

logger = logging.getLogger(__name__)

RSS_FEEDS: dict[str, str] = {
    "Reuters Business": "https://feeds.reuters.com/reuters/businessNews",
    "Reuters Markets": "https://feeds.reuters.com/reuters/financialsNews",
    "CNBC": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "MarketWatch": "https://feeds.marketwatch.com/marketwatch/topstories/",
    "Yahoo Finance": "https://finance.yahoo.com/rss/topstories",
    "Bloomberg Markets": "https://feeds.bloomberg.com/markets/news.rss",
    "Financial Times": "https://www.ft.com/world?format=rss",
    "The Economist – Finance": "https://www.economist.com/finance-and-economics/rss.xml",
    "WSJ Markets": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "AP Business": "https://feeds.apnews.com/apf-business",
    "Coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "CryptoNews": "https://cryptonews.com/news/feed/",
    "The Block": "https://www.theblock.co/rss.xml",
    "Decrypt": "https://decrypt.co/feed",
    "ECB Press": "https://www.ecb.europa.eu/rss/press.html",
    "Jornal de Negócios": "https://www.jornaldenegocios.pt/rss/",
    "Dinheiro Vivo": "https://www.dinheirovivo.pt/feed/",
    "ECO Portugal": "https://eco.pt/feed/",
}

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
    "high",
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
_TICKER_RE = re.compile(r"\b([A-Z]{1,5})\b")
_KNOWN_TICKERS = {
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "NVDA",
    "TSLA",
    "META",
    "SPY",
    "QQQ",
    "VTI",
    "GLD",
    "BTC",
    "ETH",
    "SOL",
    "BNB",
    "EUR",
    "USD",
    "GBP",
    "JPY",
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


def _extract_tags(text: str) -> list[str]:
    return sorted(set(_TICKER_RE.findall(text)) & _KNOWN_TICKERS)


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    import email.utils

    try:
        return email.utils.parsedate_to_datetime(value).astimezone(UTC)
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value[:25], fmt)
            return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
        except ValueError:
            pass
    return None


def _article(
    title: str,
    summary: str,
    source: str,
    url: str,
    published_raw: str = "",
    content: str | None = None,
) -> dict[str, Any]:
    full = f"{title} {summary} {content or ''}"
    label, score = _sentiment(full)
    return {
        "title": title[:500],
        "summary": summary[:2000],
        "content": content,
        "source": source,
        "url": url,
        "published_at": _parse_date(published_raw),
        "sentiment_label": label,
        "sentiment_score": score,
        "tags": _extract_tags(full),
    }


def fetch_rss(max_per_feed: int = 20) -> list[dict[str, Any]]:
    articles: list[dict[str, Any]] = []
    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                link = getattr(entry, "link", "") or ""
                if not link:
                    continue
                articles.append(
                    _article(
                        getattr(entry, "title", "") or "",
                        getattr(entry, "summary", "") or "",
                        source,
                        link,
                        getattr(entry, "published", "") or "",
                    )
                )
        except Exception as exc:
            logger.debug("RSS %s failed: %s", source, exc)
    return articles


async def fetch_guardian(days_back: int = 1) -> list[dict[str, Any]]:
    if not settings.guardian_api_key:
        return []
    since = (datetime.now(UTC) - timedelta(days=days_back)).strftime("%Y-%m-%d")
    articles: list[dict[str, Any]] = []
    async with aiohttp.ClientSession() as client:
        for section in ["business", "money", "technology", "world"]:
            try:
                async with client.get(
                    "https://content.guardianapis.com/search",
                    params={
                        "api-key": settings.guardian_api_key,
                        "section": section,
                        "from-date": since,
                        "page-size": 50,
                        "show-fields": "bodyText,trailText",
                        "order-by": "newest",
                    },
                ) as resp:
                    for item in (
                        (await resp.json()).get("response", {}).get("results", [])
                    ):
                        f = item.get("fields", {})
                        body = f.get("bodyText", "")
                        articles.append(
                            _article(
                                item.get("webTitle", ""),
                                f.get("trailText", body[:500]),
                                "The Guardian",
                                item.get("webUrl", ""),
                                item.get("webPublicationDate", ""),
                                body[:5000] or None,
                            )
                        )
            except Exception as exc:
                logger.warning("Guardian section=%s failed: %s", section, exc)
    return articles


async def fetch_all(days_back: int = 1) -> list[dict[str, Any]]:
    results = fetch_rss() + await fetch_guardian(days_back=days_back)
    seen: set[str] = set()
    deduped = []
    for a in results:
        u = a.get("url", "").strip()
        if u and u not in seen:
            seen.add(u)
            deduped.append(a)
    return deduped
