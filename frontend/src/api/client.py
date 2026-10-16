"""Backend API client — all cached fetch functions."""
import os
import re
from datetime import date, timedelta

import pandas as pd
import requests
import streamlit as st

BACKEND_URL = os.environ.get("BACKEND_URL", "http://back:8000")

_TAG_RE = re.compile(r"<[^>]+>")


@st.cache_data(ttl=3600, show_spinner="Loading filters...")
def load_filter_options() -> dict:
    resp = requests.get(f"{BACKEND_URL}/api/filter-options", timeout=30)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=300, show_spinner="Fetching release notes...")
def fetch_release_notes(
    types_key: tuple,
    products_key: tuple,
    start_date_str: str,
    end_date_str: str,
    search: str,
    page: int,
    page_size: int,
) -> dict:
    params: dict = {
        "start_date": start_date_str,
        "end_date": end_date_str,
        "search": search,
        "page": page,
        "page_size": page_size,
    }
    for t in types_key:
        params.setdefault("types", [])
        if isinstance(params["types"], list):
            params["types"].append(t)
    for p in products_key:
        params.setdefault("products", [])
        if isinstance(params["products"], list):
            params["products"].append(p)
    resp = requests.get(f"{BACKEND_URL}/api/release-notes", params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=3600, show_spinner="Fetching time series data...")
def fetch_time_series() -> list:
    return requests.get(f"{BACKEND_URL}/api/insights/time-series", timeout=30).json()


@st.cache_data(ttl=3600, show_spinner="Fetching type distribution...")
def fetch_type_distribution() -> list:
    return requests.get(f"{BACKEND_URL}/api/insights/type-distribution", timeout=30).json()


@st.cache_data(ttl=3600, show_spinner="Fetching top products...")
def fetch_top_products() -> list:
    return requests.get(f"{BACKEND_URL}/api/insights/top-products", timeout=30).json()


@st.cache_data(ttl=3600, show_spinner="Fetching heatmap data...")
def fetch_heatmap() -> list:
    return requests.get(f"{BACKEND_URL}/api/insights/heatmap", timeout=30).json()


@st.cache_data(ttl=300, show_spinner="Checking for new notes since your last visit...")
def fetch_new_count(since_date: str, products_key: tuple) -> int:
    try:
        start = str(date.fromisoformat(since_date) + timedelta(days=1))
    except Exception:
        return 0
    if start > str(date.today()):
        return 0
    params = [
        ("start_date", start),
        ("end_date", str(date.today())),
        ("page", 1),
        ("page_size", 1),
    ]
    for p in products_key:
        params.append(("products", p))
    try:
        resp = requests.get(f"{BACKEND_URL}/api/release-notes", params=params, timeout=10)
        resp.raise_for_status()
        return int(resp.json()["total"])
    except Exception:
        return 0


@st.cache_data(ttl=1800, show_spinner="Fetching breaking changes...")
def fetch_breaking_changes(
    products_key: tuple = (),
    start_date_str: str = "",
    end_date_str: str = "",
) -> dict:
    params = [
        ("types", "BREAKING_CHANGE"),
        ("types", "DEPRECATION"),
        ("start_date", start_date_str),
        ("end_date", end_date_str),
        ("page", 1),
        ("page_size", 200),
    ]
    for p in products_key:
        params.append(("products", p))
    resp = requests.get(f"{BACKEND_URL}/api/release-notes", params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=300, show_spinner="Fetching export notes...")
def fetch_export_notes(
    types_key: tuple,
    products_key: tuple,
    start_date_str: str,
    end_date_str: str,
    search: str,
    max_rows: int = 1000,
) -> pd.DataFrame:
    params = [
        ("start_date", start_date_str),
        ("end_date", end_date_str),
        ("search", search),
        ("page", 1),
        ("page_size", max_rows),
    ]
    for t in types_key:
        params.append(("types", t))
    for p in products_key:
        params.append(("products", p))
    resp = requests.get(f"{BACKEND_URL}/api/release-notes", params=params, timeout=60)
    resp.raise_for_status()
    return pd.DataFrame(resp.json()["data"])


def to_markdown_digest(df: pd.DataFrame, platform: str, start: date, end: date) -> str:
    def strip_html(text: str) -> str:
        return _TAG_RE.sub("", str(text or "")).strip()

    lines = [
        f"# {platform} Release Notes Digest",
        "",
        f"**Period:** {start.strftime('%B %d, %Y')} – {end.strftime('%B %d, %Y')}  ",
        f"**Total notes:** {len(df)}  ",
        f"**Generated:** {date.today().strftime('%B %d, %Y')}",
        "",
        "---",
        "",
    ]
    for product, group in df.groupby("product_name"):
        lines.append(f"## {product}")
        lines.append("")
        for _, row in group.sort_values("published_at").iterrows():
            pub = pd.to_datetime(row["published_at"]).strftime("%Y-%m-%d")
            rtype = row.get("release_note_type", "")
            lines.append(f"**[{rtype}]** `{pub}`")
            lines.append("")
            lines.append(strip_html(row.get("description", "")))
            lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)
