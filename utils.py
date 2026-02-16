def format_description(description):
    """
    Format description text directly into Streamlit tabs
    """
    if not description or not isinstance(description, str):
        return
    description = description.replace('{: .external target="_blank" rel="noreferrer noopener"}',"")
    import re
    import streamlit as st
    
    # Find all track sections
    track_pattern = r'\* \{([^}]+)\}\{: track-name=\'([^\']+)\'\}'
    tracks = re.findall(track_pattern, description)
    
    # If no tracks found, just display the description
    if not tracks:
        st.markdown(description, unsafe_allow_html=True)
        return ""
        
    # Get all unique track names
    track_names = [track[0] for track in tracks]
    
    # Split description by track markers
    parts = re.split(track_pattern, description)
    
    # Display intro content if any
    intro = parts[0]
    if intro.strip():
        st.markdown(intro.strip())
    
    # Create tabs
    tabs = st.tabs(track_names)
    
    # Create dictionary to store content for each track
    track_content = {}
    
    # Process the remaining parts (every 3 items form a group: track name, track id, content)
    for i in range(1, len(parts), 3):
        if i+2 < len(parts):
            track_name = parts[i]
            content = parts[i+2].strip()
            track_content[track_name] = content
    
    # Fill each tab with content
    for tab, track_name in zip(tabs, track_names):
        if track_name in track_content:
            with tab:
                st.markdown(track_content[track_name])
    return ""
