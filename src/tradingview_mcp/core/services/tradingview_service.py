from __future__ import annotations

import logging, os, time

from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# set timezone to UTC
os.environ["TZ"] = "UTC"
time.tzset()

current = datetime.now()
previous = current.replace(hour=0, minute=0, second=0) - timedelta(days=1)

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
    text = re.sub(r'\s+', ' ', text)  # collapse whitespace
    return text.strip()

def fetch_tradingview_feed() -> list[dict]:
    if not _FEEDPARSER_AVAILABLE:
        return [{"error": "feedparser not installed.", "install": "pip install feedparser"}]

    results: list[dict] = []
    try:
        feed = feedparser.parse("https://www.tradingview.com/feed/?symbol=xauusd")
        for entry in feed.entries:
            raw_published = entry.get("published", "")

            pub_dt = parsedate_to_datetime(raw_published).replace(tzinfo=None)
            summary = _clean_html(entry.get("summary", ""))
            summary_detail = _clean_html(entry.get("summary_detail", "").get('value'))
            conclusion = summary if summary == summary_detail else f'{summary} {summary_detail}'

            if previous <= pub_dt <= current:
              results.append({
                  "title": entry.get("title", ""),
                  "title_detail": entry.get("title_detail", ""),
                  "url": entry.get("links", ""),
                  "published": pub_dt,
                  "summary": conclusion,
                  "content": _clean_html(entry.get("content", "")[0].get('value')),
              })
    except Exception:
        raise

    sorted_results = sorted(results, key=lambda x: x.get('published'), reverse=True)
    return sorted_results