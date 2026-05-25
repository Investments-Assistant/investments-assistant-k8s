"""Portfolio summary, account info, and trade history tools."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, select

from src.db.database import async_session
from src.db.models import Trade

logger = logging.getLogger(__name__)


def get_portfolio_summary(broker: str | None = None) -> dict:
    from src.tools.brokers import alpaca, binance, coinbase, ibkr
    from src.config import settings

    brokers_to_query = []
    if not broker or broker == "alpaca":
        brokers_to_query.append(("alpaca", alpaca.get_positions))
    if not broker or broker == "ibkr":
        if settings.ibkr_enabled:
            brokers_to_query.append(("ibkr", ibkr.get_positions))
    if not broker or broker == "coinbase":
        brokers_to_query.append(("coinbase", coinbase.get_positions))
    if not broker or broker == "binance":
        brokers_to_query.append(("binance", binance.get_positions))

    result: dict = {"timestamp": datetime.now(UTC).isoformat(), "brokers": {}}
    for name, fn in brokers_to_query:
        try:
            result["brokers"][name] = fn()
        except Exception as exc:
            result["brokers"][name] = {"error": str(exc)}
    return result


def get_account_info(broker: str) -> dict:
    from src.tools.brokers import alpaca, binance, coinbase, ibkr

    fns = {
        "alpaca": alpaca.get_account,
        "ibkr": ibkr.get_account,
        "coinbase": coinbase.get_account,
        "binance": binance.get_account,
    }
    fn = fns.get(broker)
    if not fn:
        return {"error": f"Unknown broker: {broker}"}
    try:
        return fn()
    except Exception as exc:
        return {"error": str(exc), "broker": broker}


async def get_trade_history(broker: str, days: int = 30) -> dict:
    try:
        since = datetime.now(UTC) - timedelta(days=days)
        async with async_session() as session:
            rows = (
                (
                    await session.execute(
                        select(Trade)
                        .where(Trade.broker == broker)
                        .where(Trade.created_at >= since)
                        .order_by(desc(Trade.created_at))
                        .limit(100)
                    )
                )
                .scalars()
                .all()
            )
        return {
            "broker": broker,
            "days": days,
            "count": len(rows),
            "trades": [
                {
                    "id": t.id,
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
            ],
        }
    except Exception as exc:
        logger.exception("get_trade_history failed")
        return {"error": str(exc), "broker": broker}
