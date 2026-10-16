"""Airbnb-style pill search bar with inline collapsible filter panel."""
from datetime import date, timedelta

import streamlit as st
import streamlit.components.v1 as components

from src.state import session

# Tags the stHorizontalBlock that follows .search-anchor with search-bar-pill,
# and the stVerticalBlock that follows .filter-panel-anchor with filter-panel.
_TAG_SCRIPT = """
<script>
(function () {
    function tagPill() {
        try {
            var doc = window.parent.document;
            var anchor = doc.querySelector('.search-anchor');
            if (!anchor) { setTimeout(tagPill, 200); return; }
            var el = anchor;
            while (el && !el.nextElementSibling) el = el.parentElement;
            while (el && el.parentElement) {
                var sib = el.nextElementSibling;
                while (sib) {
                    var hb = sib.matches('[data-testid="stHorizontalBlock"]')
                        ? sib : sib.querySelector('[data-testid="stHorizontalBlock"]');
                    if (hb) { hb.classList.add('search-bar-pill'); break; }
                    sib = sib.nextElementSibling;
                }
                el = el.parentElement;
            }
        } catch(e) {}
    }

    function tagPanel() {
        try {
            var doc = window.parent.document;
            var anchor = doc.querySelector('.filter-panel-anchor');
            if (!anchor) return;
            var el = anchor;
            while (el && !el.nextElementSibling) el = el.parentElement;
            if (!el) return;
            var sib = el.nextElementSibling;
            while (sib) {
                var vb = sib.matches('[data-testid="stVerticalBlock"]')
                    ? sib : sib.querySelector('[data-testid="stVerticalBlock"]');
                if (vb) { vb.classList.add('filter-panel'); return; }
                sib = sib.nextElementSibling;
            }
        } catch(e) {}
    }

    tagPill();
    setTimeout(tagPanel, 400);
})();
</script>
"""


def render_search_bar(
    active_filter_count: int = 0,
    product_names: list[str] | None = None,
    release_note_types: list[str] | None = None,
    min_date: date | None = None,
) -> str:
    """Render an Airbnb-style pill search bar. Returns current search text."""
    st.markdown('<div class="search-anchor"></div>', unsafe_allow_html=True)

    col_input, col_btn = st.columns([8, 1])

    with col_input:
        st.text_input(
            "Search",
            placeholder="Search products, features, fixes, breaking changes…",
            label_visibility="collapsed",
            key=session.SEARCH_TEXT,
            on_change=session.reset_page,
        )

    current = st.session_state.get(session.SEARCH_TEXT, "")
    filters_open = st.session_state.get(session.FILTERS_OPEN, False)

    with col_btn:
        if current:
            if st.button(
                "Clear",
                icon=":material/close:",
                use_container_width=True,
                key="search_clear_btn",
            ):
                st.session_state[session.SEARCH_TEXT] = ""
                session.reset_page()
                st.rerun()
        else:
            badge = f" · {active_filter_count}" if active_filter_count else ""
            is_active = bool(active_filter_count) or filters_open
            if st.button(
                f"Filters{badge}",
                icon=":material/tune:",
                use_container_width=True,
                key="filter_indicator_btn",
                type="primary" if is_active else "secondary",
            ):
                st.session_state[session.FILTERS_OPEN] = not filters_open
                st.rerun()

    components.html(_TAG_SCRIPT, height=0)

    if st.session_state.get(session.FILTERS_OPEN, False):
        _render_filter_panel(
            product_names or [],
            release_note_types or [],
            min_date or date.today(),
        )

    return current


def _render_filter_panel(
    product_names: list[str],
    release_note_types: list[str],
    min_date: date,
) -> None:
    st.markdown('<div class="filter-panel-anchor"></div>', unsafe_allow_html=True)

    with st.container():
        col1, col2, col3 = st.columns(3)

        with col1:
            selected_products = st.multiselect(
                "Products",
                options=product_names,
                default=st.session_state.get(session.PRODUCTS_SELECT, []),
                placeholder="All products",
                key="_panel_products",
            )

        with col2:
            selected_types = st.multiselect(
                "Types",
                options=release_note_types,
                default=st.session_state.get(session.TYPES_SELECT, []),
                placeholder="All types",
                key="_panel_types",
            )

        with col3:
            _default_start = max(min_date, date.today() - timedelta(days=90))
            _init_start = st.session_state.get(session.DATE_START) or _default_start
            _init_end = st.session_state.get(session.DATE_END) or date.today()
            date_range = st.date_input(
                "Period",
                value=(_init_start, _init_end),
                min_value=min_date,
                max_value=date.today(),
                key="_panel_date_range",
            )

        _, col_clear, col_apply = st.columns([4, 1, 1])

        with col_clear:
            if st.button("Clear all", use_container_width=True, key="_panel_clear"):
                st.session_state[session.PRODUCTS_SELECT] = []
                st.session_state[session.TYPES_SELECT] = []
                st.session_state[session.DATE_START] = _default_start
                st.session_state[session.DATE_END] = date.today()
                st.session_state[session.FILTERS_OPEN] = False
                session.reset_page()
                st.rerun()

        with col_apply:
            if st.button("Apply", use_container_width=True, type="primary", key="_panel_apply"):
                st.session_state[session.PRODUCTS_SELECT] = selected_products
                st.session_state[session.TYPES_SELECT] = selected_types
                if isinstance(date_range, tuple) and len(date_range) >= 2:
                    st.session_state[session.DATE_START] = date_range[0]
                    st.session_state[session.DATE_END] = date_range[1]
                elif isinstance(date_range, tuple) and len(date_range) == 1:
                    st.session_state[session.DATE_START] = date_range[0]
                    st.session_state[session.DATE_END] = date_range[0]
                st.session_state[session.FILTERS_OPEN] = False
                session.reset_page()
                st.rerun()
