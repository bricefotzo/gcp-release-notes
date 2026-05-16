"""Formatting utilities for release note descriptions."""

import re

import streamlit as st

TRACK_PATTERN = r'\* \{([^}]+)\}\{: track-name=\'([^\']+)\'\}'

_TYPE_MAP = {
    "FEATURE": "type-feature",
    "FIX": "type-fix",
    "ISSUE": "type-issue",
    "ANNOUNCEMENT": "type-announcement",
    "BREAKING_CHANGE": "type-breaking_change",
    "DEPRECATION": "type-deprecation",
}

_BADGE_MAP = {
    "FEATURE": "badge-feature",
    "FIX": "badge-fix",
    "ISSUE": "badge-issue",
    "ANNOUNCEMENT": "badge-announcement",
    "BREAKING_CHANGE": "badge-breaking_change",
    "DEPRECATION": "badge-deprecation",
}


def get_type_css_class(release_type: str | None) -> str:
    if not release_type:
        return "type-default"
    return _TYPE_MAP.get(release_type.upper().replace(" ", "_"), "type-default")


def get_badge_class(release_type: str | None) -> str:
    if not release_type:
        return "badge-default"
    return _BADGE_MAP.get(release_type.upper().replace(" ", "_"), "badge-default")


def format_description(description: str | None) -> str:
    """Format description for display; handles track-name sections with tabs."""
    if not description or not isinstance(description, str):
        return ""
    description = description.replace(
        '{: .external target="_blank" rel="noreferrer noopener"}', ""
    )
    tracks = re.findall(TRACK_PATTERN, description)
    if not tracks:
        st.markdown(
            f'<div class="note-description">{description}</div>',
            unsafe_allow_html=True,
        )
        return ""
    track_names = [t[0] for t in tracks]
    parts = re.split(TRACK_PATTERN, description)
    intro = parts[0]
    if intro.strip():
        st.markdown(
            f'<div class="note-description">{intro.strip()}</div>',
            unsafe_allow_html=True,
        )
    tabs = st.tabs(track_names)
    track_content = {}
    for i in range(1, len(parts), 3):
        if i + 2 < len(parts):
            track_content[parts[i]] = parts[i + 2].strip()
    for tab, name in zip(tabs, track_names):
        if name in track_content:
            with tab:
                st.markdown(
                    f'<div class="note-description">{track_content[name]}</div>',
                    unsafe_allow_html=True,
                )
    return ""
