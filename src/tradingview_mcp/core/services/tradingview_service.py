from __future__ import annotations

import json
import logging
import os
import time
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta

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
        # Merge any extra fields passed via extra={}
        for key, value in record.__dict__.items():
            if key not in logging.LogRecord.__dict__ and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, default=str, ensure_ascii=False)


# ── File handler setup ────────────────────────────────────────────────────────

_LOG_FILE = Path(os.environ.get("LOG_DIR", "log")) / "tradingview_feed.log"
_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

_file_handler = RotatingFileHandler(
    _LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_file_handler.setFormatter(_JsonFormatter())
_file_handler.setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(_file_handler)
# Keep existing basicConfig for console output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# ── Timezone ──────────────────────────────────────────────────────────────────

os.environ["TZ"] = "UTC"
time.tzset()

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


_FEED_URL = "https://www.tradingview.com/feed/?symbol=xauusd"


def fetch_tradingview_feed() -> list[dict]:
    if not _FEEDPARSER_AVAILABLE:
        return [{"error": "feedparser not installed.", "install": "pip install feedparser"}]

    current = datetime.now()
    previous = current.replace(hour=0, minute=0, second=0) - timedelta(days=1)

    logger.info(
        "fetch_tradingview_feed called",
        extra={
            "event": "fetch_start",
            "feed_url": _FEED_URL,
            "filter_from": previous.isoformat(),
            "filter_to": current.isoformat(),
        },
    )

    results: list[dict] = []
    try:
        feed = feedparser.parse(_FEED_URL)

        bozo_exc = str(feed.get("bozo_exception", "")) if feed.get("bozo") else None
        http_status = feed.get("status")
        total_entries = len(feed.entries)

        logger.info(
            "feedparser response received",
            extra={
                "event": "fetch_response",
                "http_status": http_status,
                "bozo": bool(feed.get("bozo")),
                "bozo_exception": bozo_exc,
                "total_entries": total_entries,
            },
        )

        for entry in feed.entries:
            title = entry.get("title", "")
            try:
                raw_published = entry.get("published", "")
                pub_dt = parsedate_to_datetime(raw_published).replace(tzinfo=None)

                if not (previous <= pub_dt <= current):
                    logger.debug(
                        "entry outside date filter — skipped",
                        extra={
                            "event": "entry_skipped",
                            "title": title,
                            "published": pub_dt.isoformat(),
                            "filter_from": previous.isoformat(),
                            "filter_to": current.isoformat(),
                        },
                    )
                    continue

                summary_raw = entry.get("summary_detail", "")
                summary_detail = _clean_html(
                    summary_raw.get("value", "") if isinstance(summary_raw, dict) else ""
                )
                summary = _clean_html(entry.get("summary", ""))
                conclusion = summary if summary == summary_detail else f"{summary} {summary_detail}"

                content_list = entry.get("content", [])
                content = _clean_html(content_list[0].get("value", "") if content_list else "")

                results.append({
                    "title": title,
                    "title_detail": entry.get("title_detail", ""),
                    "url": entry.get("links", ""),
                    "published": pub_dt,
                    "summary": conclusion,
                    "content": content,
                })

            except Exception as exc:
                logger.warning(
                    "error processing feed entry — skipped",
                    extra={
                        "event": "entry_error",
                        "title": title,
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                    },
                )
                continue

    except Exception as exc:
        logger.error(
            "fatal error fetching tradingview feed",
            extra={
                "event": "fetch_error",
                "error": str(exc),
                "traceback": traceback.format_exc(),
            },
        )
        raise

    sorted_results = sorted(results, key=lambda x: x.get("published"), reverse=True)

    logger.info(
        "fetch completed",
        extra={
            "event": "fetch_success",
            "result_count": len(sorted_results),
            "titles": [r.get("title", "") for r in sorted_results],
        },
    )

    return {
        'tradingview_feed_data': sorted_results
    }
