"""Interactive Brokers integration via ib_insync (optional)."""

from __future__ import annotations

import logging
from src.config import settings

logger = logging.getLogger(__name__)


def _ib():
    if not settings.ibkr_enabled:
        raise RuntimeError("IBKR is not enabled (IBKR_ENABLED=false)")
    from ib_insync import IB

    ib = IB()
    ib.connect(settings.ibkr_host, settings.ibkr_port, clientId=settings.ibkr_client_id)
    return ib


def get_account() -> dict:
    try:
        ib = _ib()
        summary = ib.accountSummary()
        ib.disconnect()
        fields = {item.tag: item.value for item in summary}
        return {
            "broker": "ibkr",
            "net_liquidation": fields.get("NetLiquidation"),
            "available_funds": fields.get("AvailableFunds"),
            "buying_power": fields.get("BuyingPower"),
            "cash": fields.get("TotalCashValue"),
        }
    except Exception as exc:
        return {"broker": "ibkr", "error": str(exc)}


def get_positions() -> dict:
    try:
        ib = _ib()
        positions = ib.positions()
        ib.disconnect()
        return {
            "broker": "ibkr",
            "positions": [
                {
                    "symbol": p.contract.symbol,
                    "qty": p.position,
                    "avg_cost": p.avgCost,
                    "market_value": p.position * p.avgCost,
                }
                for p in positions
            ],
        }
    except Exception as exc:
        return {"broker": "ibkr", "error": str(exc)}


def _is_forex_pair(symbol: str) -> bool:
    """Return True for symbols like 'EURUSD', 'EUR/USD', 'EUR-USD'."""
    clean = symbol.upper().replace("/", "").replace("-", "")
    return len(clean) == 6 and clean.isalpha()


def submit_order(symbol, side, quantity, order_type="market", limit_price=None) -> dict:
    try:
        from ib_insync import Forex, LimitOrder, MarketOrder, Stock

        ib = _ib()
        if _is_forex_pair(symbol):
            clean = symbol.upper().replace("/", "").replace("-", "")
            contract = Forex(clean)
        else:
            contract = Stock(symbol, "SMART", "USD")
        if order_type == "market":
            order = MarketOrder(action=side.upper(), totalQuantity=quantity)
        else:
            order = LimitOrder(
                action=side.upper(), totalQuantity=quantity, lmtPrice=limit_price
            )
        trade = ib.placeOrder(contract, order)
        ib.disconnect()
        return {
            "status": "submitted",
            "broker": "ibkr",
            "order_id": str(trade.order.orderId),
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
        }
    except Exception as exc:
        logger.exception("IBKR submit_order failed")
        return {"status": "error", "broker": "ibkr", "error": str(exc)}


def cancel_order(order_id: str) -> dict:
    try:
        ib = _ib()
        open_trades = ib.openTrades()
        for trade in open_trades:
            if str(trade.order.orderId) == order_id:
                ib.cancelOrder(trade.order)
                ib.disconnect()
                return {"status": "cancelled", "broker": "ibkr", "order_id": order_id}
        ib.disconnect()
        return {"status": "not_found", "broker": "ibkr", "order_id": order_id}
    except Exception as exc:
        return {"status": "error", "broker": "ibkr", "error": str(exc)}
