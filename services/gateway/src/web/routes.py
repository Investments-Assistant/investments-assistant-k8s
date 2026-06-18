"""Gateway HTTP routes: REST API, WebSocket chat, and chat UI."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse

from src.auth import (
    AuthContext,
    WebSocketAuthError,
    authenticate_websocket,
    require_access,
    require_permission,
)
from src.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

STATIC_DIR = Path(__file__).parent / "static"
WS_KEEPALIVE_SECONDS = 15


# ── WebSocket chat ─────────────────────────────────────────────────────────────


async def _send_chat_events(
    websocket: WebSocket,
    session,
    user_msg: str,
    auth_context: AuthContext,
) -> None:
    queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def produce() -> None:
        try:
            async for event in session.chat(user_msg, auth_context=auth_context):
                await queue.put(event)
        except Exception as exc:
            logger.exception("Chat stream failed")
            await queue.put({"type": "error", "message": str(exc)})
        finally:
            await queue.put(None)

    producer = asyncio.create_task(produce())
    try:
        await websocket.send_json({"type": "status", "message": "thinking"})
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=WS_KEEPALIVE_SECONDS)
            except TimeoutError:
                await websocket.send_json({"type": "status", "message": "thinking"})
                continue

            if event is None:
                return
            await websocket.send_json(event)
    finally:
        if not producer.done():
            producer.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await producer


@router.websocket("/ws/chat/{session_id}")
async def ws_chat(websocket: WebSocket, session_id: str) -> None:
    try:
        auth_context = authenticate_websocket(websocket)
    except WebSocketAuthError as exc:
        await websocket.close(code=4003, reason=exc.reason)
        return

    await websocket.accept()
    logger.info(
        "WS connected session=%s user=%s role=%s",
        session_id,
        auth_context.username,
        auth_context.role,
    )

    from src.agent.orchestrator import get_or_create_session

    session = get_or_create_session(session_id)
    await session.load_history()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                user_msg = json.loads(raw).get("message", "").strip()
            except json.JSONDecodeError:
                user_msg = raw.strip()
            if not user_msg:
                continue

            await _send_chat_events(websocket, session, user_msg, auth_context)

    except WebSocketDisconnect:
        logger.info("WS disconnected session=%s", session_id)
    except Exception as exc:
        logger.exception("WS error: %s", exc)
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass


# ── REST API ──────────────────────────────────────────────────────────────────


@router.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "timestamp": datetime.now(UTC).isoformat(),
        "trading_mode": settings.trading_mode,
        "model": settings.llm_model_name,
        "auth_mode": settings.auth_mode,
        "services": {
            "market_data": settings.market_data_url,
            "news": settings.news_url,
            "portfolio": settings.portfolio_url,
            "simulation": settings.simulation_url,
            "scheduler": settings.scheduler_url,
            "forex": settings.forex_url,
        },
    }


@router.get("/api/me")
async def current_user(auth: AuthContext = Depends(require_access)) -> dict:
    return auth.to_public_dict()


@router.get("/api/market/snapshot")
async def market_snapshot(
    auth: AuthContext = Depends(require_permission("market")),
) -> dict:
    """Return the latest cached market snapshot (served by the scheduler service)."""
    from src.agent.router import get_router

    result_str = await get_router().dispatch(
        "get_market_overview",
        {},
        auth_context=auth,
    )
    try:
        return json.loads(result_str)
    except json.JSONDecodeError:
        return {"raw": result_str}


@router.get("/api/reports")
async def list_reports(
    auth: AuthContext = Depends(require_permission("reports")),
) -> list[dict]:
    """Proxy to scheduler service for report listing."""
    try:
        import aiohttp

        async with aiohttp.ClientSession() as s:
            async with s.get(f"{settings.scheduler_url}/reports") as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception:
        pass
    return []


async def _fetch_trades(limit: int = 50) -> list[dict]:
    """Proxy to portfolio service for trade listing."""
    try:
        import aiohttp

        async with aiohttp.ClientSession() as s:
            async with s.get(f"{settings.portfolio_url}/trades?limit={limit}") as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception:
        pass
    return []


@router.get("/api/trades")
async def list_trades(
    limit: int = 50,
    auth: AuthContext = Depends(require_permission("portfolio")),
) -> list[dict]:
    return await _fetch_trades(limit)


@router.get("/api/chat/{session_id}/messages")
async def chat_history(
    session_id: str,
    limit: int = 200,
    auth: AuthContext = Depends(require_permission("chat")),
) -> list[dict]:
    """Return persisted chat history for the browser session."""
    from sqlalchemy import desc, select

    from src.db.database import async_session
    from src.db.models import ChatMessage

    safe_limit = max(1, min(limit, 500))
    async with async_session() as session:
        rows = (
            (
                await session.execute(
                    select(ChatMessage)
                    .where(ChatMessage.session_id == session_id)
                    .order_by(desc(ChatMessage.created_at))
                    .limit(safe_limit)
                )
            )
            .scalars()
            .all()
        )

    return [
        {
            "id": row.id,
            "role": row.role,
            "content": row.content,
            "created_at": row.created_at.isoformat(),
        }
        for row in reversed(rows)
    ]


@router.get("/api/portfolio/dashboard")
async def portfolio_dashboard(
    auth: AuthContext = Depends(require_permission("portfolio")),
) -> dict:
    """Portfolio dashboard payload: current broker summary plus recent trades."""
    from src.agent.router import get_router

    summary_str = await get_router().dispatch(
        "get_portfolio_summary",
        {},
        auth_context=auth,
    )
    try:
        summary = json.loads(summary_str)
    except json.JSONDecodeError:
        summary = {"error": "Portfolio summary returned non-JSON data.", "raw": summary_str}

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "summary": summary,
        "trades": await _fetch_trades(limit=20),
    }


@router.post("/api/autonomous-scan")
async def trigger_autonomous_scan(
    request: Request,
    auth: AuthContext = Depends(require_permission("admin")),
) -> dict:
    """Trigger an autonomous market scan (called by the scheduler)."""
    from src.agent.orchestrator import get_or_create_session

    session = get_or_create_session("autonomous_scanner")
    default_prompt = (
        "Perform a proactive market scan. Check market overview, scan for technical signals on "
        "major stocks and crypto. If you identify a compelling opportunity with a strong "
        "risk/reward profile, execute it (if in auto mode). Document your full reasoning."
    )
    try:
        payload = await request.json()
        prompt = payload.get("prompt") or default_prompt
    except Exception:
        prompt = default_prompt

    text_parts: list[str] = []
    try:
        async for event in session.chat(prompt, auth_context=auth):
            if event["type"] == "text_delta":
                text_parts.append(event["text"])
        return {"status": "ok", "summary": "".join(text_parts)[:500]}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# ── Chat UI ───────────────────────────────────────────────────────────────────


@router.get(
    "/",
    response_class=HTMLResponse,
    dependencies=[Depends(require_permission("chat"))],
)
async def chat_ui() -> str:
    return (STATIC_DIR / "index.html").read_text()
