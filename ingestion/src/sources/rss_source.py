"""
Pull and parse Google Cloud's release-notes RSS feed.

CAVEAT — read this before relying on SOURCE_MODE=rss in production:
The sandboxed environment that wrote this parser could not reach
cloud.google.com (network policy blocked it), so the exact live field
layout of RSS_FEED_URL was never directly verified here. The mapping
below follows the standard RSS 2.0 shape Google uses across its other
release-notes feeds (title / link / guid / pubDate / description), and
uses `feedparser`, which tolerates both RSS 2.0 and Atom and normalises
the common fields — but `product_name` and `release_note_type` are
best-effort heuristics, not structured fields the feed actually provides.

After the first real run, check Cloud Logging for the "RSS source: sample
parsed row" line and compare it against the raw feed. If `product_name`
or `release_note_type` come out wrong, `_parse_entry()` below is the only
place that needs to change. The BigQuery source (SOURCE_MODE=bigquery) has
none of this uncertainty, since it reads the same structured columns the
rest of this app already uses — prefer it unless you specifically need
the RSS text.
"""

import datetime as dt
import logging
import re

import feedparser
import pandas as pd
import requests

from src import config

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")

# Keyword -> release_note_type, checked in order against the entry text.
# The RSS feed doesn't carry a structured type field, so this is a
# best-effort heuristic; the BigQuery source is the authoritative one.
_TYPE_KEYWORDS = [
    ("BREAKING_CHANGE", ("breaking change",)),
    ("DEPRECATION", ("deprecat",)),
    ("ANNOUNCEMENT", ("announc",)),
    ("ISSUE", ("known issue", "issue:")),
    ("FIX", ("fix",)),
]
_DEFAULT_TYPE = "FEATURE"

_REQUEST_HEADERS = {"User-Agent": "gcp-release-notes-ingestion/1.0"}


def _strip_html(raw: str) -> str:
    return _TAG_RE.sub("", raw or "").strip()


def _infer_type(text: str) -> str:
    lowered = text.lower()
    for note_type, keywords in _TYPE_KEYWORDS:
        if any(k in lowered for k in keywords):
            return note_type
    return _DEFAULT_TYPE


def _entry_published(entry) -> dt.date | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return dt.date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday)


def _parse_entry(entry) -> dict | None:
    published_at = _entry_published(entry)
    if published_at is None:
        return None
    description = _strip_html(entry.get("summary") or entry.get("description") or "")
    title = _strip_html(entry.get("title") or "")
    return {
        "description": description or title,
        "release_note_type": _infer_type(f"{title} {description}"),
        "published_at": published_at,
        # Google's other release-notes feeds use <title> as the product
        # name; verify this against a live pull of RSS_FEED_URL.
        "product_name": title or None,
        "product_version_name": None,
    }


def fetch_new_rows(since: dt.date) -> pd.DataFrame:
    """Return feed entries published on/after `since`."""
    resp = requests.get(config.RSS_FEED_URL, timeout=30, headers=_REQUEST_HEADERS)
    resp.raise_for_status()
    parsed = feedparser.parse(resp.content)
    if parsed.bozo:
        logger.warning("RSS feed parsed with warnings: %s", parsed.bozo_exception)

    rows = [
        row
        for row in (_parse_entry(entry) for entry in parsed.entries)
        if row and row["published_at"] >= since
    ]

    df = pd.DataFrame(rows)
    logger.info(
        "RSS source: fetched %d rows published on/after %s (feed had %d entries total)",
        len(df),
        since,
        len(parsed.entries),
    )
    if not df.empty:
        logger.info("RSS source: sample parsed row: %s", df.iloc[0].to_dict())
    return df
