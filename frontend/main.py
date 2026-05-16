"""Release Notes Navigator – Streamlit frontend."""

import json
import os
import re
from datetime import date
from pathlib import Path
from urllib.parse import quote as urlquote

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from src.utils import format_description, get_badge_class, get_type_css_class

load_dotenv()

BACKEND_URL = os.environ.get("BACKEND_URL", "http://back:8000")
WATCHLIST_PATH = Path(__file__).parent / "watchlist.json"


def load_watchlist() -> list[str]:
    try:
        if WATCHLIST_PATH.exists():
            return json.loads(WATCHLIST_PATH.read_text())
    except Exception:
        pass
    return []


def save_watchlist(products: list[str]) -> None:
    try:
        WATCHLIST_PATH.write_text(json.dumps(products))
    except Exception:
        pass


LAST_VISIT_PATH = Path(__file__).parent / "last_visit.json"


def load_last_visit() -> str | None:
    """Return the ISO date string of the previous visit, or None on first ever visit."""
    try:
        if LAST_VISIT_PATH.exists():
            return json.loads(LAST_VISIT_PATH.read_text()).get("date")
    except Exception:
        pass
    return None


def save_last_visit(iso_date: str) -> None:
    try:
        LAST_VISIT_PATH.write_text(json.dumps({"date": iso_date}))
    except Exception:
        pass

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

# --------------- Global copy-button listener ---------------
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

# --------------- Backend Connection Check ---------------
try:
    requests.get(f"{BACKEND_URL}/health", timeout=10).raise_for_status()
except Exception as e:
    st.error(f"Cannot reach backend at {BACKEND_URL}: {e}")
    st.stop()

# --------------- API Helpers ---------------


@st.cache_data(ttl=3600, show_spinner="Loading filters...")
def load_filter_options() -> dict:
    resp = requests.get(f"{BACKEND_URL}/api/filter-options", timeout=30)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=300)
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
    # requests repeats the key for list params
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


@st.cache_data(ttl=3600)
def fetch_time_series() -> list:
    return requests.get(f"{BACKEND_URL}/api/insights/time-series", timeout=30).json()


@st.cache_data(ttl=3600)
def fetch_type_distribution() -> list:
    return requests.get(f"{BACKEND_URL}/api/insights/type-distribution", timeout=30).json()


@st.cache_data(ttl=3600)
def fetch_top_products() -> list:
    return requests.get(f"{BACKEND_URL}/api/insights/top-products", timeout=30).json()


@st.cache_data(ttl=3600)
def fetch_heatmap() -> list:
    return requests.get(f"{BACKEND_URL}/api/insights/heatmap", timeout=30).json()


@st.cache_data(ttl=300)
def fetch_new_count(since_date: str, products_key: tuple) -> int:
    """Count notes published strictly after since_date (day+1 onwards)."""
    from datetime import timedelta
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


@st.cache_data(ttl=1800)
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


@st.cache_data(ttl=300)
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


_TAG_RE = re.compile(r"<[^>]+>")


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


# --------------- Watchlist + Session State Init ---------------
if "watchlist" not in st.session_state:
    st.session_state.watchlist = load_watchlist()

# Last-visit tracking: capture previous date on first run, then stamp today
if "_prev_last_visit" not in st.session_state:
    st.session_state["_prev_last_visit"] = load_last_visit()
    save_last_visit(str(date.today()))

# Auto-apply watchlist on first load of the session
if "_watchlist_applied" not in st.session_state:
    st.session_state["_products_select"] = list(st.session_state.watchlist)
    st.session_state["_watchlist_applied"] = True

# "Apply my stack as filter" manual trigger — must run before the multiselect renders
if st.session_state.pop("_apply_stack", False):
    st.session_state["_products_select"] = list(st.session_state.watchlist)

if "_products_select" not in st.session_state:
    st.session_state["_products_select"] = []
if "_types_select" not in st.session_state:
    st.session_state["_types_select"] = []

# --------------- Load Filter Options ---------------
filter_options = load_filter_options()
release_note_types = filter_options.get("types", ["Feature", "Issue", "Announcement"])
product_names = filter_options.get("products", ["Compute Engine", "BigQuery", "Cloud Storage"])
min_date = date.fromisoformat(filter_options["min_date"])
max_date = date.fromisoformat(filter_options["max_date"])

