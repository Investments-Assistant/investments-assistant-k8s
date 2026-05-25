"""Forex agent service — FX rates, carry-trade analysis."""

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
    logger.info("Forex agent starting")
    yield
    logger.info("Forex agent stopped")


app = FastAPI(
    title="Forex Agent",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,
    redoc_url=None,
)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "forex",
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
                    "error": "External API access is disabled for forex.",
                    "tool": tool_name,
                }
            )
        }

    from src.tools.forex import get_central_bank_rates, get_forex_data, get_forex_rates

    DISPATCH = {
        "get_forex_data": lambda i: get_forex_data(**i),
        "get_forex_rates": lambda i: get_forex_rates(pairs=i.get("pairs")),
        "get_central_bank_rates": lambda i: get_central_bank_rates(
            currencies=i.get("currencies")
        ),
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
