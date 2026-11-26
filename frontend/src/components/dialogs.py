"""Streamlit dialog components."""
from datetime import date, timedelta

import streamlit as st
import streamlit.components.v1 as components

from src.state import session


@st.dialog("Filters")
def filter_dialog(
    product_names: list[str],
    release_note_types: list[str],
    min_date: date,
) -> None:
    """Modal filter panel — mirrors the sidebar filters."""
    _default_start = max(min_date, date.today() - timedelta(days=90))
    _init_start = st.session_state.get(session.DATE_START) or _default_start
    _init_end = st.session_state.get(session.DATE_END) or date.today()

    # Use distinct keys (_dialog_*) to avoid duplicate-key errors with sidebar widgets
    selected_products = st.multiselect(
        "Products",
        options=product_names,
        default=st.session_state.get(session.PRODUCTS_SELECT, []),
        placeholder="All products",
        key="_dialog_products",
    )
    selected_types = st.multiselect(
        "Types",
        options=release_note_types,
        default=st.session_state.get(session.TYPES_SELECT, []),
        placeholder="All types",
        key="_dialog_types",
    )
    date_range = st.date_input(
        "Period",
        value=(_init_start, _init_end),
        min_value=min_date,
        max_value=date.today(),
        key="_dialog_date_range",
    )

    st.markdown("")
    col_clear, col_apply = st.columns([1, 2])
    with col_clear:
        if st.button("Clear all", use_container_width=True, key="_dialog_clear"):
            st.session_state[session.PRODUCTS_SELECT] = []
            st.session_state[session.TYPES_SELECT] = []
            st.session_state[session.DATE_START] = _default_start
            st.session_state[session.DATE_END] = date.today()
            session.reset_page()
            st.rerun()
    with col_apply:
        if st.button("Apply", use_container_width=True, type="primary", key="_dialog_apply"):
            st.session_state[session.PRODUCTS_SELECT] = selected_products
            st.session_state[session.TYPES_SELECT] = selected_types
            if isinstance(date_range, tuple) and len(date_range) >= 2:
                st.session_state[session.DATE_START] = date_range[0]
                st.session_state[session.DATE_END] = date_range[1]
            elif isinstance(date_range, tuple) and len(date_range) == 1:
                st.session_state[session.DATE_START] = date_range[0]
                st.session_state[session.DATE_END] = date_range[0]
            session.reset_page()
            st.rerun()


@st.dialog("Share this view")
def share_dialog() -> None:
    st.markdown("Copy this link to share your current filters with teammates.")
    components.html(
        """
        <div style="display:flex;gap:8px;align-items:center;margin-top:4px">
            <input id="share-url" type="text" readonly
                style="flex:1;padding:8px 12px;border:1.5px solid #E8EAED;border-radius:8px;
                       font-size:0.82rem;color:#202124;background:#F8FAFE;font-family:monospace;
                       outline:none;min-width:0">
            <button id="copy-btn"
                style="padding:8px 18px;background:#1A73E8;color:white;border:none;border-radius:8px;
                       cursor:pointer;font-weight:600;font-size:0.82rem;white-space:nowrap;flex-shrink:0"
                onclick="
                    navigator.clipboard.writeText(document.getElementById('share-url').value).then(function() {
                        var btn = document.getElementById('copy-btn');
                        btn.textContent = 'Copied!';
                        btn.style.background = '#34A853';
                        setTimeout(function() {
                            btn.textContent = 'Copy';
                            btn.style.background = '#1A73E8';
                        }, 2000);
                    });
                ">Copy</button>
        </div>
        <script>
            try {
                document.getElementById('share-url').value = window.parent.location.href;
            } catch(e) {
                document.getElementById('share-url').value = window.location.href;
            }
        </script>
        """,
        height=60,
    )
