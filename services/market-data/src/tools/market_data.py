"""Market data tools: OHLCV, technicals, options, earnings, ticker search."""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime
import logging

import pandas as pd
import ta
import yfinance as yf

logger = logging.getLogger(__name__)


def _df_to_records(df: pd.DataFrame, max_rows: int = 90) -> list[dict]:
    if df.empty:
        return []
    df = df.tail(max_rows).copy()
    df.index = (
        df.index.strftime("%Y-%m-%d") if hasattr(df.index, "strftime") else df.index
    )
    return [
        {
            "date": str(date),
            "open": round(float(row.get("Open", 0)), 4),
            "high": round(float(row.get("High", 0)), 4),
            "low": round(float(row.get("Low", 0)), 4),
            "close": round(float(row.get("Close", 0)), 4),
            "volume": int(row.get("Volume", 0)),
        }
        for date, row in df.iterrows()
    ]


def get_stock_data(
    symbols: list[str], period: str = "1mo", interval: str = "1d"
) -> dict:
    result: dict = {}
    for sym in symbols:
        try:
            ticker = yf.Ticker(sym)
            df = ticker.history(period=period, interval=interval)
            info = ticker.info or {}
            result[sym] = {
                "company_name": info.get("longName", sym),
                "current_price": info.get("currentPrice")
                or info.get("regularMarketPrice"),
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "52w_high": info.get("fiftyTwoWeekHigh"),
                "52w_low": info.get("fiftyTwoWeekLow"),
                "candles": _df_to_records(df),
            }
        except Exception as exc:
            logger.warning("Failed to fetch %s: %s", sym, exc)
            result[sym] = {"error": str(exc)}
    return result


def get_crypto_data(
    symbols: list[str], period: str = "1mo", interval: str = "1d"
) -> dict:
    return get_stock_data(symbols, period=period, interval=interval)


def get_market_overview() -> dict:
    tickers = {
        "S&P 500": "^GSPC",
        "NASDAQ 100": "^NDX",
        "Dow Jones": "^DJI",
        "Russell 2000": "^RUT",
        "VIX": "^VIX",
        "10Y Yield": "^TNX",
        "Gold": "GC=F",
        "Crude Oil": "CL=F",
        "Bitcoin": "BTC-USD",
        "Ethereum": "ETH-USD",
        "Dollar Index": "DX-Y.NYB",
    }
    markets: dict = {}
    for name, sym in tickers.items():
        try:
            info = yf.Ticker(sym).info or {}
            price = info.get("regularMarketPrice") or info.get("currentPrice")
            prev = info.get("regularMarketPreviousClose")
            markets[name] = {
                "symbol": sym,
                "price": price,
                "change_pct": round((price - prev) / prev * 100, 2)
                if price and prev and prev != 0
                else None,
            }
        except Exception as exc:
            markets[name] = {"error": str(exc)}
    return {"timestamp": datetime.now(UTC).isoformat(), "markets": markets}


