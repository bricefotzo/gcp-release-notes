"""
Entrypoint for the release-notes ingestion Cloud Run Job.

For every platform in PLATFORMS (default "GCP"), builds the configured
provider (src/providers/), pulls rows published since that platform's own
watermark, and merges them into one shared BigQuery table in your own
project, idempotently. Designed to run once a day via Cloud Scheduler ->
Cloud Run Jobs. See README.md for deployment steps and for how to add a
new platform.
"""

import datetime as dt
import logging
import sys

from src import config
from src.bq_client import init_bq_client
from src.loader import ensure_dataset_and_table, get_watermark, merge_new_rows
from src.providers import build_provider

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _ingest_platform(client, platform: str) -> tuple[int, int]:
    provider = build_provider(platform, client)

    watermark = get_watermark(client, platform)
    if watermark is None:
        since = dt.date.today() - dt.timedelta(days=config.INITIAL_BACKFILL_DAYS)
        logger.info("[%s] no rows yet for this platform — backfilling from %s", platform, since)
    else:
        since = watermark - dt.timedelta(days=config.WATERMARK_OVERLAP_DAYS)
        logger.info(
            "[%s] watermark=%s — pulling since %s (%d day overlap)",
            platform,
            watermark,
            since,
            config.WATERMARK_OVERLAP_DAYS,
        )

    df = provider.fetch_new_rows(since)
    inserted = merge_new_rows(client, df, platform=provider.platform, source=provider.source_id)
    logger.info(
        "[%s] fetched=%d inserted=%d skipped_as_duplicate=%d",
        platform,
        len(df),
        inserted,
        len(df) - inserted,
    )
    return len(df), inserted


def run() -> int:
    config.validate()
    logger.info(
        "Starting ingestion run: platforms=%s dest=%s",
        config.PLATFORMS,
        config.dest_table_fqn(),
    )

    client = init_bq_client()
    ensure_dataset_and_table(client)

    total_fetched = 0
    total_inserted = 0
    for platform in config.PLATFORMS:
        fetched, inserted = _ingest_platform(client, platform)
        total_fetched += fetched
        total_inserted += inserted

    logger.info(
        "Done. platforms=%s total_fetched=%d total_inserted=%d",
        config.PLATFORMS,
        total_fetched,
        total_inserted,
    )
    return 0


if __name__ == "__main__":
    sys.exit(run())
