"""Screen page: a PE deal-sourcing tool. The funnel shows how a thesis narrows
the register stage by stage, and the table lets an analyst mark a shortlist and
export it. One callback recomputes the funnel, table, facets and summary
together so everything stays consistent with the current filters."""

import csv
import io
from dataclasses import dataclass
from math import ceil

import dash
import plotly.graph_objects as go
from dash import (
    Input,
    Output,
    State,
    callback,
    callback_context,
    dash_table,
    dcc,
    html,
    no_update,
)
from dash.dash_table.Format import Format, Group

from mini_motherbrain.app.figures import GRAPH_CONFIG, HAIRLINE, ORANGE
from mini_motherbrain.config import settings
from mini_motherbrain.es.client import get_client
from mini_motherbrain.search.models import MAX_RESULT_WINDOW, SearchRequest
from mini_motherbrain.search.queries import build_query
from mini_motherbrain.search.service import search

dash.register_page(
    __name__, path="/screen", name="Screen", title="Screen — Mini-Motherbrain"
)

PAGE_SIZE = 20
MAX_PAGES = MAX_RESULT_WINDOW // PAGE_SIZE


@dataclass(frozen=True)
class FunnelStage:
    """One narrowing step in the sourcing funnel. The flags decide which
    dimension-specific filter groups the stage applies; geography and text
    always apply from the active stage onward (they are the thesis scope)."""

    label: str
    active: bool = False
    industry: bool = False
    size: bool = False
    margin: bool = False


# Edit this list to reorder or add stages — nothing else needs to change.
FUNNEL_STAGES = [
    FunnelStage("All AS/ASA"),
    FunnelStage("Active", active=True),
    FunnelStage("Industry", active=True, industry=True),
    FunnelStage("Size", active=True, industry=True, size=True),
    FunnelStage("Profitability", active=True, industry=True, size=True, margin=True),
]

COLUMNS = [
    {"name": "Name", "id": "name", "presentation": "markdown"},
    {"name": "Industry", "id": "industry_text"},
    {"name": "Municipality", "id": "municipality"},
    {"name": "Employees", "id": "employees", "type": "numeric", "format": Format(group=Group.yes)},
    {
        "name": "Revenue (NOK m)",
        "id": "revenue",
        "type": "numeric",
        "format": Format(group=Group.yes),
    },
    {"name": "Operating margin", "id": "operating_margin"},
    {"name": "Founded", "id": "founded_at"},
]


def _filters(query, municipality, min_employees, max_employees, min_revenue, min_margin):
    return {
        "text": query or None,
        "municipalities": [municipality] if municipality else [],
        "min_employees": int(min_employees) if min_employees is not None else None,
        "max_employees": int(max_employees) if max_employees is not None else None,
        "min_revenue": int(min_revenue * 1_000_000) if min_revenue is not None else None,
        "min_operating_margin": min_margin / 100 if min_margin is not None else None,
    }


def _stage_request(stage: FunnelStage, base: dict, industry) -> SearchRequest:
    """Build the SearchRequest for one funnel stage. Text and municipality (the
    thesis scope) apply from the active stage onward; the stage flags gate the
    dimension-specific filters."""
    scoped = stage.active or stage.industry or stage.size or stage.margin
    return SearchRequest(
        text=base["text"] if scoped else None,
        municipalities=base["municipalities"] if scoped else [],
        exclude_inactive=stage.active,
        industry_codes=[industry] if stage.industry and industry else [],
        min_employees=base["min_employees"] if stage.size else None,
        max_employees=base["max_employees"] if stage.size else None,
        min_revenue=base["min_revenue"] if stage.size else None,
        min_operating_margin=base["min_operating_margin"] if stage.margin else None,
        size=0,
    )


def _funnel_counts(base: dict, industry) -> list[int]:
    client = get_client()
    counts = []
    for stage in FUNNEL_STAGES:
        req = _stage_request(stage, base, industry)
        resp = client.search(
            index=settings.companies_index,
            query=build_query(req),
            size=0,
            track_total_hits=True,
        )
        counts.append(resp["hits"]["total"]["value"])
    return counts