def get_technical_indicators(symbol: str, period: str = "6mo") -> dict:
    try:
        df = yf.Ticker(symbol).history(period=period, interval="1d")
        if df.empty or len(df) < 20:
            return {"error": f"Insufficient data for {symbol}"}

        close, high, low, volume = df["Close"], df["High"], df["Low"], df["Volume"]

        rsi = ta.momentum.RSIIndicator(close=close, window=14).rsi().iloc[-1]
        macd_ind = ta.trend.MACD(close=close)
        macd_val, macd_sig, macd_hist = (
            macd_ind.macd().iloc[-1],
            macd_ind.macd_signal().iloc[-1],
            macd_ind.macd_diff().iloc[-1],
        )
        bb = ta.volatility.BollingerBands(close=close, window=20, window_dev=2)
        bb_u, bb_m, bb_l = (
            bb.bollinger_hband().iloc[-1],
            bb.bollinger_mavg().iloc[-1],
            bb.bollinger_lband().iloc[-1],
        )
        ema20 = ta.trend.EMAIndicator(close=close, window=20).ema_indicator().iloc[-1]
        ema50 = ta.trend.EMAIndicator(close=close, window=50).ema_indicator().iloc[-1]
        ema200 = (
            ta.trend.EMAIndicator(close=close, window=200).ema_indicator().iloc[-1]
            if len(df) >= 200
            else None
        )
        atr = (
            ta.volatility.AverageTrueRange(high=high, low=low, close=close, window=14)
            .average_true_range()
            .iloc[-1]
        )
        obv = (
            ta.volume.OnBalanceVolumeIndicator(close=close, volume=volume)
            .on_balance_volume()
            .iloc[-1]
        )

        cp = float(close.iloc[-1])

        def _r(v, d=4):
            return round(float(v), d) if v is not None and v == v else None

        signals = []
        if rsi < 30:
            signals.append("RSI oversold (bullish)")
        elif rsi > 70:
            signals.append("RSI overbought (bearish)")
        if macd_val > macd_sig:
            signals.append("MACD bullish crossover")
        else:
            signals.append("MACD bearish crossover")
        if ema200 and cp > ema200:
            signals.append("Price above 200 EMA (uptrend)")
        elif ema200:
            signals.append("Price below 200 EMA (downtrend)")
        if cp > bb_u:
            signals.append("Price above upper BB (overextended)")
        elif cp < bb_l:
            signals.append("Price below lower BB (oversold)")

        return {
            "symbol": symbol,
            "current_price": _r(cp),
            "rsi_14": _r(rsi, 2),
            "macd": {
                "macd": _r(macd_val),
                "signal": _r(macd_sig),
                "histogram": _r(macd_hist),
            },
            "bollinger_bands": {
                "upper": _r(bb_u),
                "middle": _r(bb_m),
                "lower": _r(bb_l),
            },
            "ema": {"ema_20": _r(ema20), "ema_50": _r(ema50), "ema_200": _r(ema200)},
            "atr_14": _r(atr),
            "obv": _r(obv, 0),
            "signals": signals,
        }
    except Exception as exc:
        logger.exception("Technical indicators failed for %s", symbol)
        return {"error": str(exc)}


_OPT_COLS = [
    "strike",
    "bid",
    "ask",
    "lastPrice",
    "impliedVolatility",
    "openInterest",
    "delta",
    "gamma",
]


def _clean_opts(rows: list[dict]) -> list[dict]:
    for item in rows:
        for k, v in item.items():
            with contextlib.suppress(Exception):
                if pd.isna(v):
                    item[k] = None
                elif hasattr(v, "item"):
                    item[k] = v.item()
    return rows


def get_options_chain(symbol: str, expiry: str | None = None) -> dict:
    try:
        ticker = yf.Ticker(symbol)
        exps = ticker.options
        if not exps:
            return {"error": f"No options for {symbol}"}
        targets = [expiry] if expiry and expiry in exps else list(exps[:3])
        result: dict = {"symbol": symbol, "expiries": {}}
        for exp in targets:
            opt = ticker.option_chain(exp)
            result["expiries"][exp] = {
                "calls": _clean_opts(opt.calls[_OPT_COLS].head(20).to_dict("records")),
                "puts": _clean_opts(opt.puts[_OPT_COLS].head(20).to_dict("records")),
            }
        return result
    except Exception as exc:
        return {"error": str(exc)}


def search_ticker(query: str) -> dict:
    try:
        results = yf.Search(query, max_results=10)
        quotes = results.quotes if hasattr(results, "quotes") else []
        return {
            "query": query,
            "results": [
                {
                    "symbol": q.get("symbol"),
                    "name": q.get("longname") or q.get("shortname"),
                    "type": q.get("quoteType"),
                    "exchange": q.get("exchange"),
                }
                for q in quotes
            ],
        }
    except Exception as exc:
        return {"error": str(exc), "query": query}


def get_earnings_calendar(
    days_ahead: int = 7, symbols: list[str] | None = None
) -> dict:
    result: dict = {"days_ahead": days_ahead, "earnings": []}
    for sym in symbols or []:
        try:
            cal = yf.Ticker(sym).calendar
            if cal is not None and not cal.empty:
                for col in cal.columns:
                    result["earnings"].append(
                        {
                            "symbol": sym,
                            "date": str(col),
                            "earnings_date": str(cal[col].get("Earnings Date", "")),
                            "eps_estimate": cal[col].get("EPS Estimate"),
                        }
                    )
        except Exception as exc:
            result["earnings"].append({"symbol": sym, "error": str(exc)})
    if not symbols:
        result["note"] = "Provide symbols for individual earnings dates."
    return result
