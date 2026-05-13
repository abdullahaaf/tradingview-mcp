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
import json
import logging
import os
import time
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta, timezone

# ── JSON log formatter ────────────────────────────────────────────────────────

class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object with UTC timestamp."""

    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        payload: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc)
                         .strftime("%Y-%m-%dT%H:%M:%S.") +
                         f"{int(record.msecs):03d}Z",
            "level": record.levelname,
        }
        for key, value in record.__dict__.items():
            if key not in logging.LogRecord.__dict__ and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, default=str, ensure_ascii=False)


# ── File handler setup ────────────────────────────────────────────────────────

_LOG_FILE = Path(__file__).parents[4] / "log" / "financial_news.log"
_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

_file_handler = RotatingFileHandler(
    _LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_file_handler.setFormatter(_JsonFormatter())
_file_handler.setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(_file_handler)

# ── Timezone ──────────────────────────────────────────────────────────────────

# set timezone to UTC
os.environ["TZ"] = "UTC"
time.tzset()

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


# ─── Utils ────────────────────────────────────────────────────────────────────

def _clean_html(text: str) -> str:
    """Strip basic HTML tags from text."""
    import re
    text = re.sub(r"<[^>]+>", "", text)
    for entity, char in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&nbsp;", " ")):
        text = text.replace(entity, char)
    text = re.sub(r'\s+', ' ', text)  # collapse whitespace
    return text.strip()


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


# ─── Public API ───────────────────────────────────────────────────────────────

def fetch_news() -> list[dict]:
    """
    Fetch financial news from RSS feeds.

    Returns:
        List of news items with title, url, published, summary, source.
    """
    if not _FEEDPARSER_AVAILABLE:
        return [{"error": "feedparser not installed.", "install": "pip install feedparser"}]

    current = datetime.now()
    previous = current - timedelta(days=1)

    feed_urls = [
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100727362",
        "https://www.dailyforex.com/rss/forexnews.xml",
        "https://news.instaforex.com/news",
        "https://www.investing.com/rss/forex_Fundamental.rss",
        "https://investinglive.com/feed/news",
        "https://www.myfxbook.com/rss/latest-forex-news",
    ]

    logger.info(
        "fetch_news called",
        extra={
            "event": "fetch_start",
            "feed_count": len(feed_urls),
            "feed_urls": feed_urls,
            "filter_from": previous.isoformat(),
            "filter_to": current.isoformat(),
        },
    )

    results: list[dict] = []

    for feed_url in feed_urls:
        try:
            feed = feedparser.parse(feed_url)

            bozo_exc = str(feed.get("bozo_exception", "")) if feed.get("bozo") else None
            http_status = feed.get("status")
            total_entries = len(feed.entries)

            logger.info(
                "feed response received",
                extra={
                    "event": "feed_response",
                    "feed_url": feed_url,
                    "http_status": http_status,
                    "bozo": bool(feed.get("bozo")),
                    "bozo_exception": bozo_exc,
                    "total_entries": total_entries,
                },
            )

            for entry in feed.entries:
                title = entry.get("title", "")

                # Parse date — skip if invalid
                try:
                    raw_published = entry.get("published", "")
                    pub_dt = parsedate_to_datetime(raw_published).replace(tzinfo=None)
                except Exception as exc:
                    logger.warning(
                        "could not parse entry date — skipped",
                        extra={
                            "event": "entry_date_error",
                            "feed_url": feed_url,
                            "title": title,
                            "raw_published": entry.get("published", ""),
                            "error": str(exc),
                        },
                    )
                    continue

                if not (previous <= pub_dt <= current):
                    logger.debug(
                        "entry outside date filter — skipped",
                        extra={
                            "event": "entry_skipped",
                            "feed_url": feed_url,
                            "title": title,
                            "published": pub_dt.isoformat(),
                            "filter_from": previous.isoformat(),
                            "filter_to": current.isoformat(),
                        },
                    )
                    continue

                # Resolve summary — merge if both present and differ
                raw_summary = _clean_html(entry.get("summary", ""))
                raw_description = _clean_html(entry.get("description", ""))

                if raw_summary and raw_description and raw_summary != raw_description:
                    summary = f"{raw_summary} {raw_description}"
                else:
                    summary = raw_summary or raw_description

                if summary.lower() in ("none", "-", ""):
                    summary = ""

                # Resolve URL
                url = entry.get("link", "")
                if not url:
                    links = entry.get("links", [])
                    url = links[0].get("href", "") if links else ""

                results.append({
                    "title":     _clean_html(title),
                    "url":       url,
                    "published": pub_dt,
                    "summary":   summary,
                    "source":    _derive_source(url),
                })

        except Exception as exc:
            logger.warning(
                "error fetching feed — skipped",
                extra={
                    "event": "feed_error",
                    "feed_url": feed_url,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                },
            )
            continue

    sorted_results = sorted(results, key=lambda x: x["published"], reverse=True)

    logger.info(
        "fetch completed",
        extra={
            "event": "fetch_success",
            "result_count": len(sorted_results),
            "titles": [r.get("title", "") for r in sorted_results],
        },
    )

    return sorted_results


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