def _funnel_figure(counts: list[int]) -> go.Figure:
    fig = go.Figure(
        go.Funnel(
            y=[s.label for s in FUNNEL_STAGES],
            x=counts,
            textinfo="label+value+percent initial",
            marker={"color": ORANGE},
            connector={"line": {"color": HAIRLINE, "width": 2}},
        )
    )
    fig.update_layout(height=360, margin={"l": 140, "r": 20, "t": 8, "b": 8})
    return fig


def _row(c):
    row = c.model_dump(
        mode="json", include={"industry_text", "municipality", "employees", "founded_at"}
    )
    safe_name = c.name.replace("[", "(").replace("]", ")")
    row["name"] = f"[{safe_name}](/company/{c.org_number})"
    row["municipality"] = (c.municipality or "").title()
    row["revenue"] = round(c.revenue / 1_000_000) if c.revenue is not None else None
    row["operating_margin"] = (
        f"{c.operating_margin * 100:.1f}%" if c.operating_margin is not None else "—"
    )
    return row


def layout(**_) -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.H1("Screen", className="page-title"),
                    html.P(id="screen-summary", className="result-count"),
                ],
                className="page-head",
            ),
            html.Div(
                [
                    dcc.Input(
                        id="screen-query",
                        type="text",
                        placeholder="Thesis keywords…",
                        debounce=True,
                        className="toolbar-search",
                    ),
                    dcc.Dropdown(
                        id="screen-industry",
                        placeholder="Industry",
                        clearable=True,
                        multi=False,
                        className="toolbar-filter",
                    ),
                    dcc.Dropdown(
                        id="screen-municipality",
                        placeholder="Municipality",
                        clearable=True,
                        multi=False,
                        className="toolbar-filter",
                    ),
                    dcc.Checklist(
                        id="screen-active-only",
                        options=[{"label": "Active only", "value": "yes"}],
                        value=[],
                        className="toolbar-toggle",
                    ),
                    dcc.Input(
                        id="screen-min-employees",
                        type="number",
                        placeholder="Min employees",
                        debounce=True,
                        className="toolbar-filter",
                    ),
                    dcc.Input(
                        id="screen-max-employees",
                        type="number",
                        placeholder="Max employees",
                        debounce=True,
                        className="toolbar-filter",
                    ),
                    dcc.Input(
                        id="screen-min-revenue",
                        type="number",
                        placeholder="Min revenue (NOK m)",
                        debounce=True,
                        min=0,
                        className="toolbar-filter",
                    ),
                    dcc.Input(
                        id="screen-min-margin",
                        type="number",
                        placeholder="Min margin %",
                        debounce=True,
                        className="toolbar-filter",
                    ),
                ],
                className="toolbar",
            ),
            html.Div(
                dcc.Graph(id="screen-funnel", config=GRAPH_CONFIG),
                className="card chart-card",
            ),
            html.Div(
                dash_table.DataTable(
                    id="screen-results",
                    columns=COLUMNS,
                    markdown_options={"link_target": "_self"},
                    page_action="custom",
                    page_current=0,
                    page_size=PAGE_SIZE,
                    sort_action="custom",
                    sort_mode="single",
                    sort_by=[],
                    row_selectable="multi",
                    selected_rows=[],
                    cell_selectable=False,
                    style_as_list_view=True,
                    style_cell={
                        "fontFamily": "Archivo, 'Helvetica Neue', sans-serif",
                        "fontSize": "14px",
                        "textAlign": "left",
                        "padding": "12px 14px",
                        "backgroundColor": "transparent",
                    },
                    style_header={
                        "fontSize": "11px",
                        "fontWeight": "600",
                        "letterSpacing": "0.14em",
                        "textTransform": "uppercase",
                        "color": "#6e675e",
                        "borderBottom": "2px solid #1c1814",
                        "paddingTop": "16px",
                    },
                    style_data={"borderBottom": "1px solid #e8e1d6"},
                    style_cell_conditional=[
                        {"if": {"column_id": "employees"}, "textAlign": "right", "width": "110px"},
                        {"if": {"column_id": "revenue"}, "textAlign": "right", "width": "130px"},
                        {
                            "if": {"column_id": "operating_margin"},
                            "textAlign": "right",
                            "width": "130px",
                        },
                        {"if": {"column_id": "founded_at"}, "width": "120px"},
                        {"if": {"column_id": "municipality"}, "width": "180px"},
                    ],
                ),
                className="card table-card",
            ),
            html.Div(
                [
                    html.Div(id="screen-selection-summary", className="result-count"),
                    html.Button("Export CSV", id="screen-export-btn", className="btn"),
                    dcc.Download(id="screen-download"),
                ],
                className="screen-selection",
            ),
        ],
        className="page",
    )


