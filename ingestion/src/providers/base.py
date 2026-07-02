"""Base interface every cloud-provider ingestion source implements."""

import datetime as dt
from abc import ABC, abstractmethod

import pandas as pd

# Every provider must return a DataFrame with exactly these columns.
# `platform` and `source` are added by the loader, not the provider —
# a provider shouldn't need to know how it's tagged downstream.
ROW_COLUMNS = [
    "description",
    "release_note_type",
    "published_at",
    "product_name",
    "product_version_name",
]


class BaseProvider(ABC):
    """One release-notes source for one cloud platform.

    A platform can have more than one provider implementation (e.g. GCP's
    BigQuery-backed source vs. its RSS-backed source) — config decides
    which one gets instantiated for a given run.
    """

    #: Stored in the destination `platform` column, e.g. "GCP", "AWS", "AZURE".
    platform: str

    #: Stored in the destination `source` column, identifies which concrete
    #: source within the platform produced the row, e.g. "bigquery", "rss".
    source_id: str

    @abstractmethod
    def fetch_new_rows(self, since: dt.date) -> pd.DataFrame:
        """Return rows (columns = ROW_COLUMNS) published on/after `since`."""
        raise NotImplementedError
