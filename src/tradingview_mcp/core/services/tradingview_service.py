from __future__ import annotations

import logging

# set datetime
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

tz = ZoneInfo("Asia/Jakarta")

today = datetime.now(tz)
yesterday = today - timedelta(days=1)

today_first_format = today.strftime("%d %b %Y")
today_second_format = today.strftime("%b %d, %Y")

yesterday_first_format = yesterday.strftime("%d %b %Y")
yesterday_second_format = yesterday.strftime("%b %d, %Y")

try:
    import feedparser
    _FEEDPARSER_AVAILABLE = True
except ImportError:
    _FEEDPARSER_AVAILABLE = False

def _clean_html(text: str) -> str:
    """Strip basic HTML tags from text."""
    import re
    text = re.sub(r"<[^>]+>", "", text)
    for entity, char in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&nbsp;", " ")):
        text = text.replace(entity, char)
    return text.strip()

def fetch_tradingview_feed() -> list[dict]:
    """
    Fetch Tradingview feed.

    Returns:
        List of news items with title, url, published, summary, source.
    """
    if not _FEEDPARSER_AVAILABLE:
        return [{
            "error": "feedparser not installed. Run: pip install feedparser",
            "install": "pip install feedparser"
        }]

    results: list[dict] = []
    try:
      feed = feedparser.parse("https://www.tradingview.com/feed/?symbol=xauusd")
      # source_name = feed.feed.get("title", feed_info["name"])

      logger.info(
          "Timezone: %s | today=%s / %s | yesterday=%s / %s",
          tz, today_first_format, today_second_format,
          yesterday_first_format, yesterday_second_format,
      )
      logger.info("Feed entries before filter: %d", len(feed.entries))

      for entry in feed.entries:
        # Filter only yesterday - today news
        if today_first_format in entry.published or today_second_format in entry.published or yesterday_first_format in entry.published or yesterday_second_format in entry.published :
          results.append({
              "title": entry.get('title', ''),
              "title_detail": entry.get('title_detail', ''),
              "url": entry.get("links", ''),
              "published": entry.get("published", ''),
              "summary": _clean_html(entry.get('summary', '')),
              "summary_detail": entry.get('summary_detail', ''),
              "content": entry.get('content', '')
          })

    except Exception:
      raise

    logger.info("Feed entries after filter: %d", len(results))
    return results