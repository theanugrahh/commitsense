"""Plotly chart builders for the analytics dashboard.

All inputs come from actual analysis results — no fabricated data.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go

GRID_COLOR = "rgba(201,209,217,0.12)"
FONT_COLOR = "#c9d1d9"


def _style(fig: go.Figure, height: int = 300) -> go.Figure:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=FONT_COLOR, size=12),
        margin=dict(l=8, r=8, t=32, b=8),
        height=height,
        bargap=0.15,
    )
    fig.update_xaxes(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR)
    fig.update_yaxes(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR)
    return fig


def timeline_chart(timeline: list[tuple[date, int]]) -> go.Figure:
    """Commit activity over time (bar or line depending on density)."""
    df = pd.DataFrame(timeline, columns=["date", "commits"])
    if len(df) > 180:
        df = (
            df.set_index("date")
            .rolling("7D").sum()
            .reset_index()
            .rename(columns={"commits": "commits"})
        )
        df["commits"] = df["commits"].round(3)
        fig = go.Figure(
            go.Scatter(x=df["date"], y=df["commits"], fill="tozeroy",
                       line=dict(color="#4dabf7", width=2), name="Commits (7d)")
        )
    else:
        fig = go.Figure(
            go.Bar(x=df["date"], y=df["commits"], marker_color="#4dabf7",
                   name="Commits")
        )
    return _style(fig, height=280)


def size_distribution_chart(dist: list[tuple[str, int]]) -> go.Figure:
    """Commit size buckets as horizontal bars."""
    df = pd.DataFrame([("Bucket", "Count", c, n) for (n, c) in dist],
                      columns=["Bucket", "Count", "count", "label"])
    orient_map = {
        "Tiny (<= 10 lines)": "#69db7c",
        "Small (<= 50 lines)": "#4dabf7",
        "Medium (<= 200 lines)": "#ffd43b",
        "Large (<= 800 lines)": "#ff922b",
        "Very large (> 800 lines)": "#ff6b6b",
    }
    labels = [label for (label, _) in dist]
    counts = [count for (_, count) in dist]
    fig = go.Figure(
        go.Bar(
            y=labels,
            x=counts,
            orientation="h",
            marker_color=[orient_map.get(l, "#4dabf7") for l in labels],
        )
    )
    fig.update_yaxes(autorange="reversed")
    return _style(fig, height=260)


def quality_donut(grades: dict) -> go.Figure:
    """Donut chart of message quality grade distribution."""
    colors = {"good": "#69db7c", "fair": "#ffd43b", "poor": "#ff6b6b"}
    fig = go.Figure(
        go.Pie(
            labels=[g.capitalize() for g in grades],
            values=list(grades.values()),
            hole=0.62,
            marker=dict(colors=[colors[g] for g in grades]),
            textinfo="value+percent",
            textfont=dict(color=FONT_COLOR, size=12),
        )
    )
    return _style(fig, height=280)


def top_files_chart(file_changes: list[tuple[str, int]], top_n: int = 12) -> go.Figure:
    """Most frequently modified files as horizontal bars."""
    top = file_changes[:top_n]
    names = [name for name, _ in top][::-1]
    counts = [count for _, count in top][::-1]
    fig = go.Figure(
        go.Bar(
            y=names,
            x=counts,
            orientation="h",
            marker_color="#748ffc",
        )
    )
    fig.update_yaxes(tickfont=dict(size=11))
    return _style(fig, height=max(240, 28 * len(names) + 60))


def contributors_chart(contributors: dict[str, dict], top_n: int = 10) -> go.Figure:
    """Per-author commit counts."""
    ranked = sorted(contributors.values(), key=lambda e: e["commits"], reverse=True)[:top_n]
    names = [e["name"] for e in ranked][::-1]
    counts = [e["commits"] for e in ranked][::-1]
    fig = go.Figure(go.Bar(y=names, x=counts, orientation="h", marker_color="#38d9a9"))
    fig.update_yaxes(tickfont=dict(size=11))
    return _style(fig, height=max(240, 28 * len(names) + 60))
