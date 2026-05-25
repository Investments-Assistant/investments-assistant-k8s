"""Gateway HTTP routes: REST API, WebSocket chat, and chat UI."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from src.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

STATIC_DIR = Path(__file__).parent / "static"


# ── IP whitelist ───────────────────────────────────────────────────────────────


def _client_ip(req: Request | WebSocket) -> str:
    if isinstance(req, Request):
        headers = req.headers
        client = req.client
    else:
        headers = req.headers
        client = req.client
    xff = headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return client.host if client else "0.0.0.0"


def require_ip(request: Request) -> None:
    ip = _client_ip(request)
    if not settings.is_development and not settings.is_ip_allowed(ip):
        logger.warning("Blocked %s", ip)
        raise HTTPException(status_code=403, detail="Access denied")


# ── WebSocket chat ─────────────────────────────────────────────────────────────


@router.websocket("/ws/chat/{session_id}")
async def ws_chat(websocket: WebSocket, session_id: str) -> None:
    ip = _client_ip(websocket)
    if not settings.is_development and not settings.is_ip_allowed(ip):
        await websocket.close(code=4003, reason="Access denied")
        return

    await websocket.accept()
    logger.info("WS connected session=%s ip=%s", session_id, ip)

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

            async for event in session.chat(user_msg):
                await websocket.send_json(event)

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
        "services": {
            "market_data": settings.market_data_url,
            "news": settings.news_url,
            "portfolio": settings.portfolio_url,
            "simulation": settings.simulation_url,
            "scheduler": settings.scheduler_url,
            "forex": settings.forex_url,
        },
    }


@router.get("/api/market/snapshot", dependencies=[Depends(require_ip)])
async def market_snapshot() -> dict:
    """Return the latest cached market snapshot (served by the scheduler service)."""
    from src.agent.router import get_router

    result_str = await get_router().dispatch("get_market_overview", {})
    try:
        return json.loads(result_str)
    except json.JSONDecodeError:
        return {"raw": result_str}


@router.get("/api/reports", dependencies=[Depends(require_ip)])
async def list_reports() -> list[dict]:
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


@router.get("/api/trades", dependencies=[Depends(require_ip)])
async def list_trades(limit: int = 50) -> list[dict]:
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


@router.post("/api/autonomous-scan", dependencies=[Depends(require_ip)])
async def trigger_autonomous_scan(request: Request) -> dict:
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
        async for event in session.chat(prompt):
            if event["type"] == "text_delta":
                text_parts.append(event["text"])
        return {"status": "ok", "summary": "".join(text_parts)[:500]}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# ── Chat UI ───────────────────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse, dependencies=[Depends(require_ip)])
async def chat_ui() -> HTMLResponse:
    return HTMLResponse(content=(STATIC_DIR / "index.html").read_text(), status_code=200)
