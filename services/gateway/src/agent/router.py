"""AgentRouter — dispatches tool calls to the appropriate microservice via HTTP.

Each tool is owned by exactly one agent service. The gateway never runs tools
in-process; it forwards every call over the internal K8s network.
"""

from __future__ import annotations

import json
import logging

import aiohttp

from src.auth import AuthContext, can_call_tool
from src.config import settings

logger = logging.getLogger(__name__)

# Map from tool name → base URL of the owning service
_ROUTES: dict[str, str] = {
    # Market Data Agent
    "get_stock_data": settings.market_data_url,
    "get_crypto_data": settings.market_data_url,
    "get_market_overview": settings.market_data_url,
    "get_technical_indicators": settings.market_data_url,
    "get_options_chain": settings.market_data_url,
    "search_ticker": settings.market_data_url,
    "get_earnings_calendar": settings.market_data_url,
    # Forex Agent
    "get_forex_data": settings.forex_url,
    "get_forex_rates": settings.forex_url,
    "get_central_bank_rates": settings.forex_url,
    # News Agent
    "search_market_news": settings.news_url,
    "search_stored_news": settings.news_url,
    "get_latest_news": settings.news_url,
    # Portfolio Agent
    "get_portfolio_summary": settings.portfolio_url,
    "get_account_info": settings.portfolio_url,
    "get_trade_history": settings.portfolio_url,
    "execute_trade": settings.portfolio_url,
    "confirm_trade": settings.portfolio_url,
    "cancel_order": settings.portfolio_url,
    # Simulation Agent
    "run_simulation": settings.simulation_url,
    # Scheduler/Report Agent
    "generate_report": settings.scheduler_url,
}

# Tools handled locally in the gateway (no HTTP hop needed)
_LOCAL_TOOLS = {"set_trading_mode"}

_TIMEOUT = aiohttp.ClientTimeout(total=120)


class AgentRouter:
    """HTTP client that forwards tool calls to the owning service."""

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        self._session = aiohttp.ClientSession(timeout=_TIMEOUT)

    async def stop(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def dispatch(
        self,
        tool_name: str,
        tool_input: dict,
        auth_context: AuthContext | None = None,
    ) -> str:
        """Call the owning service and return a JSON string result."""
        if not can_call_tool(auth_context, tool_name):
            role = auth_context.role if auth_context else "unknown"
            return json.dumps(
                {"error": (f"Permission denied: role '{role}' cannot use tool '{tool_name}'.")}
            )

        if tool_name in _LOCAL_TOOLS:
            return await self._handle_local(tool_name, tool_input)

        base_url = _ROUTES.get(tool_name)
        if not base_url:
            return json.dumps({"error": f"No agent handles tool '{tool_name}'"})

        url = f"{base_url}/tools/invoke"
        logger.info("Routing %s → %s", tool_name, base_url)
        try:
            assert self._session is not None
            async with self._session.post(
                url,
                json={"tool_name": tool_name, "tool_input": tool_input},
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    return json.dumps({"error": f"Service returned {resp.status}: {text[:300]}"})
                data = await resp.json()
                return data.get("result", json.dumps({"error": "empty result"}))
        except aiohttp.ClientConnectorError as exc:
            logger.error("Cannot reach %s: %s", base_url, exc)
            return json.dumps({"error": f"Agent service unreachable: {base_url}"})
        except Exception as exc:
            logger.exception("AgentRouter error for %s", tool_name)
            return json.dumps({"error": str(exc)})

    async def _handle_local(self, tool_name: str, tool_input: dict) -> str:
        if tool_name == "set_trading_mode":
            return await _set_trading_mode(tool_input.get("mode", ""))
        return json.dumps({"error": f"Unknown local tool: {tool_name}"})


async def _set_trading_mode(mode: str) -> str:
    if mode not in ("recommend", "auto"):
        return json.dumps({"error": "mode must be 'recommend' or 'auto'"})

    # Persist in Redis so all gateway replicas and the portfolio service see the same value
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        await r.set("trading_mode", mode)
        await r.aclose()
    except Exception as exc:
        logger.warning("Failed to persist trading_mode to Redis: %s", exc)

    # Also update in-process for the current request
    settings.trading_mode = mode  # type: ignore[misc]

    return json.dumps(
        {
            "success": True,
            "trading_mode": mode,
            "message": f"Trading mode switched to '{mode}'.",
        }
    )


# Module-level singleton — created once per process, reused across requests
_router: AgentRouter | None = None


def get_router() -> AgentRouter:
    global _router
    if _router is None:
        _router = AgentRouter()
    return _router
