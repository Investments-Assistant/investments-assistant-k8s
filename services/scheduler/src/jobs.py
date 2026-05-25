"""APScheduler background jobs: news ingestion, market refresh, reports, autonomous scans."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging

import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.config import settings

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

_TIMEOUT = aiohttp.ClientTimeout(total=30)


async def _post(url: str, **kwargs) -> dict:
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as s:
            async with s.post(url, **kwargs) as resp:
                return await resp.json()
    except Exception as exc:
        logger.warning("POST %s failed: %s", url, exc)
        return {"error": str(exc)}


async def _get(url: str) -> dict:
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as s:
            async with s.get(url) as resp:
                return await resp.json()
    except Exception as exc:
        logger.warning("GET %s failed: %s", url, exc)
        return {"error": str(exc)}


async def _ingest_news() -> None:
    logger.info("Scheduled: news ingestion")
    result = await _post(f"{settings.news_url}/ingest", params={"days_back": 1})
    logger.info("News ingestion result: %s", result)


async def _ingest_newsletters() -> None:
    logger.info("Scheduled: newsletter ingestion")
    result = await _post(
        f"{settings.news_url}/ingest/newsletters", params={"since_days": 8}
    )
    logger.info("Newsletter ingestion result: %s", result)


async def _refresh_market_data() -> None:
    """Pull market overview and cache it in Redis via market-data service."""
    logger.info("Scheduled: market data refresh")
    result = await _post(
        f"{settings.market_data_url}/tools/invoke",
        json={"tool_name": "get_market_overview", "tool_input": {}},
    )
    logger.debug("Market refresh result: %s", str(result)[:200])


async def _weekly_report() -> None:
    logger.info("Scheduled: weekly report")
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    start = (datetime.now(UTC) - timedelta(days=7)).strftime("%Y-%m-%d")
    result = await _post(
        f"{settings.gateway_url}/api/autonomous-scan",
        json={},
    )
    # Also trigger a formal report generation
    from src.reporter import generate_report

    await generate_report(period_start=start, period_end=today)
    logger.info("Weekly report done: %s", str(result)[:200])


async def _autonomous_scan() -> None:
    logger.info("Scheduled: autonomous scan")
    result = await _post(f"{settings.gateway_url}/api/autonomous-scan", json={})
    logger.info("Autonomous scan result: %s", str(result)[:200])


def setup_scheduler() -> None:
    scheduler.add_job(
        _refresh_market_data,
        IntervalTrigger(minutes=settings.market_data_refresh_minutes),
        id="market_refresh",
        replace_existing=True,
        misfire_grace_time=60,
    )

    scheduler.add_job(
        _weekly_report,
        CronTrigger(
            day_of_week=settings.weekly_report_day,
            hour=settings.weekly_report_hour,
            minute=settings.weekly_report_minute,
            timezone="UTC",
        ),
        id="weekly_report",
        replace_existing=True,
    )

    scheduler.add_job(
        _autonomous_scan,
        CronTrigger(day_of_week="mon-fri", hour="14-21", minute="*/30", timezone="UTC"),
        id="autonomous_scan",
        replace_existing=True,
    )

    scheduler.add_job(
        _ingest_news,
        IntervalTrigger(minutes=30),
        id="news_ingestion",
        replace_existing=True,
        misfire_grace_time=120,
    )

    scheduler.add_job(
        _ingest_newsletters,
        CronTrigger(day_of_week="sat", hour=9, minute=0, timezone="UTC"),
        id="newsletter_ingestion",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started (%d jobs)", len(scheduler.get_jobs()))


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
