"""Scheduler service: APScheduler + report listing + on-demand report generation."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from src.config import settings
from src.db.database import create_all_tables
from src.jobs import setup_scheduler, shutdown_scheduler

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Scheduler service starting")
    await create_all_tables()
    setup_scheduler()
    yield
    shutdown_scheduler()
    logger.info("Scheduler service stopped")


app = FastAPI(
    title="Scheduler Service",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,
    redoc_url=None,
)


@app.get("/health")
async def health() -> dict:
    from src.jobs import scheduler

    return {
        "status": "ok",
        "service": "scheduler",
        "jobs": [
            {"id": j.id, "next_run": str(j.next_run_time)} for j in scheduler.get_jobs()
        ],
    }


@app.get("/reports")
async def list_reports(limit: int = 20) -> list[dict]:
    from sqlalchemy import desc, select
    from src.db.database import async_session
    from src.db.models import Report

    try:
        async with async_session() as session:
            rows = (
                (
                    await session.execute(
                        select(Report).order_by(desc(Report.created_at)).limit(limit)
                    )
                )
                .scalars()
                .all()
            )
        return [
            {
                "id": r.id,
                "title": r.title,
                "period_start": r.period_start.isoformat(),
                "period_end": r.period_end.isoformat(),
                "pdf_available": r.pdf_path is not None,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


@app.post("/reports/generate")
async def generate_on_demand(period_start: str, period_end: str | None = None) -> dict:
    from src.reporter import generate_report

    return await generate_report(period_start=period_start, period_end=period_end)


@app.post("/tools/invoke")
async def invoke_tool_generate_report(body: dict) -> dict:
    """Accepts generate_report tool calls from the gateway."""
    import json

    tool_name = body.get("tool_name")
    if tool_name != "generate_report":
        return {"result": json.dumps({"error": f"Unknown tool: {tool_name}"})}
    tool_input = body.get("tool_input", {})
    from src.reporter import generate_report

    try:
        result = await generate_report(**tool_input)
    except Exception as exc:
        result = {"error": str(exc)}
    return {"result": json.dumps(result, default=str)}
