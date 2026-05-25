"""Investment backtester: buy_and_hold, sma_crossover, rsi_mean_reversion, momentum."""

from __future__ import annotations

from datetime import UTC, datetime
import logging
import math

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def _download(symbols: list[str], start: str, end: str) -> pd.DataFrame:
    data = yf.download(symbols, start=start, end=end, auto_adjust=True, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        return data["Close"].dropna(how="all")
    return data[["Close"]].rename(columns={"Close": symbols[0]}).dropna()


def _metrics(equity: pd.Series) -> dict:
    if equity.empty or len(equity) < 2:
        return {}
    total_ret = (equity.iloc[-1] / equity.iloc[0] - 1) * 100
    daily_ret = equity.pct_change().dropna()
    annual_factor = 252
    sharpe = (
        float(daily_ret.mean() / daily_ret.std() * math.sqrt(annual_factor))
        if daily_ret.std() != 0
        else 0.0
    )
    max_dd = float(((equity - equity.cummax()) / equity.cummax()).min() * 100)
    return {
        "total_return_pct": round(float(total_ret), 2),
        "sharpe_ratio": round(sharpe, 3),
        "max_drawdown_pct": round(max_dd, 2),
        "annual_volatility_pct": round(
            float(daily_ret.std() * math.sqrt(annual_factor) * 100), 2
        ),
    }


def _buy_and_hold(prices: pd.DataFrame, capital: float) -> tuple[pd.Series, list[dict]]:
    n = len(prices.columns)
    alloc = capital / n
    shares = {sym: alloc / prices[sym].iloc[0] for sym in prices.columns}
    equity = sum(shares[sym] * prices[sym] for sym in prices.columns)
    trades = [
        {
            "date": str(prices.index[0].date()),
            "action": "BUY",
            "symbol": sym,
            "shares": round(shares[sym], 4),
        }
        for sym in prices.columns
    ]
    trades += [
        {
            "date": str(prices.index[-1].date()),
            "action": "SELL",
            "symbol": sym,
            "shares": round(shares[sym], 4),
        }
        for sym in prices.columns
    ]
    return equity, trades


def _sma_crossover(
    prices: pd.DataFrame, capital: float, fast: int = 20, slow: int = 50
) -> tuple[pd.Series, list[dict]]:
    equity = pd.Series(0.0, index=prices.index)
    trades = []
    for sym in prices.columns:
        p = prices[sym].dropna()
        sma_f, sma_s = p.rolling(fast).mean(), p.rolling(slow).mean()
        position, sym_cash = 0.0, capital / len(prices.columns)
        sym_eq = pd.Series(sym_cash, index=prices.index)
        for i in range(1, len(p)):
            date = p.index[i]
            crossed_up = (
                sma_f.iloc[i] > sma_s.iloc[i] and sma_f.iloc[i - 1] <= sma_s.iloc[i - 1]
            )
            crossed_dn = (
                sma_f.iloc[i] < sma_s.iloc[i] and sma_f.iloc[i - 1] >= sma_s.iloc[i - 1]
            )
            if crossed_up and sym_cash > 0 and position == 0:
                position = sym_cash / p.iloc[i]
                sym_cash = 0.0
                trades.append(
                    {
                        "date": str(date.date()),
                        "action": "BUY",
                        "symbol": sym,
                        "price": round(p.iloc[i], 4),
                        "shares": round(position, 4),
                    }
                )
            elif crossed_dn and position > 0:
                sym_cash = position * p.iloc[i]
                position = 0.0
                trades.append(
                    {
                        "date": str(date.date()),
                        "action": "SELL",
                        "symbol": sym,
                        "price": round(p.iloc[i], 4),
                        "proceeds": round(sym_cash, 2),
                    }
                )
            sym_eq.loc[date] = sym_cash + position * p.iloc[i]
        equity += sym_eq
    return equity, trades


def _rsi_mean_reversion(
    prices: pd.DataFrame, capital: float, rsi_buy: float = 30.0, rsi_sell: float = 70.0
) -> tuple[pd.Series, list[dict]]:
    from ta.momentum import RSIIndicator

    equity = pd.Series(0.0, index=prices.index)
    trades = []
    for sym in prices.columns:
        p = prices[sym].dropna()
        rsi = RSIIndicator(close=p, window=14).rsi()
        position, sym_cash = 0.0, capital / len(prices.columns)
        sym_eq = pd.Series(sym_cash, index=prices.index)
        for i in range(14, len(p)):
            date = p.index[i]
            r = rsi.iloc[i]
            if r < rsi_buy and position == 0 and sym_cash > 0:
                position = sym_cash / p.iloc[i]
                sym_cash = 0.0
                trades.append(
                    {
                        "date": str(date.date()),
                        "action": "BUY",
                        "symbol": sym,
                        "rsi": round(r, 1),
                        "price": round(p.iloc[i], 4),
                    }
                )
            elif r > rsi_sell and position > 0:
                sym_cash = position * p.iloc[i]
                position = 0.0
                trades.append(
                    {
                        "date": str(date.date()),
                        "action": "SELL",
                        "symbol": sym,
                        "rsi": round(r, 1),
                        "proceeds": round(sym_cash, 2),
                    }
                )
            sym_eq.loc[date] = sym_cash + position * p.iloc[i]
        equity += sym_eq
    return equity, trades


def _momentum(
    prices: pd.DataFrame,
    capital: float,
    lookback_days: int = 63,
    rebalance_days: int = 21,
    min_return: float = 0.0,
) -> tuple[pd.Series, list[dict]]:
    equity = pd.Series(0.0, index=prices.index)
    trades = []
    for sym in prices.columns:
        p = prices[sym].dropna()
        momentum = p.pct_change(lookback_days)
        position, sym_cash = 0.0, capital / len(prices.columns)
        sym_eq = pd.Series(sym_cash, index=prices.index)
        for i in range(lookback_days, len(p)):
            date = p.index[i]
            score = momentum.iloc[i]
            if pd.isna(score):
                continue

            should_rebalance = (i - lookback_days) % rebalance_days == 0
            if (
                should_rebalance
                and score > min_return
                and position == 0
                and sym_cash > 0
            ):
                position = sym_cash / p.iloc[i]
                sym_cash = 0.0
                trades.append(
                    {
                        "date": str(date.date()),
                        "action": "BUY",
                        "symbol": sym,
                        "momentum_pct": round(float(score * 100), 2),
                        "price": round(p.iloc[i], 4),
                        "shares": round(position, 4),
                    }
                )
            elif should_rebalance and score <= min_return and position > 0:
                sym_cash = position * p.iloc[i]
                position = 0.0
                trades.append(
                    {
                        "date": str(date.date()),
                        "action": "SELL",
                        "symbol": sym,
                        "momentum_pct": round(float(score * 100), 2),
                        "proceeds": round(sym_cash, 2),
                    }
                )
            sym_eq.loc[date] = sym_cash + position * p.iloc[i]
        equity += sym_eq
    return equity, trades


def run_simulation(
    name: str,
    symbols: list[str],
    strategy: dict,
    initial_capital: float = 10_000.0,
    period_start: str = "2023-01-01",
    period_end: str | None = None,
) -> dict:
    end = period_end or datetime.now(UTC).strftime("%Y-%m-%d")
    try:
        prices = _download(symbols, period_start, end)
    except Exception as exc:
        return {"error": f"Failed to download price data: {exc}"}
    if prices.empty:
        return {"error": "No price data returned."}

    stype = strategy.get("type", "buy_and_hold")
    params = strategy.get("params", {})
    try:
        if stype == "buy_and_hold":
            equity, trades = _buy_and_hold(prices, initial_capital)
        elif stype == "sma_crossover":
            equity, trades = _sma_crossover(
                prices,
                initial_capital,
                fast=int(params.get("fast", 20)),
                slow=int(params.get("slow", 50)),
            )
        elif stype == "rsi_mean_reversion":
            equity, trades = _rsi_mean_reversion(
                prices,
                initial_capital,
                rsi_buy=float(params.get("rsi_buy", 30)),
                rsi_sell=float(params.get("rsi_sell", 70)),
            )
        elif stype == "momentum":
            equity, trades = _momentum(
                prices,
                initial_capital,
                lookback_days=int(params.get("lookback_days", 63)),
                rebalance_days=int(params.get("rebalance_days", 21)),
                min_return=float(params.get("min_return", 0.0)),
            )
        else:
            return {"error": f"Unknown strategy: {stype}"}
    except Exception as exc:
        logger.exception("Simulation failed")
        return {"error": str(exc)}

    equity_weekly = equity.resample("W").last().dropna()
    return {
        "name": name,
        "strategy": strategy,
        "symbols": symbols,
        "initial_capital": initial_capital,
        "final_value": round(float(equity.iloc[-1]), 2),
        "period_start": period_start,
        "period_end": end,
        "trades_count": len(trades),
        "trades_sample": trades[:20],
        "equity_curve": [
            {"date": str(idx.date()), "value": round(float(v), 2)}
            for idx, v in equity_weekly.items()
        ],
        **_metrics(equity),
    }
