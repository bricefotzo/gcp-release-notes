"""
Provider registry.

A "provider" is one release-notes source for one cloud platform (e.g.
GCP's BigQuery-backed source, GCP's RSS-backed source, a future AWS
"What's New" feed). All providers return the same row shape
(`src.providers.base.ROW_COLUMNS`); the loader tags each batch with the
provider's `platform` and `source_id` and merges it into one shared table.

To add a new cloud:
  1. Create src/providers/<platform>.py with a BaseProvider subclass
     (see src/providers/gcp.py for two working examples).
  2. Register a factory for it below with @register("AWS").
  3. Add "AWS" to the PLATFORMS env var.
No other file needs to change — main.py and loader.py are platform-agnostic.
"""

from typing import Callable

from google.cloud import bigquery

from src.providers.base import BaseProvider
from src.providers.gcp import GCPBigQuerySource, GCPRssSource
from src import config

_REGISTRY: dict[str, Callable[[bigquery.Client], BaseProvider]] = {}


def register(platform: str):
    def decorator(factory: Callable[[bigquery.Client], BaseProvider]):
        _REGISTRY[platform.upper()] = factory
        return factory

    return decorator


@register("GCP")
def _build_gcp_provider(bq_client: bigquery.Client) -> BaseProvider:
    if config.GCP_SOURCE_MODE == "rss":
        return GCPRssSource()
    return GCPBigQuerySource(bq_client)


def build_provider(platform: str, bq_client: bigquery.Client) -> BaseProvider:
    try:
        factory = _REGISTRY[platform.upper()]
    except KeyError:
        raise ValueError(
            f"No provider registered for platform {platform!r}. "
            f"Known platforms: {sorted(_REGISTRY)}. "
            "Add one in src/providers/ — see the module docstring."
        ) from None
    return factory(bq_client)
