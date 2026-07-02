"""Create-if-needed destination table + idempotent incremental load via MERGE."""

import datetime as dt
import hashlib
import logging
import uuid

import pandas as pd
from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from src import config

logger = logging.getLogger(__name__)

_SCHEMA = [
    bigquery.SchemaField("row_hash", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("description", "STRING"),
    bigquery.SchemaField("release_note_type", "STRING"),
    bigquery.SchemaField("published_at", "DATE"),
    bigquery.SchemaField("product_name", "STRING"),
    bigquery.SchemaField("product_version_name", "STRING"),
    bigquery.SchemaField("source", "STRING"),
    bigquery.SchemaField("ingested_at", "TIMESTAMP"),
]


def ensure_dataset_and_table(client: bigquery.Client) -> None:
    dataset_ref = bigquery.DatasetReference(config.DEST_PROJECT_ID, config.DEST_DATASET_ID)
    try:
        client.get_dataset(dataset_ref)
    except NotFound:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = config.DEST_LOCATION
        client.create_dataset(dataset)
        logger.info("Created dataset %s", dataset_ref)

    table_ref = dataset_ref.table(config.DEST_TABLE_ID)
    try:
        client.get_table(table_ref)
    except NotFound:
        table = bigquery.Table(table_ref, schema=_SCHEMA)
        table.time_partitioning = bigquery.TimePartitioning(field="published_at")
        table.clustering_fields = ["product_name", "release_note_type"]
        client.create_table(table)
        logger.info("Created table %s", config.dest_table_fqn())


def get_watermark(client: bigquery.Client) -> dt.date | None:
    """Return MAX(published_at) currently in the destination table, or None if empty."""
    query = f"SELECT MAX(published_at) AS max_date FROM `{config.dest_table_fqn()}`"
    rows = list(client.query(query).result())
    return rows[0]["max_date"] if rows else None


def _row_hash(row: pd.Series) -> str:
    key = "|".join(
        str(row.get(field, ""))
        for field in ("product_name", "release_note_type", "published_at", "description")
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def merge_new_rows(client: bigquery.Client, df: pd.DataFrame, source: str) -> int:
    """Load `df` into a staging table, then MERGE new rows into the destination.

    Dedup key is a content hash (product_name + type + published_at +
    description), not an identity from the source, since neither the
    public BigQuery table nor the RSS feed expose a stable row id. This
    makes re-running the job over an overlapping date range safe.
    """
    if df.empty:
        return 0

    df = df.copy()
    df["published_at"] = pd.to_datetime(df["published_at"]).dt.date
    df["row_hash"] = df.apply(_row_hash, axis=1)
    df["source"] = source
    df["ingested_at"] = pd.Timestamp.now(tz="UTC")
    df = df.drop_duplicates(subset="row_hash")

    staging_table_id = f"{config.dest_table_fqn()}_staging_{uuid.uuid4().hex[:8]}"
    job_config = bigquery.LoadJobConfig(schema=_SCHEMA, write_disposition="WRITE_TRUNCATE")
    client.load_table_from_dataframe(df, staging_table_id, job_config=job_config).result()

    try:
        merge_query = f"""
        MERGE `{config.dest_table_fqn()}` T
        USING `{staging_table_id}` S
        ON T.row_hash = S.row_hash
        WHEN NOT MATCHED THEN
          INSERT (row_hash, description, release_note_type, published_at,
                  product_name, product_version_name, source, ingested_at)
          VALUES (S.row_hash, S.description, S.release_note_type, S.published_at,
                  S.product_name, S.product_version_name, S.source, S.ingested_at)
        """
        job = client.query(merge_query)
        job.result()
        inserted = job.num_dml_affected_rows or 0
        logger.info(
            "Merged %d new row(s) into %s (staging batch had %d candidate rows)",
            inserted,
            config.dest_table_fqn(),
            len(df),
        )
        return inserted
    finally:
        client.delete_table(staging_table_id, not_found_ok=True)
