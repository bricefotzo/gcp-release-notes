"""GCP Release Notes Navigator – Streamlit entrypoint."""

from datetime import date
from pathlib import Path
from typing import cast

import plotly.express as px

import streamlit as st
import streamlit_antd_components as sac
import streamlit.components.v1 as components
from dotenv import load_dotenv
from PIL import Image

from src.bq import get_bigquery_client
from src.config import get_table_name
from src.queries import (
    get_date_range,
    load_product_names,
    load_release_note_types,
    query_release_notes,
)
from src.utils import format_description
from src.db import get_database
from src.auth import show_auth_ui, get_current_user
from src.personalized import (
    get_personalized_feed,
    get_personalized_stats,
    show_preferences_ui,
)
from src.ai_insights import generate_ai_summary

load_dotenv()

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
PAGE_ICON_PATH = Path(__file__).parent / "assets/google.png"
page_icon = Image.open(PAGE_ICON_PATH) if PAGE_ICON_PATH.exists() else None
st.set_page_config(
    page_title="Release Notes Navigator",
    page_icon=page_icon,
    layout="wide",
)
components.html("""
    <!-- Google Analytics -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-4DDTVR6RLY"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){dataLayer.push(arguments);}
      gtag('js', new Date());

      gtag('config', 'G-4DDTVR6RLY');
    </script>
    <script type="text/javascript">
var _iub = _iub || [];
_iub.csConfiguration = {"siteId":4443283,"cookiePolicyId":61007907,"lang":"en","storage":{"useSiteId":true}};
</script>
<script type="text/javascript" src="https://cs.iubenda.com/autoblocking/4443283.js"></script>
<script type="text/javascript" src="//cdn.iubenda.com/cs/gpp/stub.js"></script>
<script type="text/javascript" src="//cdn.iubenda.com/cs/iubenda_cs.js" charset="UTF-8" async></script>
""", height=0)