# --------------- URL Param Loading (shareable links) ---------------
if "_url_loaded" not in st.session_state:
    _qp = st.query_params
    try:
        _url_products = _qp.get_all("p")
        _url_types = _qp.get_all("t")
    except AttributeError:
        _url_products = [_qp["p"]] if "p" in _qp else []
        _url_types = [_qp["t"]] if "t" in _qp else []
    _valid_products = [p for p in _url_products if p in product_names]
    _valid_types = [t for t in _url_types if t in release_note_types]
    if _valid_products:
        st.session_state["_products_select"] = _valid_products
    if _valid_types:
        st.session_state["_types_select"] = _valid_types
    st.session_state["_url_loaded"] = True

# ╔══════════════════════════════════════════════════════════════╗
# ║                        SIDEBAR                              ║
# ╚══════════════════════════════════════════════════════════════╝
with st.sidebar:
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

    # st.markdown("### Platform")
    # selected_platform = st.selectbox(
    #     "Platform",
    #     options=["Google Cloud"],
    #     index=0,
    #     label_visibility="collapsed",
    # )
    selected_platform = "Google Cloud"

    # st.markdown("### Search")
    # search_text = st.text_input(
    #     "Keyword",
    #     "",
    #     placeholder="e.g. Kubernetes, IAM, BigQuery...",
    #     label_visibility="collapsed",
    # )
    search_text = ""

    st.markdown("### Filters")
    selected_products = st.multiselect(
        "Product",
        options=product_names,
        placeholder="All products",
        key="_products_select",
    )
    selected_types = st.multiselect(
        "Type",
        options=release_note_types,
        placeholder="All types",
        key="_types_select",
    )

    st.markdown("### Date Range")
    date_range = st.date_input(
        "Period",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        label_visibility="collapsed",
    )

    st.markdown("")
    apply_filters = st.button("Apply Filters", use_container_width=True)

    st.markdown("---")

    # ---- My Stack / Watchlist ----
    watchlist = st.session_state.watchlist
    wl_count = len(watchlist)

    if wl_count:
        tags_html = "".join(
            f'<span class="wl-tag">{p}</span>' for p in watchlist
        )
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
            st.session_state.watchlist = watchlist_edit
            save_watchlist(watchlist_edit)
            st.rerun()
    with wl_col2:
        if st.button("Clear", use_container_width=True, key="wl_clear"):
            st.session_state.watchlist = []
            save_watchlist([])
            st.rerun()

    if watchlist:
        if st.button("Apply as filter", use_container_width=True, key="wl_apply"):
            st.session_state["_apply_stack"] = True
            st.rerun()

    st.markdown("---")

    # ---- Last Visit ----
    _prev = st.session_state["_prev_last_visit"]
    if _prev:
        try:
            _prev_fmt = date.fromisoformat(_prev).strftime("%b %d, %Y")
        except Exception:
            _prev_fmt = _prev

        _lv_products = tuple(st.session_state.watchlist or [])
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
                st.session_state["_prev_last_visit"] = str(date.today())
                st.rerun()
        else:
            st.markdown(
                f'<div class="lv-bar lv-bar-current">'
                f'<span class="lv-text">Up to date</span>'
                f'<span class="lv-since">last visit {_prev_fmt}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

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

_PLATFORM_ICONS = {
    "Google Cloud": '<svg viewBox="0 0 24 24"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#fff"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="rgba(255,255,255,0.85)"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="rgba(255,255,255,0.7)"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="rgba(255,255,255,0.55)"/></svg>',
}

st.markdown(
    f"""
    <div class="hero-header">
        <div class="hero-platform-badge">
            {_PLATFORM_ICONS.get(selected_platform, "")}
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


def _date_range_bounds(dr, default_start: date, default_end: date) -> tuple[date, date]:
    if isinstance(dr, tuple) and len(dr) >= 2:
        return dr[0], dr[1]
    if isinstance(dr, tuple) and len(dr) == 1:
        return dr[0], dr[0]
    return default_start, default_end


start_date, end_date = _date_range_bounds(date_range, min_date, max_date)

# --------------- Fetch Release Notes ---------------
raw = fetch_release_notes(
    tuple(selected_types),
    tuple(selected_products),
    str(start_date),
    str(end_date),
    search_text,
    current_page,
    st.session_state.items_per_page,
)
results = pd.DataFrame(raw["data"])
if not results.empty and "published_at" in results.columns:
    results["published_at"] = pd.to_datetime(results["published_at"])
total_count = raw["total"]
total_pages = max(1, (total_count + st.session_state.items_per_page - 1) // st.session_state.items_per_page)

active_filters = sum([
    bool(search_text),
    bool(selected_products),
    bool(selected_types),
    start_date != min_date or end_date != max_date,
])

# --------------- Breaking Changes Banner ---------------
# Banner scope: watchlist takes priority, then product filter, then global
_active_watchlist = st.session_state.watchlist
bc_products_key = tuple(_active_watchlist) if _active_watchlist else tuple(selected_products)
bc_raw = fetch_breaking_changes(
    products_key=bc_products_key,
    start_date_str=str(start_date),
    end_date_str=str(end_date),
)
bc_df = pd.DataFrame(bc_raw["data"]) if bc_raw["data"] else pd.DataFrame()
bc_total = bc_raw["total"]

if bc_total > 0 and not bc_df.empty:
    bc_df["published_at"] = pd.to_datetime(bc_df["published_at"])

    breaking = bc_df[bc_df["release_note_type"].str.upper() == "BREAKING_CHANGE"]
    deprecations = bc_df[bc_df["release_note_type"].str.upper() == "DEPRECATION"]

    summary_parts = []
    if len(breaking):
        summary_parts.append(f"<strong>{len(breaking)}</strong> breaking change{'s' if len(breaking) != 1 else ''}")
    if len(deprecations):
        summary_parts.append(f"<strong>{len(deprecations)}</strong> deprecation{'s' if len(deprecations) != 1 else ''}")
    summary_text = " and ".join(summary_parts)

    unique_products = sorted(bc_df["product_name"].dropna().unique())
    MAX_TAGS = 12
    tags_html = "".join(
        f'<span class="bc-product-tag">{p}</span>' for p in unique_products[:MAX_TAGS]
    )
    if len(unique_products) > MAX_TAGS:
        tags_html += f'<span class="bc-product-tag bc-product-tag-more">+{len(unique_products) - MAX_TAGS} more</span>'

    date_label = f"{start_date.strftime('%b %d, %Y')} – {end_date.strftime('%b %d, %Y')}"
    if _active_watchlist:
        scope_label = "for <strong>your stack</strong>"
    elif selected_products:
        scope_label = "for your selection"
    else:
        scope_label = "across all products"

    st.markdown(
        f"""
        <div class="bc-banner">
            <div class="bc-banner-header">
                <span class="bc-banner-icon">⚠</span>
                <span class="bc-banner-count">{bc_total}</span>
                <span class="bc-banner-title">Breaking Changes &amp; Deprecations — {date_label}</span>
            </div>
            <div class="bc-banner-subtitle">
                {summary_text} {scope_label} — review before deploying.
            </div>
            <div class="bc-tags">{tags_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander(f"View all {bc_total} notes", expanded=False):
        for _, row in bc_df.iterrows():
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
            format_description(row["description"])
            st.markdown("<div style='height:0.25rem'></div>", unsafe_allow_html=True)

# --------------- Share Dialog ---------------
@st.dialog("Share this view")
def share_dialog():
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

# --------------- Tabs ---------------
_prev_lv = st.session_state["_prev_last_visit"]
_tab_new_count = fetch_new_count(_prev_lv, bc_products_key) if _prev_lv else 0
_notes_tab_label = f"Release Notes  ·  {_tab_new_count} new ↑" if _tab_new_count else "Release Notes"
tab_notes, tab_insights, tab_ai = st.tabs([_notes_tab_label, "Insights & Analytics", "Ask AI"])

# ╔══════════════════════════════════════════════════════════════╗
# ║                     NOTES TAB                                ║
# ╚══════════════════════════════════════════════════════════════╝
with tab_notes:
    filter_text = (
        f"given your <strong>{active_filters}</strong> active filter{'s' if active_filters != 1 else ''}"
        if active_filters
        else ""
    )

    # Results summary + export toolbar
    sum_col, export_col = st.columns([5, 4])
    with sum_col:
        st.markdown(
            f"""
            <div class="results-summary">
                <span class="results-count">{total_count:,}</span> notes found on
                <span class="results-platform">{selected_platform}</span>
                {filter_text}· <span class="results-page">Page {current_page} of {total_pages}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if total_count > 0:
        export_df = fetch_export_notes(
            tuple(selected_types),
            tuple(selected_products),
            str(start_date),
            str(end_date),
            search_text,
        )
        _file_stem = f"gcp-rn-{start_date}-{end_date}"
        _digest = to_markdown_digest(export_df, selected_platform, start_date, end_date)
        _export_label = (
            f"up to 1,000 of {total_count:,}"
            if total_count > 1000
            else f"all {total_count:,}"
        )

        with export_col:
            st.markdown(
                f'<div class="export-label">Export {_export_label} notes</div>',
                unsafe_allow_html=True,
            )
            fmt_col, dl_col, share_col = st.columns([2, 1.4, 1.2])
            with fmt_col:
                st.empty()  # needed to align the button with the label
            with dl_col:
                st.empty()  # needed to align the button with the label
            with share_col:
                if st.button("🔗 Share", use_container_width=True, key="share_btn"):
                    st.query_params.clear()
                    if selected_products:
                        st.query_params["p"] = selected_products
                    if selected_types:
                        st.query_params["t"] = selected_types
                    st.query_params["start"] = str(start_date)
                    st.query_params["end"] = str(end_date)
                    share_dialog()

    if not results.empty:
        for _, row in results.iterrows():
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
                                <svg viewBox="0 0 24 24"><path d="M19 3h-1V1h-2v2H8V1H6v2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V8h14v11zM9 10H7v2h2v-2zm4 0h-2v2h2v-2zm4 0h-2v2h2v-2z"/></svg>
                                {pub_date}
                            </span>
                            <button class="note-copy-btn" title="Copy note" data-text="{copy_text}">
                                <svg viewBox="0 0 24 24" width="13" height="13"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>
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
    with pcol3:
        st.markdown(
            f"<div style='text-align:center;padding:0.5rem 0;font-size:0.85rem;color:#5F6368;font-weight:500;'>"
            f"Page {current_page} of {total_pages} &nbsp;·&nbsp; {total_count:,} results"
            f"</div>",
            unsafe_allow_html=True,
        )
    with pcol5:
        if current_page < total_pages:
            st.button("Next →", on_click=next_page, use_container_width=True)

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
        time_df = pd.DataFrame(fetch_time_series())
        fig1 = go.Figure()
        if not time_df.empty:
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
            xaxis=dict(showgrid=False, tickformat="%b %Y", linecolor="#E8EAED", tickfont=dict(size=11, color="#3C4043")),
            yaxis=dict(showgrid=True, gridcolor="rgba(232, 234, 237, 0.5)", gridwidth=1, tickfont=dict(size=11, color="#3C4043")),
            height=350,
        )
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        st.markdown(
            '<div class="insights-title">Note Type Distribution</div>'
            '<div class="insights-subtitle">Breakdown by release note category</div>',
            unsafe_allow_html=True,
        )
        types_df = pd.DataFrame(fetch_type_distribution())
        fig2 = go.Figure()
        if not types_df.empty:
            fig2.add_trace(go.Pie(
                labels=types_df["release_note_type"],
                values=types_df["count"],
                hole=0.55,
                marker=dict(colors=CHART_COLORS[:len(types_df)], line=dict(color="white", width=2.5)),
                textinfo="label+percent",
                textfont=dict(size=11),
                hovertemplate="<b>%{label}</b><br>%{value:,} notes (%{percent})<extra></extra>",
            ))
        fig2.update_layout(**PLOTLY_LAYOUT, showlegend=False, height=350)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("<div style='height: 1rem'></div>", unsafe_allow_html=True)
    col3, col4 = st.columns(2)

    with col3:
        st.markdown(
            '<div class="insights-title">Top Products</div>'
            '<div class="insights-subtitle">Most active products by release note count</div>',
            unsafe_allow_html=True,
        )
        top_df = pd.DataFrame(fetch_top_products())
        fig3 = go.Figure()
        if not top_df.empty:
            fig3.add_trace(go.Bar(
                x=top_df["count"],
                y=top_df["product_name"],
                orientation="h",
                marker=dict(
                    color=top_df["count"],
                    colorscale=[[0, "#E8F0FE"], [1, "#1A73E8"]],
                    cornerradius=4,
                    line=dict(width=0),
                ),
                hovertemplate="<b>%{y}</b><br>%{x:,} release notes<extra></extra>",
            ))
        fig3.update_layout(
            **PLOTLY_LAYOUT,
            yaxis=dict(autorange="reversed", tickfont=dict(size=11, color="#3C4043")),
            xaxis=dict(showgrid=True, gridcolor="rgba(232, 234, 237, 0.5)", tickfont=dict(size=11, color="#3C4043")),
            height=400,
        )
        st.plotly_chart(fig3, use_container_width=True)

    with col4:
        st.markdown(
            '<div class="insights-title">Recent Activity Heatmap</div>'
            '<div class="insights-subtitle">Daily release note activity (last 3 months)</div>',
            unsafe_allow_html=True,
        )
        heatmap_data = fetch_heatmap()
        heatmap_df = pd.DataFrame(heatmap_data)
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

# ╔══════════════════════════════════════════════════════════════╗
# ║                      ASK AI TAB                              ║
# ╚══════════════════════════════════════════════════════════════╝
with tab_ai:
    # Model health check
    try:
        ai_status = requests.get(f"{BACKEND_URL}/api/ai/health", timeout=5).json()
        model_ready = ai_status.get("ready", False)
        if model_ready:
            st.success(f"Model **{ai_status['model']}** is ready.", icon="✅")
        else:
            st.warning(
                f"Model runner is reachable but **{ai_status['model']}** is not loaded yet. "
                "It will be pulled on first use — this may take a moment.",
                icon="⏳",
            )
    except Exception:
        st.error(
            "Model runner is not reachable. Make sure Docker Desktop Model Runner is enabled:\n\n"
            "```\ndocker desktop enable model-runner --tcp 12434\n```",
            icon="🔴",
        )
        model_ready = False

    # Context indicator
    _ai_products = st.session_state.watchlist or selected_products
    _ai_scope = (
        f"**{len(_ai_products)} products** from your stack: "
        + ", ".join(f"`{p}`" for p in _ai_products[:4])
        + (f" +{len(_ai_products) - 4} more" if len(_ai_products) > 4 else "")
        if _ai_products
        else "**all products** (no stack or filter set)"
    )
    _date_scope = f"`{start_date}` → `{end_date}`"
    st.markdown(
        f'<div class="ai-context-bar">'
        f'Answering about {_ai_scope} &nbsp;·&nbsp; {_date_scope}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Suggested questions
    st.markdown('<div class="ai-suggestions-label">Suggested questions</div>', unsafe_allow_html=True)

    _SUGGESTIONS = [
        ("📋", "Summarize the most important changes in the selected period"),
        ("⚠️", "What breaking changes require immediate action?"),
        ("🕐", "List all deprecations and what I need to do before they take effect"),
        ("🔒", "Are there any security-related updates I should know about?"),
        ("✨", "What major new features were released and which products got the most?"),
        ("📉", "Are there any changes that affect quotas, limits, or performance?"),
    ]

    # Apply suggestion to question input
    if st.session_state.pop("_ai_question_set", None) is not None:
        st.session_state["_ai_q"] = st.session_state.get("_ai_pending_q", "")

    _row1 = st.columns(3)
    _row2 = st.columns(3)
    for _idx, (_icon, _text) in enumerate(_SUGGESTIONS):
        _col = _row1[_idx] if _idx < 3 else _row2[_idx - 3]
        with _col:
            if st.button(
                f"{_icon} {_text}",
                key=f"ai_sugg_{_idx}",
                use_container_width=True,
            ):
                st.session_state["_ai_pending_q"] = _text
                st.session_state["_ai_question_set"] = True
                st.rerun()

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    # Question input
    if "_ai_q" not in st.session_state:
        st.session_state["_ai_q"] = ""

    question = st.text_area(
        "Your question",
        placeholder="e.g. Does the new Cloud Run timeout change affect my long-running jobs?",
        label_visibility="collapsed",
        height=90,
        key="_ai_q",
    )

    if st.button("Ask", type="primary", disabled=not (question or "").strip() or not model_ready):
        with st.spinner("Reading release notes and generating answer…"):
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/api/ai/chat",
                    json={
                        "question": question,
                        "products": _ai_products,
                        "types": selected_types,
                        "start_date": str(start_date),
                        "end_date": str(end_date),
                    },
                    timeout=180,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    st.markdown(
                        '<div class="ai-answer">',
                        unsafe_allow_html=True,
                    )
                    st.markdown(data["answer"])
                    st.markdown("</div>", unsafe_allow_html=True)
                    st.caption(
                        f"Based on {data['count']} release notes"
                        + (f" (of {data['total']:,} matching your filters)" if data["total"] > data["count"] else "")
                        + f" · {start_date} – {end_date}"
                    )
                else:
                    st.error(f"**Error {resp.status_code}:** {resp.json().get('detail', resp.text)}")
            except Exception as e:
                st.error(f"Request failed: {e}")

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
