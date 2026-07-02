"""
Entrypoint for the release-notes ingestion Cloud Run Job.

Pulls new release notes from either the public BigQuery dataset or
Google's release-notes RSS feed (SOURCE_MODE) and merges them into your
own BigQuery table, idempotently. Designed to run once a day via Cloud
Scheduler -> Cloud Run Jobs. See README.md for deployment steps.
"""

import datetime as dt
import logging
import sys

from src import config
from src.bq_client import init_bq_client
from src.loader import ensure_dataset_and_table, get_watermark, merge_new_rows
from src.sources import bigquery_source, rss_source

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run() -> int:
    config.validate()
    logger.info(
        "Starting ingestion run: source_mode=%s dest=%s",
        config.SOURCE_MODE,
        config.dest_table_fqn(),
    )

    client = init_bq_client()
    ensure_dataset_and_table(client)

    watermark = get_watermark(client)
    if watermark is None:
        since = dt.date.today() - dt.timedelta(days=config.INITIAL_BACKFILL_DAYS)
        logger.info("Destination table is empty (first run) — backfilling from %s", since)
    else:
        since = watermark - dt.timedelta(days=config.WATERMARK_OVERLAP_DAYS)
        logger.info(
            "Destination watermark is %s — pulling since %s (%d day overlap)",
            watermark,
            since,
            config.WATERMARK_OVERLAP_DAYS,
        )

    if config.SOURCE_MODE == "bigquery":
        df = bigquery_source.fetch_new_rows(client, since)
    else:
        df = rss_source.fetch_new_rows(since)

    inserted = merge_new_rows(client, df, source=config.SOURCE_MODE)
    logger.info(
        "Done. source=%s fetched=%d inserted=%d skipped_as_duplicate=%d",
        config.SOURCE_MODE,
        len(df),
        inserted,
        len(df) - inserted,
    )
    return 0


if __name__ == "__main__":
    sys.exit(run())
