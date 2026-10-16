"""Shared UI banner components."""
from datetime import date

import pandas as pd
import streamlit as st

from src.utils import format_description, get_badge_class, get_type_css_class

_CALENDAR_ICON = '<svg viewBox="0 0 24 24"><path d="M19 3h-1V1h-2v2H8V1H6v2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V8h14v11zM9 10H7v2h2v-2zm4 0h-2v2h2v-2zm4 0h-2v2h2v-2z"/></svg>'


def render_breaking_changes_banner(
    bc_df: pd.DataFrame,
    bc_total: int,
    start_date: date,
    end_date: date,
    active_watchlist: list[str],
    selected_products: list[str],
) -> None:
    if bc_total == 0 or bc_df.empty:
        return

    bc_df = bc_df.copy()
    bc_df["published_at"] = pd.to_datetime(bc_df["published_at"])

    breaking = bc_df[bc_df["release_note_type"].str.upper() == "BREAKING_CHANGE"]
    deprecations = bc_df[bc_df["release_note_type"].str.upper() == "DEPRECATION"]

    summary_parts = []
    if len(breaking):
        summary_parts.append(f"<strong>{len(breaking)}</strong> breaking change{'s' if len(breaking) != 1 else ''}")
    if len(deprecations):
        summary_parts.append(f"<strong>{len(deprecations)}</strong> deprecation{'s' if len(deprecations) != 1 else ''}")
    summary_text = " and ".join(summary_parts)

    if active_watchlist:
        scope_label = "for <strong>your stack</strong>"
    elif selected_products:
        scope_label = "for your selection"
    else:
        scope_label = "across all products"

    date_label = f"{start_date.strftime('%b %d, %Y')} – {end_date.strftime('%b %d, %Y')}"

    # Compact one-line banner — product tags stay inside the expander
    st.markdown(
        f"""
        <div class="bc-banner">
            <div class="bc-banner-header">
                <span class="bc-banner-icon">⚠</span>
                <span class="bc-banner-count">{bc_total}</span>
                <span class="bc-banner-title">Breaking Changes &amp; Deprecations</span>
                <span class="bc-banner-subtitle">
                    {summary_text} {scope_label} &nbsp;·&nbsp; {date_label}
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    unique_products = sorted(bc_df["product_name"].dropna().unique())
    MAX_TAGS = 12
    tags_html = "".join(f'<span class="bc-product-tag">{p}</span>' for p in unique_products[:MAX_TAGS])
    if len(unique_products) > MAX_TAGS:
        tags_html += f'<span class="bc-product-tag bc-product-tag-more">+{len(unique_products) - MAX_TAGS} more</span>'

    with st.expander(f"View all {bc_total} notes", expanded=False):
        st.markdown(f'<div class="bc-tags" style="margin-bottom:1rem">{tags_html}</div>', unsafe_allow_html=True)
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
                                {_CALENDAR_ICON}
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
