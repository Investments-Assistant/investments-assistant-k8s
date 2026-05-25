"""Portfolio tool dispatcher: trade execution with full safety guardrails.

Safety guards (same as the Pi version, enforced here not in the gateway):
  - RECOMMEND mode: returns pending_confirmation, never executes
  - AUTO mode:
      1. Symbol allowlist check
      2. Per-trade USD cap (AUTO_MAX_TRADE_USD)
      3. Daily loss limit (AUTO_DAILY_LOSS_LIMIT_USD) with Redis-backed halt flag
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select

from src.config import settings
from src.db.database import async_session
from src.db.models import DailyPnL, Trade

logger = logging.getLogger(__name__)


async def _get_trading_mode() -> str:
    """Read trading_mode from Redis (set by gateway) or fall back to env setting."""
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        mode = await r.get("trading_mode")
        await r.aclose()
        if mode in ("recommend", "auto"):
            return mode
    except Exception:
        pass
    return settings.trading_mode


async def _is_daily_halted() -> bool:
    try:
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        async with async_session() as session:
            row = (
                await session.execute(select(DailyPnL).where(DailyPnL.date == today))
            ).scalar_one_or_none()
            return bool(row and row.auto_trading_halted)
    except Exception as exc:
        logger.warning("Daily halt check failed: %s", exc)
        return False


async def _update_daily_pnl(delta_usd: float) -> None:
    try:
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        async with async_session() as session:
            row = (
                await session.execute(select(DailyPnL).where(DailyPnL.date == today))
            ).scalar_one_or_none()
            if row is None:
                row = DailyPnL(date=today, realized_usd=0.0)
                session.add(row)
            row.realized_usd = (row.realized_usd or 0.0) + delta_usd
            if row.realized_usd < -abs(settings.auto_daily_loss_limit_usd):
                row.auto_trading_halted = True
                logger.warning(
                    "Daily loss limit reached (%.2f). Auto-trading halted.",
                    row.realized_usd,
                )
            await session.commit()
    except Exception as exc:
        logger.warning("Failed to update daily P&L: %s", exc)


async def execute_trade(inp: dict) -> dict:
    broker = inp["broker"]
    symbol = inp["symbol"]
    side = inp["side"]
    quantity = float(inp["quantity"])
    order_type = inp.get("order_type", "market")
    limit_price = inp.get("limit_price")
    stop_price = inp.get("stop_price")
    reason = inp.get("reason", "")

    trading_mode = await _get_trading_mode()

    if trading_mode == "recommend":
        return {
            "status": "pending_confirmation",
            "message": (
                f"RECOMMENDATION: {side.upper()} {quantity} {symbol} via {broker} "
                f"({order_type}{f' @ {limit_price}' if limit_price else ''}). "
                f"Reason: {reason}. Reply 'confirm trade' to execute."
            ),
            "trade_details": {
                "broker": broker,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "order_type": order_type,
                "limit_price": limit_price,
                "stop_price": stop_price,
                "reason": reason,
            },
        }

    # ── AUTO mode safety checks ────────────────────────────────────────────────
    if (
        settings.auto_allowed_symbols_set
        and symbol.upper() not in settings.auto_allowed_symbols_set
    ):
        return {
            "blocked": True,
            "reason": f"{symbol} is not in the auto-trading allowed symbols list.",
        }

    notional = (limit_price or 0) * quantity
    if limit_price and notional > settings.auto_max_trade_usd:
        return {
            "blocked": True,
            "reason": (
                f"Trade notional ${notional:.0f} exceeds per-trade limit "
                f"${settings.auto_max_trade_usd:.0f}."
            ),
        }

    if await _is_daily_halted():
        return {
            "blocked": True,
            "reason": f"Auto-trading halted: daily loss limit ${settings.auto_daily_loss_limit_usd:.0f} reached.",
        }

    result = _route_order(
        broker, symbol, side, quantity, order_type, limit_price, stop_price
    )
    result["reason"] = reason

    try:
        async with async_session() as session:
            session.add(
                Trade(
                    broker=broker,
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    price=limit_price,
                    order_type=order_type,
                    status=result.get("status", "submitted"),
                    broker_order_id=result.get("order_id"),
                    mode="auto",
                    reason=reason,
                )
            )
            await session.commit()
    except Exception as exc:
        logger.warning("Failed to persist trade: %s", exc)

    if side == "sell" and limit_price:
        await _update_daily_pnl(-(quantity * limit_price))

    return result


async def confirm_trade(inp: dict) -> dict:
    """Execute a user-confirmed recommendation (bypasses recommend-mode guard)."""
    broker = inp["broker"]
    symbol = inp["symbol"]
    side = inp["side"]
    quantity = float(inp["quantity"])
    order_type = inp.get("order_type", "market")
    limit_price = inp.get("limit_price")
    stop_price = inp.get("stop_price")
    reason = inp.get("reason", "User confirmed recommendation")

    result = _route_order(
        broker, symbol, side, quantity, order_type, limit_price, stop_price
    )
    result["reason"] = reason

    try:
        async with async_session() as session:
            session.add(
                Trade(
                    broker=broker,
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    price=limit_price,
                    order_type=order_type,
                    status=result.get("status", "submitted"),
                    broker_order_id=result.get("order_id"),
                    mode="manual",
                    reason=reason,
                )
            )
            await session.commit()
    except Exception as exc:
        logger.warning("Failed to persist confirmed trade: %s", exc)

    return result


def _route_order(
    broker, symbol, side, quantity, order_type, limit_price, stop_price
) -> dict:
    from src.tools.brokers import alpaca, binance, coinbase, ibkr

    if broker == "alpaca":
        return alpaca.submit_order(
            symbol, side, quantity, order_type, limit_price, stop_price
        )
    if broker == "ibkr":
        return ibkr.submit_order(symbol, side, quantity, order_type, limit_price)
    if broker == "coinbase":
        return coinbase.submit_order(symbol, side, quantity, order_type, limit_price)
    if broker == "binance":
        return binance.submit_order(symbol, side, quantity, order_type, limit_price)
    return {"error": f"Unknown broker: {broker}"}


def cancel_order(broker: str, order_id: str) -> dict:
    from src.tools.brokers import alpaca, binance, coinbase, ibkr

    if broker == "alpaca":
        return alpaca.cancel_order(order_id)
    if broker == "ibkr":
        return ibkr.cancel_order(order_id)
    if broker == "coinbase":
        return coinbase.cancel_order(order_id)
    if broker == "binance":
        return binance.cancel_order(order_id)
    return {"error": f"Unknown broker: {broker}"}
