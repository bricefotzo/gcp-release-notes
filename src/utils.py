"""Formatting utilities for release note descriptions."""

import re
import streamlit as st

TRACK_PATTERN = r'\* \{([^}]+)\}\{: track-name=\'([^\']+)\'\}'


def format_description(description: str | None) -> str:
    """
    Format description for display; handles track-name sections with tabs.
    Renders via st and returns empty string (for compatibility).
    """
    if not description or not isinstance(description, str):
        return ""
    description = description.replace(
        '{: .external target="_blank" rel="noreferrer noopener"}', ""
    )
    tracks = re.findall(TRACK_PATTERN, description)
    if not tracks:
        st.markdown(description, unsafe_allow_html=True)
        return ""
    track_names = [t[0] for t in tracks]
    parts = re.split(TRACK_PATTERN, description)
    intro = parts[0]
    if intro.strip():
        st.markdown(intro.strip())
    tabs = st.tabs(track_names)
    track_content = {}
    for i in range(1, len(parts), 3):
        if i + 2 < len(parts):
            track_content[parts[i]] = parts[i + 2].strip()
    for tab, name in zip(tabs, track_names):
        if name in track_content:
            with tab:
                st.markdown(track_content[name])
    return ""
