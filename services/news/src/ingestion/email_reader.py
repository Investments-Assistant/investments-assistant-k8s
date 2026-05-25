"""Read newsletters from IMAP and ingest them as articles."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import email
import imaplib
import logging
from typing import Any

from src.config import settings
from src.ingestion.pipeline import ingest_articles

logger = logging.getLogger(__name__)


def _fetch_emails(since_days: int = 7) -> list[dict[str, Any]]:
    if not (settings.newsletter_email_user and settings.newsletter_email_password):
        return []
    try:
        imap = imaplib.IMAP4_SSL(
            settings.newsletter_imap_server, settings.newsletter_imap_port
        )
        imap.login(settings.newsletter_email_user, settings.newsletter_email_password)
        imap.select("INBOX")
        since_date = (datetime.now(UTC) - timedelta(days=since_days)).strftime(
            "%d-%b-%Y"
        )
        criteria = [f"SINCE {since_date}"]
        if settings.newsletter_sender_filter:
            criteria.append(f'FROM "{settings.newsletter_sender_filter}"')
        _, ids = imap.search(None, *criteria)
        articles: list[dict[str, Any]] = []
        for msg_id in (ids[0].split() if ids[0] else [])[:50]:
            try:
                _, data = imap.fetch(msg_id, "(RFC822)")
                raw = data[0][1]  # type: ignore[index]
                msg = email.message_from_bytes(raw)
                subject = msg.get("Subject", "Newsletter")
                sender = msg.get(
                    "From", settings.newsletter_sender_filter or "newsletter"
                )
                source_name = f"Newsletter: {sender[:50]}"
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode(
                                "utf-8", errors="ignore"
                            )
                            break
                else:
                    body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
                uid = msg.get("Message-ID") or f"{sender}-{subject}"
                articles.append(
                    {
                        "title": subject[:500],
                        "summary": body[:500],
                        "content": body[:10000],
                        "source": source_name,
                        "url": f"email://{uid[:200]}",
                        "published_at": datetime.now(UTC),
                        "sentiment_label": "neutral",
                        "sentiment_score": 0.0,
                        "tags": [],
                    }
                )
            except Exception as exc:
                logger.debug("Failed to parse email %s: %s", msg_id, exc)
        imap.logout()
        return articles
    except Exception as exc:
        logger.warning("IMAP fetch failed: %s", exc)
        return []


async def read_and_ingest_newsletters(since_days: int = 7) -> dict:
    articles = await asyncio.get_event_loop().run_in_executor(
        None, lambda: _fetch_emails(since_days)
    )
    inserted = await ingest_articles(articles) if articles else 0
    return {"fetched": len(articles), "inserted": inserted}
