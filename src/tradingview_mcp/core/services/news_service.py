"""
Financial News Service via RSS feeds.

Uses feedparser (already installed as part of agent-reach dependencies).
No API keys required. Pulls from free, public RSS feeds.

Sources:
  crypto: CoinDesk, Cointelegraph
  stocks: Reuters Business News
  all:    Combined
"""
from __future__ import annotations

from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Optional

tz = ZoneInfo("Asia/Jakarta")

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

def set_time():
    tz = ZoneInfo("Asia/Jakarta")

    today = datetime.now(tz)
    yesterday = today - timedelta(days=1)

    today_first_format = today.strftime("%d %b %Y")
    today_second_format = today.strftime("%b %d, %Y")

    yesterday_first_format = yesterday.strftime("%d %b %Y")
    yesterday_second_format = yesterday.strftime("%b %d, %Y")

    return today_first_format, today_second_format, yesterday_first_format, yesterday_second_format

def _parse_pubdate(published_str: str) -> datetime | None:
    """
    Try multiple date formats to parse a published string into a datetime.
    Returns None if all formats fail.
    """
    if not published_str:
        return None

    # Try RFC 2822 format first (common in RSS: "Wed, 06 May 2026 10:30:00 +0000")
    try:
        return parsedate_to_datetime(published_str)
    except Exception:
        pass

    # Try common fallback formats
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%d %b %Y %H:%M:%S %z",
        "%b %d, %Y %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%d %b %Y",
        "%b %d, %Y",
    ):
        try:
            return datetime.strptime(published_str.strip(), fmt)
        except ValueError:
            continue

    return None

def fetch_news() -> list[dict]:
    """
    Fetch financial news from RSS feeds.

    Returns:
        List of news items with title, url, published, summary, source.
    """
    if not _FEEDPARSER_AVAILABLE:
        return [{
            "error": "feedparser not installed. Run: pip install feedparser",
            "install": "pip install feedparser"
        }]

    feeds = [
        {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100727362", "name": "CNBC World News"},
        {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15837362", "name": "CNBC US News"},
        {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258", "name": "CNBC Economy News"},
        {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114", "name": "CNBC Markets News"},
        {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19836768", "name": "CNBC Energy News"},
        {"url": "https://www.dailyforex.com/rss/forexnews.xml", "name": "Daily Forex"},
        {"url": "https://news.instaforex.com/news", "name": "Insta Forex"},
        {"url": "https://www.investing.com/rss/forex_Fundamental.rss", "name": "Investing.com Forex"},
        {"url": "https://investinglive.com/feed/news", "name": "Reuters Business"},
        {"url": "https://www.myfxbook.com/rss/latest-forex-news", "name": "MyFxBook"},
    ]
    results: list[dict] = []
    today_first_format, today_second_format, yesterday_first_format, yesterday_second_format = set_time()

    for feed_info in feeds:
        try:
            feed = feedparser.parse(feed_info["url"])
            source_name = feed.feed.get("title", feed_info["name"])

            for entry in feed.entries:

                title = entry.get("title", "")
                summary = entry.get("summary", "") or entry.get("description", "")
                raw_published = entry.get("published", "")

                 # Filter only yesterday–today news (keep original string-based check)
                if not any(d in raw_published for d in (
                    today_first_format, today_second_format,
                    yesterday_first_format, yesterday_second_format,
                )):
                    continue

                pub_dt = _parse_pubdate(raw_published)

                results.append({
                    "title": title,
                    "url": entry.get("link", ""),
                    "published": pub_dt,
                    "summary": _clean_html(summary),
                    "source": source_name,
                })
                  

        except Exception:
            continue

    # Sort descending: entries without a date go to the bottom
    results.sort(key=lambda x: x["published"] or datetime.min.replace(tzinfo=tz), reverse=True)
    return results


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
    return text.strip()
