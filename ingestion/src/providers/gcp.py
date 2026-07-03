"""
GCP release-notes providers.

Two implementations of the same platform, selected by GCP_SOURCE_MODE:

  GCPBigQuerySource  reads bigquery-public-data.google_cloud_release_notes
                     (structured columns, same shape this whole app already
                     uses). Recommended — see the caveat below.

  GCPRssSource       parses https://cloud.google.com/feeds/gcp-release-notes.xml.
                     CAVEAT: the sandboxed environment that wrote this
                     parser could not reach cloud.google.com (network
                     policy blocked it), so the exact live field layout
                     was never directly verified. The mapping follows the
                     standard RSS 2.0 shape Google uses across its other
                     release-notes feeds (title/link/guid/pubDate/
                     description) via `feedparser`, but `product_name`
                     and `release_note_type` are best-effort heuristics,
                     not fields the feed actually provides in structured
                     form. After a first real run, check Cloud Logging
                     for "[GCP/rss] sample parsed row" and compare it
                     against the raw feed; adjust `_parse_entry` below if
                     the mapping is off. Prefer GCPBigQuerySource unless
                     you specifically need the RSS text.
"""

import datetime as dt
import logging
import re

import feedparser
import pandas as pd
import requests
from google.cloud import bigquery

from src import config
from src.providers.base import BaseProvider

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_REQUEST_HEADERS = {"User-Agent": "gcp-release-notes-ingestion/1.0"}

# Keyword -> release_note_type, checked in order against the entry text.
# The RSS feed doesn't carry a structured type field, so this is a
# best-effort heuristic; GCPBigQuerySource is the authoritative source.
_TYPE_KEYWORDS = [
    ("BREAKING_CHANGE", ("breaking change",)),
    ("DEPRECATION", ("deprecat",)),
    ("ANNOUNCEMENT", ("announc",)),
    ("ISSUE", ("known issue", "issue:")),
    ("FIX", ("fix",)),
]
_DEFAULT_TYPE = "FEATURE"


class GCPBigQuerySource(BaseProvider):
    """Reads bigquery-public-data.google_cloud_release_notes.release_notes."""

    platform = "GCP"
    source_id = "bigquery"

    def __init__(self, client: bigquery.Client):
        self._client = client

    def fetch_new_rows(self, since: dt.date) -> pd.DataFrame:
        table_fqn = (
            f"{config.GCP_SOURCE_PROJECT_ID}."
            f"{config.GCP_SOURCE_DATASET_ID}.{config.GCP_SOURCE_TABLE_ID}"
        )
        query = f"""
        SELECT
            description,
            release_note_type,
            published_at,
            product_name,
            product_version_name
        FROM `{table_fqn}`
        WHERE published_at >= @since
        ORDER BY published_at
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("since", "DATE", since)]
        )
        df = self._client.query(query, job_config=job_config).to_dataframe()
        logger.info("[GCP/bigquery] fetched %d rows published on/after %s", len(df), since)
        return df


class GCPRssSource(BaseProvider):
    """Best-effort parser for Google's release-notes RSS feed. See module docstring."""

    platform = "GCP"
    source_id = "rss"

    @staticmethod
    def _strip_html(raw: str) -> str:
        return _TAG_RE.sub("", raw or "").strip()

    @classmethod
    def _infer_type(cls, text: str) -> str:
        lowered = text.lower()
        for note_type, keywords in _TYPE_KEYWORDS:
            if any(k in lowered for k in keywords):
                return note_type
        return _DEFAULT_TYPE

    @staticmethod
    def _entry_published(entry) -> dt.date | None:
        parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        if not parsed:
            return None
        return dt.date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday)

    def _parse_entry(self, entry) -> dict | None:
        published_at = self._entry_published(entry)
        if published_at is None:
            return None
        description = self._strip_html(entry.get("summary") or entry.get("description") or "")
        title = self._strip_html(entry.get("title") or "")
        return {
            "description": description or title,
            "release_note_type": self._infer_type(f"{title} {description}"),
            "published_at": published_at,
            # Google's other release-notes feeds use <title> as the product
            # name; verify this against a live pull of GCP_RSS_FEED_URL.
            "product_name": title or None,
            "product_version_name": None,
        }

    def fetch_new_rows(self, since: dt.date) -> pd.DataFrame:
        resp = requests.get(config.GCP_RSS_FEED_URL, timeout=30, headers=_REQUEST_HEADERS)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)
        if parsed.bozo:
            logger.warning("[GCP/rss] feed parsed with warnings: %s", parsed.bozo_exception)

        rows = [
            row
            for row in (self._parse_entry(entry) for entry in parsed.entries)
            if row and row["published_at"] >= since
        ]

        df = pd.DataFrame(rows)
        logger.info(
            "[GCP/rss] fetched %d rows published on/after %s (feed had %d entries total)",
            len(df),
            since,
            len(parsed.entries),
        )
        if not df.empty:
            logger.info("[GCP/rss] sample parsed row: %s", df.iloc[0].to_dict())
        return df
