"""Release Notes Navigator – Streamlit entrypoint."""

from datetime import date
from pathlib import Path
from typing import cast

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from src.bq import get_bigquery_client
from src.config import get_table_name
from src.queries import (
    get_date_range,
    load_product_names,
    load_release_note_types,
    query_release_notes,
)
from src.utils import format_description, get_type_css_class, get_badge_class

load_dotenv()

# --------------- Page Config ---------------
st.set_page_config(
    page_title="Release Notes Navigator",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------- Load Custom CSS ---------------
CSS_PATH = Path(__file__).parent / "assets" / "style.css"
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text()}</style>", unsafe_allow_html=True)

# --------------- Analytics (hidden iframe) ---------------
components.html(
    """
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
    """,
    height=0,
)

# --------------- BigQuery Connection ---------------
_table = get_table_name()
if not _table:
    st.warning("Please configure project/dataset/table in src/config.py")
    st.stop()
table_name = cast(str, _table)

try:
    client = get_bigquery_client()
    client.query(f"SELECT 1 FROM `{table_name}` LIMIT 1").result()
except Exception as e:
    st.error(f"Connection failed: {e}")
    st.stop()

# --------------- Load Filter Options ---------------
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

# ╔══════════════════════════════════════════════════════════════╗
# ║                        SIDEBAR                              ║
# ╚══════════════════════════════════════════════════════════════╝
with st.sidebar:
    # Brand
    st.markdown(
        """
        <div class="sidebar-brand">
            <div class="sidebar-brand-icon">
                <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm-1 2l5 5h-5V4zM6 20V4h5v7h7v9H6z" fill="#fff"/>
                    <path d="M8 15h8v1.5H8zm0-3h8v1.5H8z" fill="rgba(255,255,255,0.8)"/>
                </svg>
            </div>
            <div>
                <div class="sidebar-brand-text">Release Notes</div>
                <div class="sidebar-brand-sub">Navigator</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Platform selector
    st.markdown("### Platform")
    selected_platform = st.selectbox(
        "Platform",
        options=["Google Cloud"],
        index=0,
        label_visibility="collapsed",
    )

    # Filters
    st.markdown("### Search")
    search_text = st.text_input(
        "Keyword",
        "",
        placeholder="e.g. Kubernetes, IAM, BigQuery...",
        label_visibility="collapsed",
    )

    st.markdown("### Filters")
    selected_products = st.multiselect(
        "Product",
        options=product_names,
        default=[],
        placeholder="All products",
    )
    selected_types = st.multiselect(
        "Type",
        options=release_note_types,
        default=[],
        placeholder="All types",
    )

    st.markdown("### Date Range")
    date_range = st.date_input(
        "Period",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        label_visibility="collapsed",
    )

    st.markdown("")  # spacing
    apply_filters = st.button("Apply Filters", use_container_width=True)

    # About section at bottom of sidebar
    st.markdown("---")
    with st.expander("About this app"):
        st.markdown(
            "Search and explore release notes across cloud platforms. "
            "Filter by product, type, and date to find the changes that matter to you."
        )
        st.markdown(
            "Built with Streamlit, BigQuery, and Plotly. "
            "Currently supporting **Google Cloud**. More platforms coming soon."
        )

# ╔══════════════════════════════════════════════════════════════╗
# ║                      MAIN CONTENT                            ║
# ╚══════════════════════════════════════════════════════════════╝

# --------------- Hero Header ---------------
# Platform icons for the hero badge
_PLATFORM_ICONS = {
    "Google Cloud": '<svg viewBox="0 0 24 24"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#fff"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="rgba(255,255,255,0.85)"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="rgba(255,255,255,0.7)"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="rgba(255,255,255,0.55)"/></svg>',
}

_platform_icon = _PLATFORM_ICONS.get(selected_platform, "")

st.markdown(
    f"""
    <div class="hero-header">
        <div class="hero-platform-badge">
            {_platform_icon}
            <span>{selected_platform}</span>
        </div>
        <p class="hero-title">Release Notes Navigator</p>
        <p class="hero-subtitle">
            Explore and analyze release notes across cloud platforms — search, filter, and gain insights from the latest changes.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# --------------- Pagination State ---------------
if "page" not in st.session_state:
    st.session_state.page = 1
if "items_per_page" not in st.session_state:
    st.session_state.items_per_page = 10


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

# --------------- Query Data ---------------
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

total_pages = max(1, (total_count + st.session_state.items_per_page - 1) // st.session_state.items_per_page)

# --------------- Metrics Row ---------------
active_filters = sum([
    bool(search_text),
    bool(selected_products),
    bool(selected_types),
    start_date != min_date or end_date != max_date,
])

st.markdown(
    f"""
    <div class="metric-container">
        <div class="metric-card">
            <div class="metric-label">Total Results</div>
            <div class="metric-value blue">{total_count:,}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Current Page</div>
            <div class="metric-value">{current_page} <span style="font-size:0.85rem;color:#5F6368;font-weight:400">of {total_pages}</span></div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Active Filters</div>
            <div class="metric-value purple">{active_filters}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Platform</div>
            <div class="metric-value teal" style="font-size:1.1rem">{selected_platform}</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# --------------- Tabs ---------------
tab_notes, tab_insights = st.tabs(["Release Notes", "Insights & Analytics"])

# ╔══════════════════════════════════════════════════════════════╗
# ║                     NOTES TAB                                ║
# ╚══════════════════════════════════════════════════════════════╝
with tab_notes:
    if not results.empty:
        for _, row in results.iterrows():
            type_class = get_type_css_class(row["release_note_type"])
            badge_class = get_badge_class(row["release_note_type"])
            pub_date = row["published_at"].strftime("%b %d, %Y")

            st.markdown(
                f"""
                <div class="note-card {type_class}">
                    <div class="note-card-header">
                        <span class="note-product">{row['product_name']}</span>
                        <div class="note-meta">
                            <span class="note-badge {badge_class}">{row['release_note_type']}</span>
                            <span class="note-date">
                                <svg viewBox="0 0 24 24"><path d="M19 3h-1V1h-2v2H8V1H6v2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V8h14v11zM9 10H7v2h2v-2zm4 0h-2v2h2v-2zm4 0h-2v2h2v-2z"/></svg>
                                {pub_date}
                            </span>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            # Render description using Streamlit markdown (supports track-name tabs)
            with st.container():
                format_description(row["description"])
            st.markdown("<div style='height: 0.25rem'></div>", unsafe_allow_html=True)
    else:
        st.markdown(
            """
            <div class="empty-state">
                <div class="empty-state-icon">🔍</div>
                <div class="empty-state-text">No release notes found</div>
                <div class="empty-state-hint">Try adjusting your filters or search terms</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # --------------- Pagination Controls ---------------
    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
    pcol1, pcol2, pcol3, pcol4, pcol5 = st.columns([1, 1, 2, 1, 1])
    with pcol1:
        if current_page > 1:
            st.button("← Previous", on_click=prev_page, use_container_width=True)
    with pcol2:
        pass
    with pcol3:
        st.markdown(
            f"<div style='text-align:center;padding:0.5rem 0;font-size:0.85rem;color:#5F6368;font-weight:500;'>"
            f"Page {current_page} of {total_pages} &nbsp;·&nbsp; {total_count:,} results"
            f"</div>",
            unsafe_allow_html=True,
        )
    with pcol4:
        pass
    with pcol5:
        if current_page < total_pages:
            st.button("Next →", on_click=next_page, use_container_width=True)

    # Items per page selector
    ipp_col1, ipp_col2, ipp_col3 = st.columns([3, 1, 3])
    with ipp_col2:
        st.session_state.items_per_page = st.selectbox(
            "Per page",
            [5, 10, 15, 20, 50],
            index=[5, 10, 15, 20, 50].index(st.session_state.items_per_page),
            key="items_per_page_select",
        )

# ╔══════════════════════════════════════════════════════════════╗
# ║                    INSIGHTS TAB                              ║
# ╚══════════════════════════════════════════════════════════════╝

# Plotly theme
PLOTLY_LAYOUT = dict(
    font=dict(family="Inter, sans-serif", size=12, color="#3C4043"),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=20, r=20, t=40, b=20),
    title=dict(text="", font=dict(size=14, color="#202124", family="Inter, sans-serif")),
    hoverlabel=dict(
        bgcolor="white",
        font_size=13,
        font_family="Inter, sans-serif",
        font_color="#202124",
        bordercolor="#DADCE0",
    ),
)

CHART_COLORS = [
    "#1A73E8", "#34A853", "#EA4335", "#F9AB00",
    "#9334E6", "#00897B", "#E91E63", "#FF6D00",
]

with tab_insights:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            '<div class="insights-title">Release Activity</div>'
            '<div class="insights-subtitle">Monthly volume over the last 12 months</div>',
            unsafe_allow_html=True,
        )
        time_series_query = f"""
        SELECT DATE_TRUNC(published_at, MONTH) as month, COUNT(*) as count
        FROM `{table_name}`
        WHERE published_at BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR) AND CURRENT_DATE()
        GROUP BY month ORDER BY month
        """
        time_df = client.query(time_series_query).to_dataframe()

        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(
            x=time_df["month"],
            y=time_df["count"],
            mode="lines+markers",
            line=dict(color="#1A73E8", width=2.5, shape="spline"),
            marker=dict(size=7, color="#1A73E8", line=dict(width=2, color="white")),
            fill="tozeroy",
            fillcolor="rgba(26, 115, 232, 0.08)",
            hovertemplate="<b>%{x|%B %Y}</b><br>%{y} release notes<extra></extra>",
        ))
        fig1.update_layout(
            **PLOTLY_LAYOUT,
            xaxis=dict(
                showgrid=False,
                tickformat="%b %Y",
                linecolor="#E8EAED",
                tickfont=dict(size=11, color="#3C4043"),
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor="rgba(232, 234, 237, 0.5)",
                gridwidth=1,
                tickfont=dict(size=11, color="#3C4043"),
            ),
            height=350,
        )
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        st.markdown(
            '<div class="insights-title">Note Type Distribution</div>'
            '<div class="insights-subtitle">Breakdown by release note category</div>',
            unsafe_allow_html=True,
        )
        types_query = f"""
        SELECT release_note_type, COUNT(*) as count
        FROM `{table_name}`
        WHERE release_note_type IS NOT NULL
        GROUP BY release_note_type ORDER BY count DESC LIMIT 10
        """
        types_df = client.query(types_query).to_dataframe()

        fig2 = go.Figure(data=[go.Pie(
            labels=types_df["release_note_type"],
            values=types_df["count"],
            hole=0.55,
            marker=dict(
                colors=CHART_COLORS[:len(types_df)],
                line=dict(color="white", width=2.5),
            ),
            textinfo="label+percent",
            textfont=dict(size=11),
            hovertemplate="<b>%{label}</b><br>%{value:,} notes (%{percent})<extra></extra>",
        )])
        fig2.update_layout(
            **PLOTLY_LAYOUT,
            showlegend=False,
            height=350,
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Additional insights row
    st.markdown("<div style='height: 1rem'></div>", unsafe_allow_html=True)
    col3, col4 = st.columns(2)

    with col3:
        st.markdown(
            '<div class="insights-title">Top Products</div>'
            '<div class="insights-subtitle">Most active products by release note count</div>',
            unsafe_allow_html=True,
        )
        top_products_query = f"""
        SELECT product_name, COUNT(*) as count
        FROM `{table_name}`
        WHERE product_name IS NOT NULL
        GROUP BY product_name ORDER BY count DESC LIMIT 10
        """
        top_products_df = client.query(top_products_query).to_dataframe()

        fig3 = go.Figure(data=[go.Bar(
            x=top_products_df["count"],
            y=top_products_df["product_name"],
            orientation="h",
            marker=dict(
                color=top_products_df["count"],
                colorscale=[[0, "#E8F0FE"], [1, "#1A73E8"]],
                cornerradius=4,
                line=dict(width=0),
            ),
            hovertemplate="<b>%{y}</b><br>%{x:,} release notes<extra></extra>",
        )])
        fig3.update_layout(
            **PLOTLY_LAYOUT,
            yaxis=dict(autorange="reversed", tickfont=dict(size=11, color="#3C4043")),
            xaxis=dict(
                showgrid=True,
                gridcolor="rgba(232, 234, 237, 0.5)",
                tickfont=dict(size=11, color="#3C4043"),
            ),
            height=400,
        )
        st.plotly_chart(fig3, use_container_width=True)

    with col4:
        st.markdown(
            '<div class="insights-title">Recent Activity Heatmap</div>'
            '<div class="insights-subtitle">Daily release note activity (last 3 months)</div>',
            unsafe_allow_html=True,
        )
        heatmap_query = f"""
        SELECT
            EXTRACT(DAYOFWEEK FROM published_at) as day_of_week,
            DATE_TRUNC(published_at, WEEK) as week,
            COUNT(*) as count
        FROM `{table_name}`
        WHERE published_at BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 3 MONTH) AND CURRENT_DATE()
        GROUP BY day_of_week, week
        ORDER BY week, day_of_week
        """
        heatmap_df = client.query(heatmap_query).to_dataframe()

        if not heatmap_df.empty:
            pivot_df = heatmap_df.pivot_table(
                index="day_of_week", columns="week", values="count", fill_value=0
            )
            day_labels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
            week_labels = [f"W{pd.Timestamp(w).isocalendar()[1]}" for w in pivot_df.columns]

            fig4 = go.Figure(data=go.Heatmap(
                z=pivot_df.values,
                x=week_labels,
                y=[day_labels[int(d) - 1] for d in pivot_df.index],
                colorscale=[[0, "#F8FAFE"], [0.5, "#A8C7FA"], [1, "#1A73E8"]],
                showscale=False,
                hovertemplate="<b>%{x} · %{y}</b><br>%{z} notes<extra></extra>",
                xgap=3,
                ygap=3,
            ))
            fig4.update_layout(
                **PLOTLY_LAYOUT,
                xaxis=dict(showgrid=False, tickfont=dict(size=10, color="#3C4043")),
                yaxis=dict(tickfont=dict(size=11, color="#3C4043"), autorange="reversed"),
                height=400,
            )
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("Not enough data for the heatmap.")

# --------------- Footer ---------------
st.markdown(
    """
    <div class="app-footer">
        Release Notes Navigator &nbsp;·&nbsp; Built by <a href="https://www.linkedin.com/in/bricefotzo/">Brice Fotzo</a>
        &nbsp;·&nbsp; Powered by BigQuery & Streamlit
    </div>
    """,
    unsafe_allow_html=True,
)
