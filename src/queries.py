"""BigQuery queries for release notes."""

import datetime
import pandas as pd
import streamlit as st
from google.cloud.bigquery import Client


def execute_query(query: str, client: Client) -> pd.DataFrame:
    """Execute a BigQuery query and return a DataFrame."""
    try:
        job = client.query(query)
        results = [dict(row) for row in job.result()]
        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"Query failed: {str(e)}")
        st.code(query, language="sql")
        return pd.DataFrame()


def query_release_notes(
    release_types: list,
    product_names: list,
    start_date,
    end_date,
    search_text: str,
    limit: int,
    offset: int,
    client: Client,
    table_name: str,
) -> tuple[pd.DataFrame, int]:
    """Query release notes with filters; returns (results_df, total_count)."""
    where_clauses = []
    query_params = []

    if release_types:
        placeholders = ", ".join(["?"] * len(release_types))
        where_clauses.append(f"release_note_type IN ({placeholders})")
        query_params.extend(release_types)
    if product_names:
        placeholders = ", ".join(["?"] * len(product_names))
        where_clauses.append(f"product_name IN ({placeholders})")
        query_params.extend(product_names)
    if start_date and end_date:
        where_clauses.append("published_at BETWEEN ? AND ?")
        query_params.extend([start_date.isoformat(), end_date.isoformat()])
    if search_text:
        where_clauses.append("LOWER(description) LIKE ?")
        query_params.append(f"%{search_text.lower()}%")

    where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
    formatted_where = where_clause
    for param in query_params:
        if isinstance(param, str):
            escaped = param.replace("'", "''")
            formatted_where = formatted_where.replace("?", f"'{escaped}'", 1)
        else:
            formatted_where = formatted_where.replace("?", str(param), 1)

    query = f"""
    SELECT description, release_note_type, published_at, product_name, product_version_name
    FROM `{table_name}`
    WHERE {formatted_where}
    ORDER BY published_at DESC
    LIMIT {limit}
    OFFSET {offset}
    """
    count_query = f"""
    SELECT COUNT(*) as total FROM `{table_name}` WHERE {formatted_where}
    """
    results_df = client.query(query).to_dataframe()
    count_df = client.query(count_query).to_dataframe()
    return results_df, count_df["total"][0]


@st.cache_data(ttl=3600)
def load_release_note_types(_client: Client, table_name: str) -> list:
    """Load distinct release_note_type values."""
    query = f"""
    SELECT DISTINCT release_note_type FROM `{table_name}`
    WHERE release_note_type IS NOT NULL ORDER BY release_note_type
    """
    df = execute_query(query, _client)
    if df.empty or "release_note_type" not in df.columns:
        return []
    return df["release_note_type"].tolist()


@st.cache_data(ttl=3600)
def load_product_names(_client: Client, table_name: str) -> list:
    """Load distinct product_name values."""
    query = f"""
    SELECT DISTINCT product_name FROM `{table_name}`
    WHERE product_name IS NOT NULL ORDER BY product_name
    """
    df = execute_query(query, _client)
    if df.empty or "product_name" not in df.columns:
        return []
    return df["product_name"].tolist()


@st.cache_data(ttl=3600)
def get_date_range(_client: Client, table_name: str) -> tuple:
    """Return (min_date, max_date) for published_at in the table."""
    query = f"""
    SELECT MIN(published_at) as min_date, MAX(published_at) as max_date
    FROM `{table_name}`
    """
    df = execute_query(query, _client)
    today = datetime.date.today()
    default_start = today - datetime.timedelta(days=365)
    if df.empty or "min_date" not in df.columns or "max_date" not in df.columns:
        return default_start, today
    min_date = df["min_date"][0] if pd.notna(df["min_date"][0]) else default_start
    max_date = df["max_date"][0] if pd.notna(df["max_date"][0]) else today
    return min_date, max_date
