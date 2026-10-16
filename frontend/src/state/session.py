"""Session state key constants and lifecycle functions."""
from datetime import date

import streamlit as st

from src.persistence.storage import load_last_visit, load_watchlist, save_last_visit

# ---- Key constants ----
WATCHLIST = "watchlist"
PREV_LAST_VISIT = "_prev_last_visit"
WATCHLIST_APPLIED = "_watchlist_applied"
PRODUCTS_SELECT = "_products_select"
TYPES_SELECT = "_types_select"
URL_LOADED = "_url_loaded"
PAGE = "page"
ITEMS_PER_PAGE = "items_per_page"
AI_Q = "_ai_q"
APPLY_STACK = "_apply_stack"
SEARCH_TEXT = "_search_text"
DATE_START = "_date_start"
DATE_END = "_date_end"
FILTERS_OPEN = "_filters_open"


def init(product_names: list[str], release_note_types: list[str]) -> None:
    """Initialise all session state keys. Call before any widget renders."""
    if WATCHLIST not in st.session_state:
        st.session_state[WATCHLIST] = load_watchlist()

    if PREV_LAST_VISIT not in st.session_state:
        st.session_state[PREV_LAST_VISIT] = load_last_visit()
        save_last_visit(str(date.today()))

    if WATCHLIST_APPLIED not in st.session_state:
        st.session_state[PRODUCTS_SELECT] = list(st.session_state[WATCHLIST])
        st.session_state[WATCHLIST_APPLIED] = True

    if st.session_state.pop(APPLY_STACK, False):
        st.session_state[PRODUCTS_SELECT] = list(st.session_state[WATCHLIST])

    st.session_state.setdefault(PRODUCTS_SELECT, [])
    st.session_state.setdefault(TYPES_SELECT, [])
    st.session_state.setdefault(PAGE, 1)
    st.session_state.setdefault(ITEMS_PER_PAGE, 10)
    st.session_state.setdefault(AI_Q, "")
    st.session_state.setdefault(SEARCH_TEXT, "")
    st.session_state.setdefault(DATE_START, None)
    st.session_state.setdefault(DATE_END, None)
    st.session_state.setdefault(FILTERS_OPEN, False)


def load_url_params(product_names: list[str], release_note_types: list[str]) -> None:
    """Apply URL query params to session state once per session."""
    if URL_LOADED in st.session_state:
        return
    qp = st.query_params
    try:
        url_products = qp.get_all("p")
        url_types = qp.get_all("t")
    except AttributeError:
        url_products = [qp["p"]] if "p" in qp else []
        url_types = [qp["t"]] if "t" in qp else []
    valid_products = [p for p in url_products if p in product_names]
    valid_types = [t for t in url_types if t in release_note_types]
    if valid_products:
        st.session_state[PRODUCTS_SELECT] = valid_products
    if valid_types:
        st.session_state[TYPES_SELECT] = valid_types
    st.session_state[URL_LOADED] = True


def next_page() -> None:
    st.session_state[PAGE] += 1


def prev_page() -> None:
    st.session_state[PAGE] = max(1, st.session_state[PAGE] - 1)


def reset_page() -> None:
    st.session_state[PAGE] = 1
