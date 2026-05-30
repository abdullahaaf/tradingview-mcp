from fastapi import FastAPI, HTTPException

from tradingview_mcp.core.services.news_service import fetch_news_summary
from tradingview_mcp.core.services.ohlc_service import get_pivots, get_session_ohlc
from tradingview_mcp.core.services.tradingview_service import fetch_tradingview_feed

app = FastAPI(title="TradingView MCP HTTP API")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/session-ohlc")
def session_ohlc():
    result = get_session_ohlc()
    return result


@app.get("/api/pivot-feeds")
def pivot_feeds():
    return get_pivots()


@app.get("/api/tradingview-feed")
def tradingview_feed():
    return fetch_tradingview_feed()


@app.get("/api/financial-news")
def financial_news():
    return fetch_news_summary()