@callback(
    Output("screen-funnel", "figure"),
    Output("screen-results", "data"),
    Output("screen-results", "page_count"),
    Output("screen-results", "page_current"),
    Output("screen-summary", "children"),
    Output("screen-industry", "options"),
    Output("screen-municipality", "options"),
    Input("screen-query", "value"),
    Input("screen-industry", "value"),
    Input("screen-municipality", "value"),
    Input("screen-active-only", "value"),
    Input("screen-min-employees", "value"),
    Input("screen-max-employees", "value"),
    Input("screen-min-revenue", "value"),
    Input("screen-min-margin", "value"),
    Input("screen-results", "page_current"),
    Input("screen-results", "sort_by"),
)
def update(
    query, industry, municipality, active_only, min_employees, max_employees,
    min_revenue, min_margin, page_current, sort_by,
):
    if callback_context.triggered_id != "screen-results":
        page_current = 0

    base = _filters(query, municipality, min_employees, max_employees, min_revenue, min_margin)
    figure = _funnel_figure(_funnel_counts(base, industry))

    sort_field = sort_by[0]["column_id"] if sort_by else None
    sort_desc = bool(sort_by) and sort_by[0]["direction"] == "desc"

    request = SearchRequest(
        text=base["text"],
        industry_codes=[industry] if industry else [],
        municipalities=base["municipalities"],
        exclude_inactive=bool(active_only),
        min_employees=base["min_employees"],
        max_employees=base["max_employees"],
        min_revenue=base["min_revenue"],
        min_operating_margin=base["min_operating_margin"],
        size=PAGE_SIZE,
        offset=page_current * PAGE_SIZE,
        sort_field=sort_field,
        sort_desc=sort_desc,
    )
    result = search(request)

    rows = [_row(c) for c in result.companies]
    page_count = min(ceil(result.total / PAGE_SIZE), MAX_PAGES) if result.total else 1

    summary = f"{result.total:,} companies"
    if result.total > MAX_RESULT_WINDOW:
        summary += f" · first {MAX_RESULT_WINDOW:,} browsable"

    industry_options = [
        {"label": f"{b.label or b.key} ({b.count:,})", "value": b.key}
        for b in result.facets["industries"]
    ]
    municipality_options = [
        {"label": f"{b.key.title()} ({b.count:,})", "value": b.key}
        for b in result.facets["municipalities"]
    ]

    return (
        figure,
        rows,
        page_count,
        page_current,
        summary,
        industry_options,
        municipality_options,
    )


@callback(
    Output("screen-download", "data"),
    Output("screen-selection-summary", "children"),
    Input("screen-export-btn", "n_clicks"),
    Input("screen-results", "selected_rows"),
    State("screen-results", "data"),
    prevent_initial_call=True,
)
def export(n_clicks, selected_rows, data):
    selected_rows = selected_rows or []
    summary = f"{len(selected_rows)} companies selected"

    if callback_context.triggered_id != "screen-export-btn" or not selected_rows:
        return no_update, summary

    fields = [c["id"] for c in COLUMNS]
    headers = [c["name"] for c in COLUMNS]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for i in selected_rows:
        if i < len(data):
            writer.writerow([data[i].get(f, "") for f in fields])

    return dcc.send_string(buffer.getvalue(), "shortlist.csv"), summary
