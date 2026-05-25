"""Portfolio agent service: account info, trade execution, safety guards."""

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
    logger.info("Portfolio agent starting (mode=%s)", settings.trading_mode)
    await create_all_tables()
    yield
    logger.info("Portfolio agent stopped")


app = FastAPI(
    title="Portfolio Agent",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,
    redoc_url=None,
)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "portfolio",
        "external_api_access": settings.external_api_access,
    }


@app.post("/tools/invoke")
async def invoke_tool(request: Request) -> dict:
    body = await request.json()
    tool_name = body.get("tool_name")
    if not tool_name:
        raise HTTPException(400, "Missing tool_name")
    tool_input = body.get("tool_input", {})

    local_tools = {"get_trade_history"}
    if tool_name not in local_tools and not settings.external_api_access:
        return {
            "result": json.dumps(
                {
                    "error": "External API access is disabled for portfolio broker calls.",
                    "tool": tool_name,
                }
            )
        }

    from src.tools.dispatcher import cancel_order, confirm_trade, execute_trade
    from src.tools.portfolio import (
        get_account_info,
        get_portfolio_summary,
        get_trade_history,
    )

    SYNC = {
        "get_portfolio_summary": lambda i: get_portfolio_summary(
            broker=i.get("broker")
        ),
        "get_account_info": lambda i: get_account_info(broker=i["broker"]),
        "cancel_order": lambda i: cancel_order(i["broker"], i["order_id"]),
    }
    ASYNC = {
        "get_trade_history": lambda i: get_trade_history(**i),
        "execute_trade": lambda i: execute_trade(i),
        "confirm_trade": lambda i: confirm_trade(i),
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
        result = {"error": str(exc)}

    return {"result": json.dumps(result, default=str)}


@app.get("/trades")
async def list_trades(limit: int = 50) -> list[dict]:
    """Direct trades listing endpoint (used by gateway /api/trades proxy)."""
    from sqlalchemy import desc, select
    from src.db.database import async_session
    from src.db.models import Trade

    try:
        async with async_session() as session:
            rows = (
                (
                    await session.execute(
                        select(Trade).order_by(desc(Trade.created_at)).limit(limit)
                    )
                )
                .scalars()
                .all()
            )
        return [
            {
                "id": t.id,
                "broker": t.broker,
                "symbol": t.symbol,
                "side": t.side,
                "quantity": t.quantity,
                "price": t.price,
                "order_type": t.order_type,
                "status": t.status,
                "mode": t.mode,
                "reason": t.reason,
                "created_at": t.created_at.isoformat(),
            }
            for t in rows
        ]
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc
