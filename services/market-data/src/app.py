"""Market-Data agent service."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from src.config import settings

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Market-data agent starting")
    yield
    logger.info("Market-data agent stopped")


app = FastAPI(
    title="Market-Data Agent",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,
    redoc_url=None,
)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "market-data",
        "external_api_access": settings.external_api_access,
    }


@app.post("/tools/invoke")
async def invoke_tool(request: Request) -> dict:
    """Dispatch a tool call from the gateway."""
    body = await request.json()
    tool_name = body.get("tool_name")
    if not tool_name:
        raise HTTPException(400, "Missing tool_name")
    tool_input = body.get("tool_input", {})

    if not settings.external_api_access:
        return {
            "result": json.dumps(
                {
                    "error": "External API access is disabled for market-data.",
                    "tool": tool_name,
                }
            )
        }

    from src.tools.market_data import (
        get_crypto_data,
        get_earnings_calendar,
        get_market_overview,
        get_options_chain,
        get_stock_data,
        get_technical_indicators,
        search_ticker,
    )

    DISPATCH = {
        "get_stock_data": lambda i: get_stock_data(**i),
        "get_crypto_data": lambda i: get_crypto_data(**i),
        "get_market_overview": lambda _: get_market_overview(),
        "get_technical_indicators": lambda i: get_technical_indicators(**i),
        "get_options_chain": lambda i: get_options_chain(**i),
        "search_ticker": lambda i: search_ticker(**i),
        "get_earnings_calendar": lambda i: get_earnings_calendar(**i),
    }

    fn = DISPATCH.get(tool_name)
    if not fn:
        return {"result": json.dumps({"error": f"Unknown tool: {tool_name}"})}

    try:
        result = fn(tool_input)
    except Exception as exc:
        logger.exception("Tool %s failed", tool_name)
        result = {"error": str(exc), "tool": tool_name}

    return {"result": json.dumps(result, default=str)}
