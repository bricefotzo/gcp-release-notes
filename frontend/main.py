"""Release Notes Navigator – Streamlit frontend."""
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from src.api.client import (
    BACKEND_URL,
    fetch_breaking_changes,
    fetch_new_count,
    fetch_release_notes,
    load_filter_options,
)
from src.components.ai_tab import render_ai_tab
from src.components.banners import render_breaking_changes_banner
from src.components.insights_tab import render_insights_tab
from src.components.notes_tab import render_notes_tab
from src.components.search_bar import render_search_bar
from src.components.sidebar import render_sidebar
from src.state import session

load_dotenv()

# ---- Page config (must be the first Streamlit call) ----
st.set_page_config(
    page_title="Release Notes Navigator",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- CSS ----
_CSS = Path(__file__).parent / "assets" / "style.css"
if _CSS.exists():
    st.markdown(f"<style>{_CSS.read_text()}</style>", unsafe_allow_html=True)

# ---- Copy-button JS listener ----
# st.markdown strips onclick handlers, so we inject a single delegated
# listener via components.html that accesses the parent document.
components.html(
    """
    <script>
    (function () {
        function copyViaTextarea(text, doc) {
            var ta = doc.createElement('textarea');
            ta.value = text;
            ta.setAttribute('readonly', '');
            ta.style.cssText = 'position:absolute;left:-9999px;top:-9999px;opacity:0';
            doc.body.appendChild(ta);
            ta.focus();
            ta.select();
            var ok = false;
            try { ok = doc.execCommand('copy'); } catch (e) {}
            doc.body.removeChild(ta);
            return ok;
        }

        function feedback(btn) {
            btn.classList.add('copied');
            btn.setAttribute('title', 'Copied!');
            setTimeout(function () {
                btn.classList.remove('copied');
                btn.setAttribute('title', 'Copy note');
            }, 2000);
        }

        function setup() {
            try {
                var doc = window.parent.document;
                if (doc.__copyBtnReady) return;
                doc.__copyBtnReady = true;
                doc.addEventListener('click', function (e) {
                    var btn = e.target.closest && e.target.closest('.note-copy-btn');
                    if (!btn) return;
                    var text = decodeURIComponent(btn.getAttribute('data-text') || '');
                    if (!text) return;
                    if (copyViaTextarea(text, doc)) {
                        feedback(btn);
                    }
                });
            } catch (e) { console.warn('copy-btn setup failed', e); }
        }

        if (document.readyState === 'complete') { setup(); }
        else { window.addEventListener('load', setup); }
        setTimeout(setup, 400);
    })();
    </script>
    """,
    height=0,
)

# ---- Analytics ----
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

# ---- Backend health check ----
try:
    requests.get(f"{BACKEND_URL}/health", timeout=10).raise_for_status()
except Exception as e:
    st.error(f"Cannot reach backend at {BACKEND_URL}: {e}")
    st.stop()

# ---- Filter options ----
filter_options = load_filter_options()
release_note_types = filter_options.get("types", [])
product_names = filter_options.get("products", [])
min_date = date.fromisoformat(filter_options["min_date"])

# ---- Session state + URL params (before any widget) ----
session.init(product_names, release_note_types)
session.load_url_params(product_names, release_note_types)

# ---- Sidebar ----
filters = render_sidebar(product_names, release_note_types, min_date)
if filters.applied:
    session.reset_page()

# ---- Hero header ----
_GCP_ICON = (
    '<svg viewBox="0 0 24 24">'
    '<path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#fff"/>'
    '<path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="rgba(255,255,255,0.85)"/>'
    '<path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="rgba(255,255,255,0.7)"/>'
    '<path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="rgba(255,255,255,0.55)"/>'
    '</svg>'
)
st.markdown(
    f"""
    <div class="hero-header">
        <div class="hero-platform-badge">
            {_GCP_ICON}
            <span>{filters.platform}</span>
        </div>
        <p class="hero-title">Release Notes Navigator</p>
        <p class="hero-subtitle">
            Explore and analyze release notes across cloud platforms — search, filter, and gain insights from the latest changes.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---- Search bar ----
_active_sidebar_filters = sum([bool(filters.products), bool(filters.types)])
filters.search_text = render_search_bar(
    active_filter_count=_active_sidebar_filters,
    product_names=product_names,
    release_note_types=release_note_types,
    min_date=min_date,
)

# ---- Fetch release notes ----
current_page = st.session_state[session.PAGE]
raw = fetch_release_notes(
    tuple(filters.types),
    tuple(filters.products),
    str(filters.start_date),
    str(filters.end_date),
    filters.search_text,
    current_page,
    st.session_state[session.ITEMS_PER_PAGE],
)
results = pd.DataFrame(raw["data"])
if not results.empty and "published_at" in results.columns:
    results["published_at"] = pd.to_datetime(results["published_at"])
total_count = raw["total"]
items_per_page = st.session_state[session.ITEMS_PER_PAGE]
total_pages = max(1, (total_count + items_per_page - 1) // items_per_page)

# ---- Breaking changes banner ----
watchlist = st.session_state[session.WATCHLIST]
bc_products_key = tuple(watchlist) if watchlist else tuple(filters.products)
bc_raw = fetch_breaking_changes(
    products_key=bc_products_key,
    start_date_str=str(filters.start_date),
    end_date_str=str(filters.end_date),
)
bc_df = pd.DataFrame(bc_raw["data"]) if bc_raw["data"] else pd.DataFrame()
render_breaking_changes_banner(
    bc_df, bc_raw["total"], filters.start_date, filters.end_date, watchlist, filters.products
)

# ---- Tabs ----
prev_lv = st.session_state[session.PREV_LAST_VISIT]
new_count = fetch_new_count(prev_lv, bc_products_key) if prev_lv else 0
notes_label = f"Release Notes  ·  {new_count} new ↑" if new_count else "Release Notes"
tab_notes, tab_insights, tab_ai = st.tabs([notes_label, "Insights & Analytics", "Ask AI"])

with tab_notes:
    render_notes_tab(filters, results, total_count, total_pages, current_page, min_date)

with tab_insights:
    render_insights_tab()

with tab_ai:
    render_ai_tab(filters, watchlist)

# ---- Footer ----
st.markdown(
    """
    <div class="app-footer">
        Release Notes Navigator &nbsp;·&nbsp; Built by <a href="https://www.linkedin.com/in/bricefotzo/">Brice Fotzo</a>
        &nbsp;·&nbsp; Powered by BigQuery & Streamlit
    </div>
    """,
    unsafe_allow_html=True,
)