st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    .stAppHeader {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
sac.buttons(
    [
        sac.ButtonsItem(
            label="Release Notes Navigator",
            icon=sac.BsIcon(name="google", size=30),
        )
    ],
    align="start",
    size="xl",
    variant="link",
    index=None,
)
with st.expander("About this App"):
    st.markdown(
        "The purpose of this app is to turn Cloud release notes into relevant insights."
    )
    st.markdown(
        """Visitors can search by keyword and filter notes by:
- Service or Product
- The type of change
- The release date
"""
    )
    st.markdown("More evolutions will come later.\nFor now it's mainly GCP oriented but we'll add Cloud providers.")

# ---------------------------------------------------------------------------
# BigQuery connection
# ---------------------------------------------------------------------------
_table = get_table_name()
if not _table:
    st.warning("Please configure project/dataset/table in app/config.py")
    st.stop()
table_name = cast(str, _table)

try:
    client = get_bigquery_client()
    client.query(f"SELECT 1 FROM `{table_name}` LIMIT 1").result()
except Exception as e:
    st.error(f"Connection failed: {e}")
    st.error(
        f"Check that table `{table_name}` exists and credentials are set "
        "(GOOGLE_APPLICATION_CREDENTIALS or .streamlit/secrets.toml)."
    )
    st.stop()

# ---------------------------------------------------------------------------
# MongoDB connection (optional – personalization features degrade gracefully)
# ---------------------------------------------------------------------------
db = get_database()

# ---------------------------------------------------------------------------
# Load filter options (needed for search AND preferences UI)
# ---------------------------------------------------------------------------
with st.spinner("Loading filter options..."):
    release_note_types = load_release_note_types(client, table_name) or [
        "Feature",
        "Issue",
        "Announcement",
    ]
    product_names = load_product_names(client, table_name) or [
        "Compute Engine",
        "BigQuery",
        "Cloud Storage",
    ]
    min_date, max_date = get_date_range(client, table_name)

# ---------------------------------------------------------------------------
# Sidebar – Authentication & Preferences
# ---------------------------------------------------------------------------
user = None
with st.sidebar:
    if db is not None:
        st.subheader("Account")
        user = show_auth_ui(db)
        if user:
            show_preferences_ui(
                db,
                user["id"],
                product_names,
                release_note_types,
                user.get("preferences", {}),
            )
    else:
        st.info("Personalization features are unavailable (MongoDB not configured).")

# ---------------------------------------------------------------------------
# Personalized Dashboard (shown at top of homepage when logged in)
# ---------------------------------------------------------------------------
if user and db:
    prefs = user.get("preferences", {})
    has_prefs = bool(prefs.get("products") or prefs.get("types"))

    if has_prefs:
        st.header("Your Dashboard")

        # --- AI Summary ---
        feed_df = get_personalized_feed(client, table_name, prefs, limit=30)

        with st.spinner("Generating AI summary..."):
            summary = generate_ai_summary(db, user["id"], feed_df, prefs)
        if summary:
            with st.container(border=True):
                st.subheader("AI Summary")
                st.markdown(summary)
        elif not feed_df.empty:
            st.info(
                "AI summary is unavailable. Set GOOGLE_API_KEY to enable it."
            )

        # --- Personalized Stats ---
        st.subheader("Your Stats")
        col_ts, col_dist = st.columns(2)
        time_df, types_df = get_personalized_stats(client, table_name, prefs)

        with col_ts:
            if not time_df.empty:
                fig = px.line(
                    time_df,
                    x="month",
                    y="count",
                    title="Your Products – Release Notes by Month",
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No time series data for your tracked products.")

        with col_dist:
            if not types_df.empty:
                fig = px.pie(
                    types_df,
                    values="count",
                    names="release_note_type",
                    title="Your Products – Release Note Types",
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No type distribution data for your tracked products.")

        # --- Personalized Feed ---
        st.subheader("Recent Updates for You")
        if not feed_df.empty:
            for _, row in feed_df.iterrows():
                with st.container():
                    st.markdown(f"### {row['product_name']}")
                    st.markdown(
                        f"**Type:** {row['release_note_type']} | "
                        f"**Published:** {row['published_at'].strftime('%Y-%m-%d')}"
                    )
                    st.markdown("**Description:** ")
                    format_description(row["description"])
                    st.divider()
        else:
            st.info("No recent notes for your tracked products in the last 30 days.")

        st.markdown("---")
    else:
        st.info(
            "Set your product and type preferences in the sidebar to unlock "
            "your personalized dashboard with AI-powered summaries."
        )

# ---------------------------------------------------------------------------
# Search & Filters
# ---------------------------------------------------------------------------
search_text = st.text_input("Search", "")
pn, tn, dr = st.columns(3)
with pn:
    selected_products = st.multiselect("Product name", options=product_names, default=[])
with tn:
    selected_types = st.multiselect(
        "Release note type", options=release_note_types, default=[]
    )
with dr:
    date_range = st.date_input(
        "Date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
apply_filters = st.button("Reload")

# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------
if "page" not in st.session_state:
    st.session_state.page = 1
if "items_per_page" not in st.session_state:
    st.session_state.items_per_page = 5


def next_page():
    st.session_state.page += 1


def prev_page():
    st.session_state.page = max(1, st.session_state.page - 1)


def reset_page():
    st.session_state.page = 1


if apply_filters:
    reset_page()

current_page = st.session_state.page
offset = (current_page - 1) * st.session_state.items_per_page


def _date_range_bounds(
    dr: date | tuple[date, ...], default_start: date, default_end: date
) -> tuple[date, date]:
    if isinstance(dr, tuple) and len(dr) >= 2:
        return dr[0], dr[1]
    if isinstance(dr, tuple) and len(dr) == 1:
        return dr[0], dr[0]
    return default_start, default_end


start_date, end_date = _date_range_bounds(date_range, min_date, max_date)

results, total_count = query_release_notes(
    selected_types,
    selected_products,
    start_date,
    end_date,
    search_text,
    st.session_state.items_per_page,
    offset,
    client,
    table_name,
)

st.write(f"Found {total_count} release notes")

# ---------------------------------------------------------------------------
# Tabs – Notes & Insights (global)
# ---------------------------------------------------------------------------
tab1, tab2 = st.tabs(["Notes", "Insights"])

with tab1:
    st.header("Search Results")
    if not results.empty:
        for _, row in results.iterrows():
            with st.container():
                st.markdown(f"### {row['product_name']}")
                st.markdown(
                    f"**Type:** {row['release_note_type']} | "
                    f"**Published:** {row['published_at'].strftime('%Y-%m-%d')}"
                )
                st.markdown("**Description:** ")
                format_description(row["description"])
                st.divider()
    else:
        st.info("No results found matching your criteria.")

    total_pages = (total_count + st.session_state.items_per_page - 1) // st.session_state.items_per_page
    col1, col2, col3, col4 = st.columns([1, 3, 1, 1])
    with col1:
        if current_page > 1:
            st.button("← Previous", on_click=prev_page)
    with col2:
        st.write(f"Page {current_page} of {total_pages}")
    with col3:
        if current_page < total_pages:
            st.button("Next →", on_click=next_page)
    with col4:
        st.session_state.items_per_page = st.selectbox(
            "", [5, 10, 15, 20, 50], key="items_per_page_select"
        )

with tab2:
    st.header("Release Notes Overview")
    col1, col2 = st.columns(2)
    with col1:
        time_series_query = f"""
        SELECT DATE_TRUNC(published_at, MONTH) as month, COUNT(*) as count
        FROM `{table_name}`
        WHERE published_at BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR) AND CURRENT_DATE()
        GROUP BY month ORDER BY month
        """
        time_df = client.query(time_series_query).to_dataframe()
        fig1 = px.line(
            time_df, x="month", y="count", title="Release Notes by Month (Last 12 Months)"
        )
        st.plotly_chart(fig1, use_container_width=True)
    with col2:
        types_query = f"""
        SELECT release_note_type, COUNT(*) as count
        FROM `{table_name}`
        WHERE release_note_type IS NOT NULL
        GROUP BY release_note_type ORDER BY count DESC LIMIT 10
        """
        types_df = client.query(types_query).to_dataframe()
        fig2 = px.pie(
            types_df,
            values="count",
            names="release_note_type",
            title="Distribution of Release Note Types",
        )
        st.plotly_chart(fig2, use_container_width=True)

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("GCP Release Notes Navigator | By Brice Fotzo")
