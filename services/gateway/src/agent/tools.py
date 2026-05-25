"""Tool definitions exposed to the local OpenAI-compatible LLM."""

TOOL_DEFINITIONS: list[dict] = [
    # ── Market Data ────────────────────────────────────────────────────────────
    {
        "name": "get_stock_data",
        "description": (
            "Fetch OHLCV price data for one or more stocks or ETFs from Yahoo Finance. "
            "Returns open, high, low, close, volume for each candle."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ticker symbols e.g. ['AAPL','SPY']",
                },
                "period": {
                    "type": "string",
                    "description": "1d,5d,1mo,3mo,6mo,1y,2y,5y,ytd,max",
                    "default": "1mo",
                },
                "interval": {
                    "type": "string",
                    "description": "1m,5m,15m,30m,60m,1d,1wk,1mo",
                    "default": "1d",
                },
            },
            "required": ["symbols"],
        },
    },
    {
        "name": "get_crypto_data",
        "description": "Fetch OHLCV price data for cryptocurrencies. Use symbols like BTC-USD.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbols": {"type": "array", "items": {"type": "string"}},
                "period": {"type": "string", "default": "1mo"},
                "interval": {"type": "string", "default": "1d"},
            },
            "required": ["symbols"],
        },
    },
    # ── Forex ──────────────────────────────────────────────────────────────────
    {
        "name": "get_forex_data",
        "description": (
            "Fetch OHLCV history for forex (FX) currency pairs from Yahoo Finance. "
            "Accepts any format: 'EUR/USD', 'EURUSD', 'eurusd'. "
            "Returns candles and current spot rate."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pairs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Currency pairs e.g. ['EUR/USD','GBP/USD','USD/JPY']",
                },
                "period": {
                    "type": "string",
                    "description": "1d,5d,1mo,3mo,6mo,1y,2y,5y",
                    "default": "1mo",
                },
                "interval": {"type": "string", "description": "1h,1d,1wk,1mo", "default": "1d"},
            },
            "required": ["pairs"],
        },
    },
    {
        "name": "get_forex_rates",
        "description": (
            "Current spot rates, daily % change, and pip size for forex pairs. "
            "If no pairs supplied, returns all major pairs including EUR/USD, GBP/USD, "
            "USD/JPY, USD/BRL, EUR/BRL and more."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pairs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Pairs to query; omit for all majors",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_central_bank_rates",
        "description": (
            "Central bank policy rates for major currencies and carry-trade differentials "
            "ranked by annualised carry. Use to identify the best carry-trade opportunities."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "currencies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "ISO codes e.g. ['USD','EUR','JPY']; omit for all",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_market_overview",
        "description": "Snapshot of major indices, VIX, treasury yields, and commodities.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_technical_indicators",
        "description": "RSI, MACD, Bollinger Bands, EMA(20/50/200), ATR, OBV for a symbol.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "period": {"type": "string", "default": "6mo"},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "get_options_chain",
        "description": "Options chain (calls+puts): strikes, expiries, bid/ask, IV, OI, delta, \
            gamma.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "expiry": {"type": "string", "description": "YYYY-MM-DD; omit for next 3 expiries"},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "search_ticker",
        "description": "Search for a ticker symbol by company name or keyword.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    # ── News & Sentiment ───────────────────────────────────────────────────────
    {
        "name": "search_market_news",
        "description": (
            "Fetch recent financial news for a topic/symbol and analyse sentiment. "
            "Returns titles, summaries, sources, dates, sentiment scores."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_articles": {"type": "integer", "default": 10},
                "sources": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_earnings_calendar",
        "description": "Upcoming earnings announcements for the next N days.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {"type": "integer", "default": 7},
                "symbols": {"type": "array", "items": {"type": "string"}},
            },
            "required": [],
        },
    },
    {
        "name": "search_stored_news",
        "description": (
            "Search the persistent news memory (Reuters, Guardian, CNBC, FT, Economist, ECB, "
            "Portuguese sources, crypto news, email newsletters). Use for recalling past events "
            "or tracking a story over time."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "days_back": {"type": "integer", "default": 30},
                "sources": {"type": "array", "items": {"type": "string"}},
                "sentiment": {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_latest_news",
        "description": "Most recently ingested headlines from all sources — quick \
            'what happened today'.",
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 20}},
            "required": [],
        },
    },
    # ── Portfolio ──────────────────────────────────────────────────────────────
    {
        "name": "get_portfolio_summary",
        "description": "Current portfolio across all connected brokers: positions, P&L.",
        "input_schema": {
            "type": "object",
            "properties": {
                "broker": {
                    "type": "string",
                    "description": "alpaca|ibkr|coinbase|binance; omit for all",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_account_info",
        "description": "Account balance, buying power, and available cash for a broker.",
        "input_schema": {
            "type": "object",
            "properties": {
                "broker": {"type": "string", "enum": ["alpaca", "ibkr", "coinbase", "binance"]},
            },
            "required": ["broker"],
        },
    },
    {
        "name": "get_trade_history",
        "description": "Recent trade history from a broker.",
        "input_schema": {
            "type": "object",
            "properties": {
                "broker": {"type": "string", "enum": ["alpaca", "ibkr", "coinbase", "binance"]},
                "days": {"type": "integer", "default": 30},
            },
            "required": ["broker"],
        },
    },
    # ── Trade Execution ────────────────────────────────────────────────────────
    {
        "name": "execute_trade",
        "description": (
            "Execute a buy/sell order via a brokerage. "
            "In RECOMMEND mode returns a pending recommendation requiring your confirmation. "
            "In AUTO mode submits the order directly within safety limits. "
            "For forex pairs (e.g. 'EUR/USD', 'GBPUSD') use broker='ibkr'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "broker": {
                    "type": "string",
                    "enum": ["alpaca", "ibkr", "coinbase", "binance"],
                    "description": "Use ibkr for stocks, options, and forex pairs.",
                },
                "symbol": {
                    "type": "string",
                    "description": "Ticker or pair e.g. 'AAPL', 'BTC-USD', 'EUR/USD'",
                },
                "side": {"type": "string", "enum": ["buy", "sell"]},
                "quantity": {"type": "number"},
                "order_type": {
                    "type": "string",
                    "enum": ["market", "limit", "stop_limit"],
                    "default": "market",
                },
                "limit_price": {"type": "number"},
                "stop_price": {"type": "number"},
                "reason": {"type": "string", "description": "Mandatory: WHY this trade is placed"},
            },
            "required": ["broker", "symbol", "side", "quantity", "reason"],
        },
    },
    {
        "name": "cancel_order",
        "description": "Cancel an open order at a broker.",
        "input_schema": {
            "type": "object",
            "properties": {
                "broker": {"type": "string", "enum": ["alpaca", "ibkr", "coinbase", "binance"]},
                "order_id": {"type": "string"},
            },
            "required": ["broker", "order_id"],
        },
    },
    {
        "name": "confirm_trade",
        "description": (
            "Execute a previously recommended trade. Call ONLY after user explicitly confirms. "
            "Pass trade_details exactly as returned by execute_trade."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "broker": {"type": "string", "enum": ["alpaca", "ibkr", "coinbase", "binance"]},
                "symbol": {"type": "string"},
                "side": {"type": "string", "enum": ["buy", "sell"]},
                "quantity": {"type": "number"},
                "order_type": {
                    "type": "string",
                    "enum": ["market", "limit", "stop_limit"],
                    "default": "market",
                },
                "limit_price": {"type": "number"},
                "stop_price": {"type": "number"},
                "reason": {"type": "string"},
            },
            "required": ["broker", "symbol", "side", "quantity"],
        },
    },
    # ── Simulation ─────────────────────────────────────────────────────────────
    {
        "name": "run_simulation",
        "description": (
            "Backtest an investment strategy. "
            "Returns equity curve, total return, Sharpe ratio, max drawdown."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "symbols": {"type": "array", "items": {"type": "string"}},
                "strategy": {
                    "type": "object",
                    "description": (
                        "Strategy type: buy_and_hold | sma_crossover (fast,slow) | "
                        "rsi_mean_reversion (rsi_buy,rsi_sell) | momentum (lookback_days)"
                    ),
                    "properties": {
                        "type": {"type": "string"},
                        "params": {"type": "object"},
                    },
                    "required": ["type"],
                },
                "initial_capital": {"type": "number", "default": 10000},
                "period_start": {"type": "string", "description": "YYYY-MM-DD"},
                "period_end": {"type": "string"},
            },
            "required": ["name", "symbols", "strategy", "period_start"],
        },
    },
    # ── Agent Control ──────────────────────────────────────────────────────────
    {
        "name": "set_trading_mode",
        "description": "Switch between recommend (propose+confirm) and auto \
            (execute within limits).",
        "input_schema": {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["recommend", "auto"]},
            },
            "required": ["mode"],
        },
    },
    {
        "name": "generate_report",
        "description": "Generate a comprehensive investment report for a time period.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period_start": {"type": "string", "description": "YYYY-MM-DD"},
                "period_end": {"type": "string"},
            },
            "required": ["period_start"],
        },
    },
]
