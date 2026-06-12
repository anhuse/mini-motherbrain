"""Chart styling in one place: design tokens, a global Plotly template, and a
builder per figure. Every current and future page draws through these so the
visual language stays consistent as the app grows."""

import plotly.graph_objects as go
import plotly.io as pio

from mini_motherbrain.app.geo import norway_municipalities
from mini_motherbrain.search.models import FacetBucket

# Tokens mirrored in assets/style.css — change both together.
INK = "#1C1814"
MUTED = "#6E675E"
HAIRLINE = "#E8E1D6"
PAPER = "#FAF7F2"
ORANGE = "#FF5800"
ORANGE_DEEP = "#B33D00"
ORANGE_TINT = "#FFE9DC"

FONT = "Archivo, sans-serif"

pio.templates["motherbrain"] = go.layout.Template(
    layout={
        "font": {"family": FONT, "size": 12.5, "color": INK},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "colorway": [ORANGE, INK, MUTED],
        "margin": {"l": 0, "r": 0, "t": 8, "b": 0},
        "hoverlabel": {
            "bgcolor": INK,
            "bordercolor": INK,
            "font": {"family": FONT, "size": 12, "color": PAPER},
        },
        "xaxis": {
            "gridcolor": HAIRLINE,
            "linecolor": HAIRLINE,
            "ticks": "",
            "zeroline": False,
            "fixedrange": True,
        },
        "yaxis": {
            "gridcolor": HAIRLINE,
            "linecolor": HAIRLINE,
            "ticks": "",
            "zeroline": False,
            "fixedrange": True,
        },
    }
)
pio.templates.default = "motherbrain"

# Charts are exhibits, not interactive widgets: no toolbar, no zoom.
GRAPH_CONFIG = {"displayModeBar": False}


def industry_figure(buckets: list[FacetBucket]) -> go.Figure:
    """Horizontal bars, largest on top, counts labelled at the bar ends so no
    x-axis is needed."""
    buckets = list(reversed(buckets))
    fig = go.Figure(
        go.Bar(
            x=[b.count for b in buckets],
            y=[_truncate(b.key) for b in buckets],
            orientation="h",
            marker={"color": ORANGE},
            text=[f"{b.count:,}" for b in buckets],
            textposition="outside",
            textfont={"color": MUTED, "size": 11.5},
            cliponaxis=False,
            hovertemplate="%{customdata}<br>%{x:,} companies<extra></extra>",
            customdata=[b.key for b in buckets],
        )
    )
    fig.update_layout(
        height=320,
        bargap=0.45,
        margin={"l": 0, "r": 48, "t": 8, "b": 8},
        xaxis={"visible": False},
        yaxis={"showgrid": False, "tickfont": {"size": 12}, "automargin": True},
    )
    return fig


def founded_figure(buckets: list[FacetBucket]) -> go.Figure:
    """Founding-year histogram; sparse early years read as a long quiet tail."""
    fig = go.Figure(
        go.Bar(
            x=[b.key for b in buckets],
            y=[b.count for b in buckets],
            marker={"color": ORANGE},
            hovertemplate="%{x}: %{y:,} companies<extra></extra>",
        )
    )
    fig.update_layout(
        height=320,
        bargap=0.25,
        margin={"l": 0, "r": 8, "t": 8, "b": 8},
        xaxis={
            "showgrid": False,
            "tickfont": {"size": 11.5, "color": MUTED},
            "automargin": True,
        },
        yaxis={
            "gridcolor": HAIRLINE,
            "griddash": "dot",
            "tickfont": {"size": 11.5, "color": MUTED},
            "tickformat": ",",
            "automargin": True,
        },
    )
    return fig


def norway_map_figure(buckets: list[FacetBucket]) -> go.Figure:
    """Choropleth of company counts by municipality. Counts span ~50 to ~80k,
    so colour follows a quartic-root scale to keep mid-sized municipalities
    visible; hovers carry the true counts."""
    counts = {b.key: b.count for b in buckets}
    keys = list(counts)
    fig = go.Figure(
        go.Choropleth(
            geojson=norway_municipalities(),
            featureidkey="properties.join_key",
            locations=keys,
            z=[counts[k] ** 0.25 for k in keys],
            customdata=[[k.title(), counts[k]] for k in keys],
            colorscale=[(0.0, ORANGE_TINT), (0.55, ORANGE), (1.0, ORANGE_DEEP)],
            marker_line_color=PAPER,
            marker_line_width=0.4,
            showscale=False,
            hovertemplate="%{customdata[0]}<br>%{customdata[1]:,} companies<extra></extra>",
        )
    )
    fig.update_geos(
        fitbounds="locations",
        visible=False,
        bgcolor="rgba(0,0,0,0)",
        projection_type="mercator",
    )
    fig.update_layout(height=680, margin={"l": 0, "r": 0, "t": 0, "b": 0}, dragmode=False)
    return fig


def _truncate(label: str, limit: int = 38) -> str:
    return label if len(label) <= limit else label[: limit - 1] + "…"
