"""Ask AI tab rendering."""
import requests
import streamlit as st

from src.api.client import BACKEND_URL
from src.components.sidebar import FilterState
from src.state import session

_SUGGESTIONS = [
    ("📋", "Summarize the most important changes in the selected period"),
    ("⚠️", "What breaking changes require immediate action?"),
    ("🕐", "List all deprecations and what I need to do before they take effect"),
    ("🔒", "Are there any security-related updates I should know about?"),
    ("✨", "What major new features were released and which products got the most?"),
    ("📉", "Are there any changes that affect quotas, limits, or performance?"),
]


def render_ai_tab(filters: FilterState, watchlist: list[str]) -> None:
    model_ready = _render_model_status()
    _render_context_bar(filters, watchlist)
    _render_suggestions()
    _render_question_input(filters, watchlist, model_ready)


def _render_model_status() -> bool:
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
        return model_ready
    except Exception:
        st.error(
            "Model runner is not reachable. Make sure Docker Desktop Model Runner is enabled:\n\n"
            "```\ndocker desktop enable model-runner --tcp 12434\n```",
            icon="🔴",
        )
        return False


def _render_context_bar(filters: FilterState, watchlist: list[str]) -> None:
    ai_products = watchlist or filters.products
    if ai_products:
        scope = (
            f"**{len(ai_products)} products** from your stack: "
            + ", ".join(f"`{p}`" for p in ai_products[:4])
            + (f" +{len(ai_products) - 4} more" if len(ai_products) > 4 else "")
        )
    else:
        scope = "**all products** (no stack or filter set)"
    date_scope = f"`{filters.start_date}` → `{filters.end_date}`"
    st.markdown(
        f'<div class="ai-context-bar">Answering about {scope} &nbsp;·&nbsp; {date_scope}</div>',
        unsafe_allow_html=True,
    )


def _render_suggestions() -> None:
    st.markdown('<div class="ai-suggestions-label">Suggested questions</div>', unsafe_allow_html=True)

    if st.session_state.pop("_ai_question_set", None) is not None:
        st.session_state[session.AI_Q] = st.session_state.get("_ai_pending_q", "")

    row1 = st.columns(3)
    row2 = st.columns(3)
    for idx, (icon, text) in enumerate(_SUGGESTIONS):
        col = row1[idx] if idx < 3 else row2[idx - 3]
        with col:
            if st.button(f"{icon} {text}", key=f"ai_sugg_{idx}", use_container_width=True):
                st.session_state["_ai_pending_q"] = text
                st.session_state["_ai_question_set"] = True
                st.rerun()

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)


def _render_question_input(filters: FilterState, watchlist: list[str], model_ready: bool) -> None:
    question = st.text_area(
        "Your question",
        placeholder="e.g. Does the new Cloud Run timeout change affect my long-running jobs?",
        label_visibility="collapsed",
        height=90,
        key=session.AI_Q,
    )

    if st.button("Ask", type="primary", disabled=not (question or "").strip() or not model_ready):
        ai_products = watchlist or filters.products
        with st.spinner("Reading release notes and generating answer…"):
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/api/ai/chat",
                    json={
                        "question": question,
                        "products": ai_products,
                        "types": filters.types,
                        "start_date": str(filters.start_date),
                        "end_date": str(filters.end_date),
                    },
                    timeout=180,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    st.markdown('<div class="ai-answer">', unsafe_allow_html=True)
                    st.markdown(data["answer"])
                    st.markdown("</div>", unsafe_allow_html=True)
                    st.caption(
                        f"Based on {data['count']} release notes"
                        + (f" (of {data['total']:,} matching your filters)" if data["total"] > data["count"] else "")
                        + f" · {filters.start_date} – {filters.end_date}"
                    )
                else:
                    st.error(f"**Error {resp.status_code}:** {resp.json().get('detail', resp.text)}")
            except Exception as e:
                st.error(f"Request failed: {e}")
