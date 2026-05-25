"""Gateway service entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.config import settings
from src.db.database import create_all_tables
from src.web.routes import STATIC_DIR, router

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Gateway starting (env=%s model=%s mode=%s)",
        settings.environment,
        settings.llm_model_name,
        settings.trading_mode,
    )
    # Create gateway-owned tables (chat_messages, analyses)
    await create_all_tables()

    # Start the HTTP client pool used by AgentRouter
    from src.agent.router import get_router

    await get_router().start()

    # Sync trading_mode from Redis if set (supports runtime changes persisted across restarts)
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        stored_mode = await r.get("trading_mode")
        if stored_mode in ("recommend", "auto"):
            settings.trading_mode = stored_mode  # type: ignore[misc]
            logger.info("Loaded trading_mode from Redis: %s", stored_mode)
        await r.aclose()
    except Exception as exc:
        logger.warning("Could not read trading_mode from Redis: %s", exc)

    yield

    await get_router().stop()
    logger.info("Gateway shut down")


app = FastAPI(
    title="Investment Assistant — Gateway",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.is_development else None,
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(router)
