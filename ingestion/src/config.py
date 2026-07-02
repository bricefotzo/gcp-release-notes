"""Environment configuration for the release-notes ingestion job."""

import os


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


# Which upstream source to pull from: "bigquery" or "rss".
SOURCE_MODE = (_env("SOURCE_MODE", "bigquery") or "bigquery").strip().lower()

# Public source table (read-only; the public dataset itself is free to
# read, query jobs are billed to DEST_PROJECT_ID).
SOURCE_PROJECT_ID = _env("SOURCE_PROJECT_ID", "bigquery-public-data")
SOURCE_DATASET_ID = _env("SOURCE_DATASET_ID", "google_cloud_release_notes")
SOURCE_TABLE_ID = _env("SOURCE_TABLE_ID", "release_notes")

# RSS feed, used only when SOURCE_MODE=rss. See src/sources/rss_source.py
# for important caveats about how reliable the field mapping is.
RSS_FEED_URL = _env("RSS_FEED_URL", "https://cloud.google.com/feeds/gcp-release-notes.xml")

# Destination — your own project.
DEST_PROJECT_ID = _env("DEST_PROJECT_ID") or _env("PROJECT_ID")
DEST_DATASET_ID = _env("DEST_DATASET_ID", "gcp_release_notes")
DEST_TABLE_ID = _env("DEST_TABLE_ID", "release_notes")
DEST_LOCATION = _env("DEST_LOCATION", "US")

# Safety overlap so a watermark-based incremental pull doesn't miss notes
# that get backfilled/corrected a few days after their published_at date.
# Safe to keep even if it re-fetches a few days of rows every run: the
# loader dedupes by content hash, so re-fetched rows are simply skipped.
WATERMARK_OVERLAP_DAYS = int(_env("WATERMARK_OVERLAP_DAYS", "3"))

# Only used when the destination table is empty (first run), and only in
# SOURCE_MODE=bigquery — the public table has years of history. RSS mode
# ignores this; feeds only carry whatever the publisher currently keeps.
INITIAL_BACKFILL_DAYS = int(_env("INITIAL_BACKFILL_DAYS", "730"))


def source_table_fqn() -> str:
    return f"{SOURCE_PROJECT_ID}.{SOURCE_DATASET_ID}.{SOURCE_TABLE_ID}"


def dest_table_fqn() -> str:
    return f"{DEST_PROJECT_ID}.{DEST_DATASET_ID}.{DEST_TABLE_ID}"


def validate() -> None:
    if SOURCE_MODE not in ("bigquery", "rss"):
        raise ValueError(f"SOURCE_MODE must be 'bigquery' or 'rss', got {SOURCE_MODE!r}")
    if not DEST_PROJECT_ID:
        raise ValueError("Missing required env var: DEST_PROJECT_ID (or PROJECT_ID)")
