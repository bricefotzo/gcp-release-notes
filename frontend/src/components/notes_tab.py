"""Release Notes tab rendering."""
from datetime import date
from urllib.parse import quote as urlquote

import pandas as pd
import streamlit as st

from src.api.client import _TAG_RE, fetch_export_notes, to_markdown_digest
from src.components.dialogs import share_dialog
from src.components.sidebar import FilterState
from src.state import session
from src.utils import format_description, get_badge_class, get_type_css_class

_CALENDAR_ICON = '<svg viewBox="0 0 24 24"><path d="M19 3h-1V1h-2v2H8V1H6v2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V8h14v11zM9 10H7v2h2v-2zm4 0h-2v2h2v-2zm4 0h-2v2h2v-2z"/></svg>'
_COPY_ICON = '<svg viewBox="0 0 24 24" width="13" height="13"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>'


def render_notes_tab(
    filters: FilterState,
    results: pd.DataFrame,
    total_count: int,
    total_pages: int,
    current_page: int,
    min_date: date,
) -> None:
    active_filters = sum([
        bool(filters.search_text),
        bool(filters.products),
        bool(filters.types),
        filters.start_date != min_date or filters.end_date != date.today(),
    ])
    filter_text = (
        f"given your <strong>{active_filters}</strong> active filter{'s' if active_filters != 1 else ''}"
        if active_filters else ""
    )

    sum_col, export_col = st.columns([5, 4])
    with sum_col:
        st.markdown(
            f"""
            <div class="results-summary">
                <span class="results-count">{total_count:,}</span> notes found on
                <span class="results-platform">{filters.platform}</span>
                {filter_text}· <span class="results-page">Page {current_page} of {total_pages}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if total_count > 0:
        export_df = fetch_export_notes(
            tuple(filters.types),
            tuple(filters.products),
            str(filters.start_date),
            str(filters.end_date),
            filters.search_text,
        )
        _digest = to_markdown_digest(export_df, filters.platform, filters.start_date, filters.end_date)
        _export_label = (
            f"up to 1,000 of {total_count:,}" if total_count > 1000 else f"all {total_count:,}"
        )
        with export_col:
            label_col, btn_col = st.columns([3, 1])
            with label_col:
                st.markdown(
                    f'<div class="export-label">Export {_export_label} notes</div>',
                    unsafe_allow_html=True,
                )
            with btn_col:
                if st.button("🔗 Share", use_container_width=True, key="share_btn"):
                    st.query_params.clear()
                    if filters.products:
                        st.query_params["p"] = filters.products
                    if filters.types:
                        st.query_params["t"] = filters.types
                    st.query_params["start"] = str(filters.start_date)
                    st.query_params["end"] = str(filters.end_date)
                    share_dialog()

    if not results.empty:
        for _, row in results.iterrows():
            _render_note_card(row)
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

    _render_pagination(current_page, total_pages, total_count)


def _render_note_card(row: pd.Series) -> None:
    type_class = get_type_css_class(row["release_note_type"])
    badge_class = get_badge_class(row["release_note_type"])
    pub_date = row["published_at"].strftime("%b %d, %Y")
    plain_desc = _TAG_RE.sub("", str(row.get("description", ""))).strip()
    copy_text = urlquote(
        f"{row['product_name']}\n"
        f"Type: {row['release_note_type']}\n"
        f"Date: {pub_date}\n\n"
        f"{plain_desc}"
    )
    st.markdown(
        f"""
        <div class="note-card {type_class}">
            <div class="note-card-header">
                <span class="note-product">{row['product_name']}</span>
                <div class="note-meta">
                    <span class="note-badge {badge_class}">{row['release_note_type']}</span>
                    <span class="note-date">
                        {_CALENDAR_ICON}
                        {pub_date}
                    </span>
                    <button class="note-copy-btn" title="Copy note" data-text="{copy_text}">
                        {_COPY_ICON}
                    </button>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.container():
        format_description(row["description"])
    st.markdown("<div style='height: 0.25rem'></div>", unsafe_allow_html=True)


def _render_pagination(current_page: int, total_pages: int, total_count: int) -> None:
    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
    pcol1, pcol2, pcol3, pcol4, pcol5 = st.columns([1, 1, 2, 1, 1])
    with pcol1:
        if current_page > 1:
            st.button("← Previous", on_click=session.prev_page, use_container_width=True)
    with pcol3:
        st.markdown(
            f"<div style='text-align:center;padding:0.5rem 0;font-size:0.85rem;color:#5F6368;font-weight:500;'>"
            f"Page {current_page} of {total_pages} &nbsp;·&nbsp; {total_count:,} results"
            f"</div>",
            unsafe_allow_html=True,
        )
    with pcol5:
        if current_page < total_pages:
            st.button("Next →", on_click=session.next_page, use_container_width=True)

    ipp_col1, ipp_col2, ipp_col3 = st.columns([3, 1, 3])
    with ipp_col2:
        st.session_state[session.ITEMS_PER_PAGE] = st.selectbox(
            "Per page",
            [5, 10, 15, 20, 50],
            index=[5, 10, 15, 20, 50].index(st.session_state[session.ITEMS_PER_PAGE]),
            key="items_per_page_select",
        )
