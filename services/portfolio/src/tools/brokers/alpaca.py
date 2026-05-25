"""Alpaca brokerage integration (stocks and ETFs)."""

from __future__ import annotations

import logging
from src.config import settings

logger = logging.getLogger(__name__)


def _client():
    from alpaca.trading.client import TradingClient

    return TradingClient(
        api_key=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
        paper=settings.alpaca_paper,
    )


def _data_client():
    from alpaca.data.historical import StockHistoricalDataClient

    return StockHistoricalDataClient(
        api_key=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
    )


def get_account() -> dict:
    try:
        acct = _client().get_account()
        return {
            "broker": "alpaca",
            "paper": settings.alpaca_paper,
            "cash": float(acct.cash),
            "portfolio_value": float(acct.portfolio_value),
            "buying_power": float(acct.buying_power),
            "equity": float(acct.equity),
            "status": acct.status,
        }
    except Exception as exc:
        return {"broker": "alpaca", "error": str(exc)}


def get_positions() -> dict:
    try:
        positions = _client().get_all_positions()
        return {
            "broker": "alpaca",
            "positions": [
                {
                    "symbol": p.symbol,
                    "qty": float(p.qty),
                    "avg_entry_price": float(p.avg_entry_price),
                    "current_price": float(p.current_price),
                    "market_value": float(p.market_value),
                    "unrealized_pl": float(p.unrealized_pl),
                    "unrealized_plpc": float(p.unrealized_plpc),
                }
                for p in positions
            ],
        }
    except Exception as exc:
        return {"broker": "alpaca", "error": str(exc)}


def submit_order(
    symbol, side, quantity, order_type="market", limit_price=None, stop_price=None
) -> dict:
    try:
        from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        order_side = OrderSide.BUY if side == "buy" else OrderSide.SELL

        if order_type == "market":
            req = MarketOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=order_side,
                time_in_force=TimeInForce.DAY,
            )
        else:
            req = LimitOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=order_side,
                time_in_force=TimeInForce.DAY,
                limit_price=limit_price,
            )

        order = _client().submit_order(req)
        return {
            "status": "submitted",
            "broker": "alpaca",
            "order_id": str(order.id),
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
        }
    except Exception as exc:
        logger.exception("Alpaca submit_order failed")
        return {"status": "error", "broker": "alpaca", "error": str(exc)}


def cancel_order(order_id: str) -> dict:
    try:
        _client().cancel_order_by_id(order_id)
        return {"status": "cancelled", "broker": "alpaca", "order_id": order_id}
    except Exception as exc:
        return {"status": "error", "broker": "alpaca", "error": str(exc)}
