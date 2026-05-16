"""
BigQuery client initialization using Application Default Credentials (ADC).

Auth strategy — no JSON key required:
  LOCAL     → gcloud auth application-default login
              ADC picks up ~/.config/gcloud/application_default_credentials.json
  CLOUD RUN → ADC picks up the service account attached at deploy time
              via the GCE metadata server (transparent, no config needed)

The bigquery.Client() constructor with no arguments uses ADC automatically
in both environments.
"""

import os
import logging

from google.cloud import bigquery
from google.auth import default as google_auth_default

logger = logging.getLogger(__name__)

# Billing project for BigQuery jobs.
# The public dataset (bigquery-public-data) is free to read,
# but query jobs are billed to your own project.
BILLING_PROJECT = os.environ.get("BILLING_PROJECT_ID") or os.environ.get("PROJECT_ID")


def init_bq_client() -> bigquery.Client:
    """
    Initialize a BigQuery client using ADC.

    No JSON key or explicit credential path needed.
    Works identically locally (user ADC) and on Cloud Run (attached SA).
    """
    if not BILLING_PROJECT:
        raise ValueError(
            "BILLING_PROJECT_ID or PROJECT_ID env var must be set "
            "to bill BigQuery jobs to your project."
        )

    try:
        credentials, detected_project = google_auth_default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        logger.info(
            "ADC initialized. Detected project: %s. Billing project: %s",
            detected_project,
            BILLING_PROJECT,
        )
    except Exception as e:
        raise RuntimeError(
            "Failed to initialize ADC. "
            "Locally: run `gcloud auth application-default login`. "
            "On Cloud Run: attach a service account with BigQuery roles."
        ) from e

    return bigquery.Client(
        project=BILLING_PROJECT,
        credentials=credentials,
    )


# Module-level client — initialized in the FastAPI lifespan context manager
bq_client: bigquery.Client | None = None


def get_bigquery_client() -> bigquery.Client:
    """Return the initialized BigQuery client. Call init_bq_client() first."""
    if bq_client is None:
        raise RuntimeError("BigQuery client not initialized. Call init_bq_client() first.")
    return bq_client

