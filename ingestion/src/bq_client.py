"""
BigQuery client for the ingestion job.

Same ADC-based approach as backend/src/bq.py: no JSON key needed locally
(gcloud auth application-default login) or on Cloud Run (attached SA).
"""

import logging

from google.auth import default as google_auth_default
from google.cloud import bigquery

from src import config

logger = logging.getLogger(__name__)


def init_bq_client() -> bigquery.Client:
    credentials, detected_project = google_auth_default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    logger.info(
        "ADC initialized. Detected project: %s. Destination/billing project: %s",
        detected_project,
        config.DEST_PROJECT_ID,
    )
    return bigquery.Client(project=config.DEST_PROJECT_ID, credentials=credentials)
