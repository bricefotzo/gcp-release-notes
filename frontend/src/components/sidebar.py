"""Sidebar rendering — returns a FilterState describing the user's current selections."""
from dataclasses import dataclass
from datetime import date, timedelta

import streamlit as st

from src.api.client import fetch_new_count
from src.persistence.storage import save_last_visit, save_watchlist
from src.state import session

_BRAND_HTML = """
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
"""


@dataclass
class FilterState:
    platform: str
    products: list[str]
    types: list[str]
    start_date: date
    end_date: date
    search_text: str
    applied: bool


def render_sidebar(
    product_names: list[str],
    release_note_types: list[str],
    min_date: date,
) -> FilterState:
    with st.sidebar:
        st.markdown(_BRAND_HTML, unsafe_allow_html=True)

        selected_products = st.multiselect(
            "Product",
            options=product_names,
            placeholder="All products",
            key=session.PRODUCTS_SELECT,
        )
        selected_types = st.multiselect(
            "Type",
            options=release_note_types,
            placeholder="All types",
            key=session.TYPES_SELECT,
        )

        _default_start = max(min_date, date.today() - timedelta(days=90))
        _init_start = st.session_state.get(session.DATE_START) or _default_start
        _init_end = st.session_state.get(session.DATE_END) or date.today()
        date_range = st.date_input(
            "Period",
            value=(_init_start, _init_end),
            min_value=min_date,
            max_value=date.today(),
            label_visibility="collapsed",
        )

        st.markdown("")
        applied = st.button("Apply Filters", use_container_width=True)

        st.markdown("---")
        _render_watchlist(product_names)

        st.markdown("---")
        _render_last_visit()

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

    start_date, end_date = _date_range_bounds(date_range, min_date, date.today())
    st.session_state[session.DATE_START] = start_date
    st.session_state[session.DATE_END] = end_date
    return FilterState(
        platform="Google Cloud",
        products=selected_products,
        types=selected_types,
        start_date=start_date,
        end_date=end_date,
        search_text="",
        applied=applied,
    )


def _render_watchlist(product_names: list[str]) -> None:
    watchlist = st.session_state[session.WATCHLIST]
    wl_count = len(watchlist)

    if wl_count:
        tags_html = "".join(f'<span class="wl-tag">{p}</span>' for p in watchlist)
        st.markdown(
            f'<div class="wl-header">'
            f'<span class="wl-header-title">My Stack</span>'
            f'<span class="wl-badge">{wl_count}</span>'
            f'</div>'
            f'<div class="wl-tags">{tags_html}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="wl-header">'
            '<span class="wl-header-title">My Stack</span>'
            '<span class="wl-badge-empty">not set</span>'
            '</div>',
            unsafe_allow_html=True,
        )

    watchlist_edit = st.multiselect(
        "Watched products",
        options=product_names,
        default=watchlist,
        placeholder="Pick your stack...",
        label_visibility="collapsed",
        key="_watchlist_select",
    )

    wl_col1, wl_col2 = st.columns(2)
    with wl_col1:
        if st.button("Save Stack", use_container_width=True, key="wl_save"):
            st.session_state[session.WATCHLIST] = watchlist_edit
            save_watchlist(watchlist_edit)
            st.rerun()
    with wl_col2:
        if st.button("Clear", use_container_width=True, key="wl_clear"):
            st.session_state[session.WATCHLIST] = []
            save_watchlist([])
            st.rerun()

    if watchlist:
        if st.button("Apply as filter", use_container_width=True, key="wl_apply"):
            st.session_state[session.APPLY_STACK] = True
            st.rerun()


def _render_last_visit() -> None:
    _prev = st.session_state.get(session.PREV_LAST_VISIT)
    if not _prev:
        return
    try:
        _prev_fmt = date.fromisoformat(_prev).strftime("%b %d, %Y")
    except Exception:
        _prev_fmt = _prev

    _lv_products = tuple(st.session_state[session.WATCHLIST] or [])
    _lv_new = fetch_new_count(_prev, _lv_products)

    if _lv_new > 0:
        _scope_txt = "for your stack" if _lv_products else "across all products"
        st.markdown(
            f'<div class="lv-bar lv-bar-new">'
            f'<span class="lv-count-badge">{_lv_new}</span>'
            f'<span class="lv-text">new notes {_scope_txt}</span>'
            f'<span class="lv-since">since {_prev_fmt}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button("Mark as seen", use_container_width=True, key="lv_mark_seen"):
            save_last_visit(str(date.today()))
            st.session_state[session.PREV_LAST_VISIT] = str(date.today())
            st.rerun()
    else:
        st.markdown(
            f'<div class="lv-bar lv-bar-current">'
            f'<span class="lv-text">Up to date</span>'
            f'<span class="lv-since">last visit {_prev_fmt}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )


def _date_range_bounds(dr, default_start: date, default_end: date) -> tuple[date, date]:
    if isinstance(dr, tuple) and len(dr) >= 2:
        return dr[0], dr[1]
    if isinstance(dr, tuple) and len(dr) == 1:
        return dr[0], dr[0]
    return default_start, default_end
