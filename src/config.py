"""BigQuery dataset and table configuration."""

PROJECT_ID = "bigquery-public-data"
DATASET_ID = "google_cloud_release_notes"
TABLE_ID = "release_notes"


def get_table_name() -> str | None:
    """Return full BigQuery table name."""
    if not (PROJECT_ID and DATASET_ID and TABLE_ID):
        return None
    return f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
