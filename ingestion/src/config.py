"""Environment configuration for the release-notes ingestion job."""

import os


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def _env_list(name: str, default: str) -> list[str]:
    raw = _env(name, default) or ""
    return [p.strip().upper() for p in raw.split(",") if p.strip()]


# Which platforms to ingest this run, e.g. "GCP" or "GCP,AWS,AZURE". Each
# name must have a factory registered in src/providers/__init__.py.
PLATFORMS = _env_list("PLATFORMS", "GCP")

# --- GCP provider config (src/providers/gcp.py) ---
GCP_SOURCE_MODE = (_env("GCP_SOURCE_MODE", "bigquery") or "bigquery").strip().lower()
GCP_SOURCE_PROJECT_ID = _env("GCP_SOURCE_PROJECT_ID", "bigquery-public-data")
GCP_SOURCE_DATASET_ID = _env("GCP_SOURCE_DATASET_ID", "google_cloud_release_notes")
GCP_SOURCE_TABLE_ID = _env("GCP_SOURCE_TABLE_ID", "release_notes")
GCP_RSS_FEED_URL = _env("GCP_RSS_FEED_URL", "https://cloud.google.com/feeds/gcp-release-notes.xml")

# --- Destination — your own project. Shared by every platform: one table,
# discriminated by the `platform` column. ---
DEST_PROJECT_ID = _env("DEST_PROJECT_ID") or _env("PROJECT_ID")
DEST_DATASET_ID = _env("DEST_DATASET_ID", "cloud_release_notes")
DEST_TABLE_ID = _env("DEST_TABLE_ID", "release_notes")
DEST_LOCATION = _env("DEST_LOCATION", "US")

# Safety overlap so a watermark-based incremental pull doesn't miss notes
# that get backfilled/corrected a few days after their published_at date.
# Safe to keep even if it re-fetches a few days of rows every run: the
# loader dedupes by content hash, so re-fetched rows are simply skipped.
WATERMARK_OVERLAP_DAYS = int(_env("WATERMARK_OVERLAP_DAYS", "3"))

# Only used when a platform has no rows yet in the destination table
# (first run for that platform), and only meaningful for sources with deep
# history (e.g. GCP's BigQuery source). Feed-based sources ignore this —
# feeds only carry whatever the publisher currently keeps in them.
INITIAL_BACKFILL_DAYS = int(_env("INITIAL_BACKFILL_DAYS", "730"))


def dest_table_fqn() -> str:
    return f"{DEST_PROJECT_ID}.{DEST_DATASET_ID}.{DEST_TABLE_ID}"


def validate() -> None:
    if not DEST_PROJECT_ID:
        raise ValueError("Missing required env var: DEST_PROJECT_ID (or PROJECT_ID)")
    if not PLATFORMS:
        raise ValueError("PLATFORMS must list at least one platform, e.g. PLATFORMS=GCP")
    if GCP_SOURCE_MODE not in ("bigquery", "rss"):
        raise ValueError(f"GCP_SOURCE_MODE must be 'bigquery' or 'rss', got {GCP_SOURCE_MODE!r}")
