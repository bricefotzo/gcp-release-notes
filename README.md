# GCP Release Notes Navigator

A Streamlit app that turns **Google Cloud release notes** into searchable insights. Browse and filter official GCP release notes from the BigQuery public dataset.

## Features

- **Search** – Full-text search by keyword in release note descriptions
- **Filters**
  - **Product** – Filter by Google Cloud service or product
  - **Release note type** – Filter by type of change
  - **Date range** – Filter by publication date
- **Notes tab** – Paginated list of release notes as cards (product, type, date, description)
- **Insights tab** – Overview charts:
  - Release notes by month (last 12 months)
  - Distribution of release note types

## Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** – Fast Python package installer and resolver
- **Google Cloud** – Access to BigQuery (app uses public dataset `bigquery-public-data.google_cloud_release_notes.release_notes`)
- **Credentials** – Service account with BigQuery read access

## Setup with uv

### 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# or: pip install uv
```

### 2. Clone and sync

```bash
cd gcp-release-notes
uv sync
```

This creates a virtual environment (if needed) and installs dependencies from `pyproject.toml`.

### 3. Configure credentials

**Option A – Environment variable (local)**

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/your-service-account-key.json
```

**Option B – Streamlit secrets (e.g. Streamlit Cloud)**

Create `.streamlit/secrets.toml`:

```toml
gcp_service_account = """
{
  "type": "service_account",
  "project_id": "your-project-id",
  ...
}
"""
```

Optional: create a `.env` file for other variables; the app loads it via `python-dotenv`.


## Run the app

```bash
uv run streamlit run main.py
```

Open the URL shown in the terminal (usually `http://localhost:8501`).

## Project structure

```
gcp-release-notes/
├── app/
│   ├── __init__.py
│   ├── config.py      # BigQuery project/dataset/table constants
│   ├── bq.py           # BigQuery client (env or Streamlit secrets)
│   ├── queries.py     # execute_query, query_release_notes, load_* filters, get_date_range
│   └── utils.py       # format_description (track-name tabs, markdown)
├── main.py             # Streamlit entrypoint (UI + wiring)
├── pyproject.toml      # uv/pip project and dependencies
└── README.md
```

| Path | Purpose |
|------|---------|
| `main.py` | Streamlit entrypoint: page config, filters, Notes/Insights tabs, pagination |
| `app/config.py` | `PROJECT_ID`, `DATASET_ID`, `TABLE_ID`, `get_table_name()` |
| `app/bq.py` | `get_bigquery_client()` using env or Streamlit secrets |
| `app/queries.py` | BigQuery helpers: `execute_query`, `query_release_notes`, `load_release_note_types`, `load_product_names`, `get_date_range` |
| `app/utils.py` | `format_description()` for release note descriptions (tracks, markdown) |

## Data source

- **Dataset:** `bigquery-public-data.google_cloud_release_notes.release_notes`
- **Fields used:** `description`, `release_note_type`, `published_at`, `product_name`, `product_version_name`

## Optional: Vertex AI

To add Vertex AI later (e.g. summarization), install the optional dependency:

```bash
uv sync --extra vertex
```

Then wire Vertex in your code; the base app does not use it.

## License

Use and modify as you like. Data is from Google Cloud’s public BigQuery datasets.
