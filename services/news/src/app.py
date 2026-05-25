"""News agent service: ingestion pipeline + full-text search."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from src.config import settings
from src.db.database import create_all_tables

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("News agent starting")
    await create_all_tables()
    yield
    logger.info("News agent stopped")


app = FastAPI(
    title="News Agent",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,
    redoc_url=None,
)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "news",
        "external_api_access": settings.external_api_access,
    }


@app.post("/tools/invoke")
async def invoke_tool(request: Request) -> dict:
    body = await request.json()
    tool_name = body.get("tool_name")
    if not tool_name:
        raise HTTPException(400, "Missing tool_name")
    tool_input = body.get("tool_input", {})

    external_tools = {"search_market_news"}
    if tool_name in external_tools and not settings.external_api_access:
        return {
            "result": json.dumps(
                {
                    "error": "External API access is disabled for news.",
                    "tool": tool_name,
                }
            )
        }

    from src.tools.news import search_market_news
    from src.tools.news_memory import get_latest_news, search_stored_news

    SYNC = {"search_market_news": lambda i: search_market_news(**i)}
    ASYNC = {
        "search_stored_news": lambda i: search_stored_news(**i),
        "get_latest_news": lambda i: get_latest_news(limit=i.get("limit", 20)),
    }

    try:
        if tool_name in SYNC:
            result = SYNC[tool_name](tool_input)
        elif tool_name in ASYNC:
            result = await ASYNC[tool_name](tool_input)
        else:
            result = {"error": f"Unknown tool: {tool_name}"}
    except Exception as exc:
        logger.exception("Tool %s failed", tool_name)
        result = {"error": str(exc), "tool": tool_name}

    return {"result": json.dumps(result, default=str)}


@app.post("/ingest")
async def trigger_ingestion(days_back: int = 1) -> dict:
    """Trigger a manual news ingestion run (called by the scheduler)."""
    if not settings.external_api_access:
        return {
            "status": "skipped",
            "reason": "External API access is disabled for news ingestion.",
        }

    from src.ingestion.pipeline import run_ingestion

    return await run_ingestion(days_back=days_back)


@app.post("/ingest/newsletters")
async def trigger_newsletter_ingestion(since_days: int = 7) -> dict:
    if not settings.external_api_access:
        return {
            "status": "skipped",
            "reason": "External API access is disabled for newsletter ingestion.",
        }

    from src.ingestion.email_reader import read_and_ingest_newsletters

    return await read_and_ingest_newsletters(since_days=since_days)
