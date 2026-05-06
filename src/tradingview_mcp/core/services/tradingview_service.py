from __future__ import annotations

import logging, re

# set datetime
from email.utils import parsedate_to_datetime
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

def fetch_tradingview_feed() -> list[dict]:
    if not _FEEDPARSER_AVAILABLE:
        return [{"error": "feedparser not installed.", "install": "pip install feedparser"}]

    results: list[dict] = []
    try:
        feed = feedparser.parse("https://www.tradingview.com/feed/?symbol=xauusd")
        for entry in feed.entries:
            raw_published = entry.get("published", "")

            if not any(d in raw_published for d in (
                today_first_format, today_second_format,
                yesterday_first_format, yesterday_second_format,
            )):
                continue

            pub_dt = _parse_pubdate(raw_published)

            results.append({
                "title": entry.get("title", ""),
                "title_detail": entry.get("title_detail", ""),
                "url": entry.get("links", ""),
                "published": pub_dt,            # datetime object (or None)
                "published_raw": raw_published,  # keep original string as fallback
                "summary": _clean_html(entry.get("summary", "")),
                "summary_detail": entry.get("summary_detail", ""),
                "content": entry.get("content", ""),
            })
    except Exception:
        raise

    results.sort(key=lambda x: x["published"] or datetime.min.replace(tzinfo=tz), reverse=True)
    return results