"""Pull incremental rows from the public BigQuery release-notes dataset."""

import datetime as dt
import logging

import pandas as pd
from google.cloud import bigquery

from src import config

logger = logging.getLogger(__name__)


def fetch_new_rows(client: bigquery.Client, since: dt.date) -> pd.DataFrame:
    """Return rows from the public dataset published on/after `since`.

    `since` is already backed off by WATERMARK_OVERLAP_DAYS by the caller,
    so recently corrected/backfilled notes aren't missed.
    """
    query = f"""
    SELECT
        description,
        release_note_type,
        published_at,
        product_name,
        product_version_name
    FROM `{config.source_table_fqn()}`
    WHERE published_at >= @since
    ORDER BY published_at
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("since", "DATE", since)]
    )
    df = client.query(query, job_config=job_config).to_dataframe()
    logger.info("BigQuery source: fetched %d rows published on/after %s", len(df), since)
    return df
