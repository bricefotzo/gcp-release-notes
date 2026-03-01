"""Personalized feed, stats, and preference management."""

from datetime import datetime, timezone

import pandas as pd
import streamlit as st
from bson import ObjectId
from google.cloud.bigquery import Client
from pymongo.database import Database


def _escape(value: str) -> str:
    """Escape single quotes for safe SQL interpolation."""
    return value.replace("'", "\\'")


def _in_clause(values: list[str]) -> str:
    """Build a SQL IN(...) value list from a list of strings."""
    return ", ".join(f"'{_escape(v)}'" for v in values)


def get_user_preferences(db: Database, user_id: str) -> dict:
    """Get user preferences from MongoDB."""
    user = db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return {"products": [], "types": []}
    return user.get("preferences", {"products": [], "types": []})


def save_user_preferences(
    db: Database, user_id: str, products: list, types: list
) -> None:
    """Save user preferences to MongoDB."""
    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "preferences.products": products,
                "preferences.types": types,
                "preferences.updated_at": datetime.now(timezone.utc),
            }
        },
    )


def _build_preference_filter(preferences: dict) -> str:
    """Build WHERE clause fragments from user preferences."""
    clauses = []
    products = preferences.get("products", [])
    types = preferences.get("types", [])
    if products:
        clauses.append(f"product_name IN ({_in_clause(products)})")
    if types:
        clauses.append(f"release_note_type IN ({_in_clause(types)})")
    return " AND ".join(clauses) if clauses else ""


def get_personalized_feed(
    bq_client: Client,
    table_name: str,
    preferences: dict,
    limit: int = 20,
) -> pd.DataFrame:
    """Get recent release notes filtered by user preferences."""
    pref_filter = _build_preference_filter(preferences)
    where = f"WHERE {pref_filter} AND" if pref_filter else "WHERE"

    query = f"""
    SELECT description, release_note_type, published_at,
           product_name, product_version_name
    FROM `{table_name}`
    {where} published_at >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
    ORDER BY published_at DESC
    LIMIT {limit}
    """
    try:
        return bq_client.query(query).to_dataframe()
    except Exception:
        return pd.DataFrame()


def get_personalized_stats(
    bq_client: Client,
    table_name: str,
    preferences: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Get personalized time series and type distribution stats."""
    pref_filter = _build_preference_filter(preferences)
    extra = f"AND {pref_filter}" if pref_filter else ""

    time_query = f"""
    SELECT DATE_TRUNC(published_at, MONTH) as month, COUNT(*) as count
    FROM `{table_name}`
    WHERE published_at BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR)
          AND CURRENT_DATE()
    {extra}
    GROUP BY month ORDER BY month
    """
    types_query = f"""
    SELECT release_note_type, COUNT(*) as count
    FROM `{table_name}`
    WHERE release_note_type IS NOT NULL
      AND published_at BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR)
          AND CURRENT_DATE()
    {extra}
    GROUP BY release_note_type ORDER BY count DESC LIMIT 10
    """
    try:
        time_df = bq_client.query(time_query).to_dataframe()
    except Exception:
        time_df = pd.DataFrame()
    try:
        types_df = bq_client.query(types_query).to_dataframe()
    except Exception:
        types_df = pd.DataFrame()

    return time_df, types_df


def show_preferences_ui(
    db: Database,
    user_id: str,
    product_names: list,
    release_note_types: list,
    current_prefs: dict,
) -> None:
    """Display preferences editor in the sidebar."""
    st.markdown("---")
    st.subheader("Preferences")
    with st.form("preferences_form"):
        selected_products = st.multiselect(
            "Products to follow",
            options=product_names,
            default=[
                p for p in current_prefs.get("products", []) if p in product_names
            ],
        )
        selected_types = st.multiselect(
            "Release note types",
            options=release_note_types,
            default=[
                t for t in current_prefs.get("types", []) if t in release_note_types
            ],
        )
        if st.form_submit_button("Save Preferences", use_container_width=True):
            save_user_preferences(db, user_id, selected_products, selected_types)
            st.session_state["user"]["preferences"] = {
                "products": selected_products,
                "types": selected_types,
            }
            st.success("Preferences saved!")
            st.rerun()
