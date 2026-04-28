# Project Analysis: tradingview-mcp

## Context
User requested an analysis and overview of the tradingview-mcp project. This is an informational task, not an implementation task.

## Project Summary

**tradingview-mcp** is an AI-powered trading intelligence framework and MCP (Model Context Protocol) server for Claude and other MCP clients. Version 0.7.1, MIT licensed, Python 3.10+.

## Tech Stack
- **Framework:** FastMCP (MCP protocol server)
- **Package Manager:** uv (Astral)
- **Python:** 3.10+, pure stdlib (no pandas/numpy)
- **Key Libraries:** tradingview-screener, tradingview-ta, feedparser, mcp[cli]
- **Deployment:** stdio (Claude Desktop) or streamable-http (Docker, port 8085)

## Architecture
```
server.py (27 MCP tools, routing only)
└── core/services/           # All business logic
    ├── backtest_service.py   # 6 strategies (RSI, BB, MACD, EMA Cross, Supertrend, Donchian)
    ├── screener_service.py   # TradingView multi-exchange screener
    ├── indicators.py         # 30+ technical indicators (1200+ lines)
    ├── multi_agent_service.py # 3-agent debate (Technical/Sentiment/Risk)
    ├── sentiment_service.py  # Reddit sentiment scoring
    ├── news_service.py       # RSS aggregation (Reuters, CoinDesk, CoinTelegraph)
    ├── yahoo_finance_service.py # Real-time price data
    ├── egx_service.py        # Egyptian Exchange toolkit (1000+ lines)
    ├── scanner_service.py    # Volume/technical scanners
    ├── screener_provider.py  # Exchange screener abstraction
    └── proxy_manager.py      # Optional Webshare proxy support
└── core/types.py             # Shared types (TypedDict)
└── core/utils/validators.py  # Input sanitization (whitelists)
└── coinlist/                 # 31 exchange symbol .txt files
```

## 27 MCP Tools by Category
- **Screener (4):** top_gainers, top_losers, bollinger_scan, rating_filter
- **Analysis (3):** coin_analysis, multi_agent_analysis, combined_analysis
- **Candle Patterns (2):** consecutive_candles_scan, advanced_candle_pattern
- **Volume Scanners (3):** volume_breakout_scanner, volume_confirmation_analysis, smart_volume_scanner
- **Multi-Timeframe (1):** multi_timeframe_analysis
- **EGX/Egypt (7):** egx_market_overview, egx_sector_scan, egx_sector_scanner, egx_index_analysis, egx_stock_screener, egx_trade_plan, egx_fibonacci_retracement
- **Sentiment & News (2):** market_sentiment, financial_news
- **Backtesting (3):** backtest_strategy, compare_strategies, walk_forward_backtest_strategy
- **Market Data (2):** yahoo_price, market_snapshot
- **Resource (1):** exchanges_list

## Supported Exchanges
- **Crypto:** BINANCE, KUCOIN, BYBIT, MEXC, BITGET, OKX, COINBASE, GATEIO, HUOBI, BITFINEX, KRAKEN, BITSTAMP, ACE (13+)
- **Stocks:** EGX (Egypt), BIST (Turkey), NASDAQ/NYSE (US), HKEX (HK), SSE/SZSE (China), TWSE/TPEX (Taiwan), BURSA (Malaysia), ASX (Australia)

## Key Files
- [src/tradingview_mcp/server.py](src/tradingview_mcp/server.py) — MCP entry point, 27 tools
- [src/tradingview_mcp/core/services/backtest_service.py](src/tradingview_mcp/core/services/backtest_service.py) — Backtesting engine
- [src/tradingview_mcp/core/services/indicators.py](src/tradingview_mcp/core/services/indicators.py) — 30+ indicators
- [src/tradingview_mcp/core/services/egx_service.py](src/tradingview_mcp/core/services/egx_service.py) — EGX tools
- [src/tradingview_mcp/core/services/multi_agent_service.py](src/tradingview_mcp/core/services/multi_agent_service.py) — 3-agent debate
- [docker-compose.yml](docker-compose.yml) — Docker deployment (port 8085)
- [pyproject.toml](pyproject.toml) — Package config
