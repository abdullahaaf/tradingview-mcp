from __future__ import annotations

"""
Financial News Service via RSS feeds.

Uses feedparser (already installed as part of agent-reach dependencies).
No API keys required. Pulls from free, public RSS feeds.

Sources:
  crypto: CoinDesk, Cointelegraph
  stocks: Reuters Business News
  all:    Combined
"""
import os, time

from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta, timezone

# set timezone to UTC
os.environ["TZ"] = "UTC"
time.tzset()

current = datetime.now()
previous = current - timedelta(days=1)

# feedparser is bundled with agent-reach (installed globally)
try:
    import feedparser
    _FEEDPARSER_AVAILABLE = True
except ImportError:
    _FEEDPARSER_AVAILABLE = False

# ─── Feed Catalog ─────────────────────────────────────────────────────────────

RSS_FEEDS: dict[str, list[dict]] = {
    "crypto": [
        {"url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "name": "CoinDesk"},
        {"url": "https://cointelegraph.com/rss", "name": "CoinTelegraph"},
    ],
    "stocks": [
        {"url": "https://feeds.reuters.com/reuters/businessNews", "name": "Reuters Business"},
        {"url": "https://feeds.reuters.com/reuters/companyNews", "name": "Reuters Company"},
    ],
    "all": [
        {"url": "https://feeds.reuters.com/reuters/businessNews", "name": "Reuters Business"},
        {"url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "name": "CoinDesk"},
        {"url": "https://cointelegraph.com/rss", "name": "CoinTelegraph"},
    ],
}

_TIMEOUT = 8


# ─── Public API ───────────────────────────────────────────────────────────────

# def fetch_news(
#     symbol: Optional[str] = None,
#     category: str = "stocks",
#     limit: int = 10,
# ) -> list[dict]:
#     """
#     Fetch financial news from RSS feeds.

#     Args:
#         symbol:   Optional ticker filter. If provided, only returns headlines
#                   that mention the symbol (case-insensitive). e.g. "AAPL", "BTC"
#         category: Feed group — "crypto" | "stocks" | "all"
#         limit:    Maximum number of items to return

#     Returns:
#         List of news items with title, url, published, summary, source.
#     """
#     if not _FEEDPARSER_AVAILABLE:
#         return [{
#             "error": "feedparser not installed. Run: pip install feedparser",
#             "install": "pip install feedparser"
#         }]

#     feeds = RSS_FEEDS.get(category, RSS_FEEDS["stocks"])
#     results: list[dict] = []

#     for feed_info in feeds:
#         if len(results) >= limit:
#             break
#         try:
#             feed = feedparser.parse(feed_info["url"])
#             source_name = feed.feed.get("title", feed_info["name"])

#             for entry in feed.entries:
#                 if len(results) >= limit:
#                     break

#                 title = entry.get("title", "")
#                 summary = entry.get("summary", "") or entry.get("description", "")

#                 # Symbol filter
#                 if symbol:
#                     combined = f"{title} {summary}".upper()
#                     if symbol.upper() not in combined:
#                         continue

#                 results.append({
#                     "title": title,
#                     "url": entry.get("link", ""),
#                     "published": entry.get("published", ""),
#                     "summary": _clean_html(summary)[:300],
#                     "source": source_name,
#                 })

#         except Exception:
#             continue

#     return results[:limit]

def _derive_source(url: str) -> str:
    SOURCE_MAP = {
        "cnbc.com":        "CNBC",
        "marketwatch.com": "MarketWatch",
        "instaforex.com":  "InstaForex",
        "reuters.com":     "Reuters",
        "myfxbook.com":    "MyFXBook",
        "dailyforex.com":  "DailyForex",
        "investing.com":   "Investing.com",
        "investinglive.com": "InvestingLive",
    }
    for domain, label in SOURCE_MAP.items():
        if domain in url:
            return label
    return "Unknown"

def fetch_news() -> list[dict]:
    """
    Fetch financial news from RSS feeds.

    Returns:
        List of news items with title, url, published, summary, source.
    """
    if not _FEEDPARSER_AVAILABLE:
        return [{"error": "feedparser not installed.", "install": "pip install feedparser"}]

    feed_urls = [
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100727362",
        "https://www.dailyforex.com/rss/forexnews.xml",
        "https://news.instaforex.com/news",
        "https://www.investing.com/rss/forex_Fundamental.rss",
        "https://investinglive.com/feed/news",
        "https://www.myfxbook.com/rss/latest-forex-news",
    ]
    results: list[dict] = []

    for feed_url in feed_urls:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                # Parse tanggal per item — skip jika tidak valid
                try:
                    raw_published = entry.get("published", "")
                    pub_dt = parsedate_to_datetime(raw_published).replace(tzinfo=None)
                except Exception:
                    continue

                if not (previous <= pub_dt <= current):
                    continue

                # Resolve summary — gabung jika keduanya ada dan berbeda
                raw_summary = _clean_html(entry.get("summary", ""))
                raw_description = _clean_html(entry.get("description", ""))

                if raw_summary and raw_description and raw_summary != raw_description:
                    summary = f"{raw_summary} {raw_description}"
                else:
                    summary = raw_summary or raw_description

                # Kosongkan jika tidak informatif
                if summary.lower() in ("none", "-", ""):
                    summary = ""

                # Resolve URL
                url = entry.get("link", "")
                if not url:
                    links = entry.get("links", [])
                    url = links[0].get("href", "") if links else ""

                results.append({
                    "title":     _clean_html(entry.get("title", "")),
                    "url":       url,
                    "published": pub_dt,
                    "summary":   summary,
                    "source":    _derive_source(url),
                })

        except Exception:
            continue

    return sorted(results, key=lambda x: x["published"], reverse=True)


def fetch_news_summary() -> dict:
    """
    Fetch news and return structured dict for MCP tool output.
    """
    items = fetch_news()
    return {
        "symbol": 'Gold',
        "category": 'Futures',
        "count": len(items),
        "feedparser_available": _FEEDPARSER_AVAILABLE,
        "items": items,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ─── Utils ────────────────────────────────────────────────────────────────────

def _clean_html(text: str) -> str:
    """Strip basic HTML tags from text."""
    import re
    text = re.sub(r"<[^>]+>", "", text)
    for entity, char in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&nbsp;", " ")):
        text = text.replace(entity, char)
    text = re.sub(r'\s+', ' ', text)  # collapse whitespace
    return text.strip()
