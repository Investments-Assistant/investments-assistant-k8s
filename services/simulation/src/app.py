"""Simulation agent service: backtesting and strategy simulation."""

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
    logger.info("Simulation agent starting")
    await create_all_tables()
    yield


app = FastAPI(
    title="Simulation Agent",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,
    redoc_url=None,
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "simulation"}


@app.post("/tools/invoke")
async def invoke_tool(request: Request) -> dict:
    body = await request.json()
    tool_name = body.get("tool_name")
    if not tool_name:
        raise HTTPException(400, "Missing tool_name")
    tool_input = body.get("tool_input", {})

    if tool_name != "run_simulation":
        return {"result": json.dumps({"error": f"Unknown tool: {tool_name}"})}

    from src.tools.simulator import run_simulation

    try:
        result = run_simulation(**tool_input)
        # Persist to DB
        if "error" not in result:
            await _persist(result)
    except Exception as exc:
        logger.exception("run_simulation failed")
        result = {"error": str(exc)}

    return {"result": json.dumps(result, default=str)}


async def _persist(result: dict) -> None:
    try:
        from src.db.database import async_session
        from src.db.models import SimulationResult

        async with async_session() as session:
            sim = SimulationResult(
                name=result["name"],
                strategy=result["strategy"],
                initial_capital=result["initial_capital"],
                final_value=result["final_value"],
                total_return_pct=result.get("total_return_pct", 0.0),
                sharpe_ratio=result.get("sharpe_ratio"),
                max_drawdown_pct=result.get("max_drawdown_pct"),
                trades_count=result["trades_count"],
                period_start=result["period_start"],
                period_end=result["period_end"],
                equity_curve=result["equity_curve"],
            )
            session.add(sim)
            await session.commit()
            result["simulation_id"] = sim.id
            logger.info("Simulation '%s' persisted (id=%s)", sim.name, sim.id)
    except Exception as exc:
        logger.warning("Failed to persist simulation: %s", exc)
