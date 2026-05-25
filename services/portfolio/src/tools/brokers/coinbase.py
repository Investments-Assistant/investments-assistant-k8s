"""Coinbase Advanced Trade integration."""

from __future__ import annotations

import logging
from src.config import settings

logger = logging.getLogger(__name__)


def _client():
    from coinbase.rest import RESTClient

    return RESTClient(
        api_key=settings.coinbase_api_key, api_secret=settings.coinbase_api_secret
    )


def get_account() -> dict:
    try:
        accounts = _client().get_accounts()
        total_usd = 0.0
        balances = []
        for acct in accounts.accounts or []:
            val = float(acct.available_balance.value or 0)
            if acct.available_balance.currency == "USD":
                total_usd += val
            balances.append(
                {"currency": acct.available_balance.currency, "available": val}
            )
        return {"broker": "coinbase", "cash_usd": total_usd, "balances": balances}
    except Exception as exc:
        return {"broker": "coinbase", "error": str(exc)}


def get_positions() -> dict:
    try:
        accounts = _client().get_accounts()
        positions = [
            {
                "currency": a.available_balance.currency,
                "available": float(a.available_balance.value or 0),
            }
            for a in (accounts.accounts or [])
            if float(a.available_balance.value or 0) > 0
        ]
        return {"broker": "coinbase", "positions": positions}
    except Exception as exc:
        return {"broker": "coinbase", "error": str(exc)}


def submit_order(symbol, side, quantity, order_type="market", limit_price=None) -> dict:
    try:
        client = _client()
        product_id = symbol.replace("-", "-")  # already in BTC-USD format
        if order_type == "market":
            if side == "buy":
                resp = client.market_order_buy(
                    client_order_id=f"ia-{symbol}-buy",
                    product_id=product_id,
                    quote_size=str(quantity * (limit_price or 1)),
                )
            else:
                resp = client.market_order_sell(
                    client_order_id=f"ia-{symbol}-sell",
                    product_id=product_id,
                    base_size=str(quantity),
                )
        else:
            if side == "buy":
                resp = client.limit_order_gtc_buy(
                    client_order_id=f"ia-{symbol}-buy",
                    product_id=product_id,
                    base_size=str(quantity),
                    limit_price=str(limit_price),
                )
            else:
                resp = client.limit_order_gtc_sell(
                    client_order_id=f"ia-{symbol}-sell",
                    product_id=product_id,
                    base_size=str(quantity),
                    limit_price=str(limit_price),
                )
        order_id = resp.order_id if hasattr(resp, "order_id") else "unknown"
        return {
            "status": "submitted",
            "broker": "coinbase",
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
        }
    except Exception as exc:
        logger.exception("Coinbase submit_order failed")
        return {"status": "error", "broker": "coinbase", "error": str(exc)}


def cancel_order(order_id: str) -> dict:
    try:
        _client().cancel_orders(order_ids=[order_id])
        return {"status": "cancelled", "broker": "coinbase", "order_id": order_id}
    except Exception as exc:
        return {"status": "error", "broker": "coinbase", "error": str(exc)}
