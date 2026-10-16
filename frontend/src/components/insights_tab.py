"""Insights & Analytics tab rendering."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.api.client import fetch_heatmap, fetch_time_series, fetch_top_products, fetch_type_distribution

_LAYOUT = dict(
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

_COLORS = [
    "#1A73E8", "#34A853", "#EA4335", "#F9AB00",
    "#9334E6", "#00897B", "#E91E63", "#FF6D00",
]


def render_insights_tab() -> None:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            '<div class="insights-title">Release Activity</div>'
            '<div class="insights-subtitle">Monthly volume over the last 12 months</div>',
            unsafe_allow_html=True,
        )
        _render_time_series()
    with col2:
        st.markdown(
            '<div class="insights-title">Note Type Distribution</div>'
            '<div class="insights-subtitle">Breakdown by release note category</div>',
            unsafe_allow_html=True,
        )
        _render_type_distribution()

    st.markdown("<div style='height: 1rem'></div>", unsafe_allow_html=True)
    col3, col4 = st.columns(2)
    with col3:
        st.markdown(
            '<div class="insights-title">Top Products</div>'
            '<div class="insights-subtitle">Most active products by release note count</div>',
            unsafe_allow_html=True,
        )
        _render_top_products()
    with col4:
        st.markdown(
            '<div class="insights-title">Recent Activity Heatmap</div>'
            '<div class="insights-subtitle">Daily release note activity (last 3 months)</div>',
            unsafe_allow_html=True,
        )
        _render_heatmap()


def _render_time_series() -> None:
    time_df = pd.DataFrame(fetch_time_series())
    fig = go.Figure()
    if not time_df.empty:
        fig.add_trace(go.Scatter(
            x=time_df["month"],
            y=time_df["count"],
            mode="lines+markers",
            line=dict(color="#1A73E8", width=2.5, shape="spline"),
            marker=dict(size=7, color="#1A73E8", line=dict(width=2, color="white")),
            fill="tozeroy",
            fillcolor="rgba(26, 115, 232, 0.08)",
            hovertemplate="<b>%{x|%B %Y}</b><br>%{y} release notes<extra></extra>",
        ))
    fig.update_layout(
        **_LAYOUT,
        xaxis=dict(showgrid=False, tickformat="%b %Y", linecolor="#E8EAED", tickfont=dict(size=11, color="#3C4043")),
        yaxis=dict(showgrid=True, gridcolor="rgba(232, 234, 237, 0.5)", gridwidth=1, tickfont=dict(size=11, color="#3C4043")),
        height=350,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_type_distribution() -> None:
    types_df = pd.DataFrame(fetch_type_distribution())
    fig = go.Figure()
    if not types_df.empty:
        fig.add_trace(go.Pie(
            labels=types_df["release_note_type"],
            values=types_df["count"],
            hole=0.55,
            marker=dict(colors=_COLORS[:len(types_df)], line=dict(color="white", width=2.5)),
            textinfo="label+percent",
            textfont=dict(size=11),
            hovertemplate="<b>%{label}</b><br>%{value:,} notes (%{percent})<extra></extra>",
        ))
    fig.update_layout(**_LAYOUT, showlegend=False, height=350)
    st.plotly_chart(fig, use_container_width=True)


def _render_top_products() -> None:
    top_df = pd.DataFrame(fetch_top_products())
    fig = go.Figure()
    if not top_df.empty:
        fig.add_trace(go.Bar(
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
    fig.update_layout(
        **_LAYOUT,
        yaxis=dict(autorange="reversed", tickfont=dict(size=11, color="#3C4043")),
        xaxis=dict(showgrid=True, gridcolor="rgba(232, 234, 237, 0.5)", tickfont=dict(size=11, color="#3C4043")),
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_heatmap() -> None:
    heatmap_df = pd.DataFrame(fetch_heatmap())
    if heatmap_df.empty:
        st.info("Not enough data for the heatmap.")
        return
    pivot_df = heatmap_df.pivot_table(
        index="day_of_week", columns="week", values="count", fill_value=0
    )
    day_labels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    week_labels = [f"W{pd.Timestamp(w).isocalendar()[1]}" for w in pivot_df.columns]
    fig = go.Figure(data=go.Heatmap(
        z=pivot_df.values,
        x=week_labels,
        y=[day_labels[int(d) - 1] for d in pivot_df.index],
        colorscale=[[0, "#F8FAFE"], [0.5, "#A8C7FA"], [1, "#1A73E8"]],
        showscale=False,
        hovertemplate="<b>%{x} · %{y}</b><br>%{z} notes<extra></extra>",
        xgap=3,
        ygap=3,
    ))
    fig.update_layout(
        **_LAYOUT,
        xaxis=dict(showgrid=False, tickfont=dict(size=10, color="#3C4043")),
        yaxis=dict(tickfont=dict(size=11, color="#3C4043"), autorange="reversed"),
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)
