"""Binance integration (spot trading)."""

from __future__ import annotations

import logging
from src.config import settings

logger = logging.getLogger(__name__)


def _client():
    from binance.client import Client

    return Client(
        api_key=settings.binance_api_key,
        api_secret=settings.binance_secret_key,
        testnet=settings.binance_testnet,
    )


def get_account() -> dict:
    try:
        acct = _client().get_account()
        balances = [
            {
                "asset": b["asset"],
                "free": float(b["free"]),
                "locked": float(b["locked"]),
            }
            for b in acct.get("balances", [])
            if float(b["free"]) > 0 or float(b["locked"]) > 0
        ]
        return {
            "broker": "binance",
            "testnet": settings.binance_testnet,
            "balances": balances,
        }
    except Exception as exc:
        return {"broker": "binance", "error": str(exc)}


def get_positions() -> dict:
    return get_account()


def submit_order(symbol, side, quantity, order_type="market", limit_price=None) -> dict:
    try:
        client = _client()
        order_side = "BUY" if side == "buy" else "SELL"
        if order_type == "market":
            resp = client.order_market(
                symbol=symbol, side=order_side, quantity=quantity
            )
        else:
            resp = client.order_limit(
                symbol=symbol,
                side=order_side,
                quantity=quantity,
                price=str(limit_price),
                timeInForce="GTC",
            )
        return {
            "status": "submitted",
            "broker": "binance",
            "order_id": str(resp.get("orderId", "")),
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
        }
    except Exception as exc:
        logger.exception("Binance submit_order failed")
        return {"status": "error", "broker": "binance", "error": str(exc)}


def cancel_order(order_id: str) -> dict:
    try:
        # symbol is required by Binance API; we can't cancel without it
        return {
            "status": "error",
            "broker": "binance",
            "error": "Binance cancel requires symbol; pass symbol+order_id",
        }
    except Exception as exc:
        return {"status": "error", "broker": "binance", "error": str(exc)}
