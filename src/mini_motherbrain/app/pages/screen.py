"""Screen page: a PE deal-sourcing tool laid out as a guided, left-to-right
screening flow. A horizontal chevron strip shows how a thesis narrows the
register stage by stage (All AS/ASA → Active → Industry → Size → Profitability)
with a live count per stage; clicking a stage reveals just that step's controls
below. The results table feeds a persistent shortlist side panel that exports to
CSV. Separate callbacks keep the funnel counts, the results, the step navigation
and the shortlist consistent with the current filters."""

import csv
import io
from dataclasses import dataclass
from math import ceil

import dash
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


# Edit this list to reorder or add stages — the chevron strip, the step panels
# and the navigation all derive their count from it.
FUNNEL_STAGES = [
    FunnelStage("All AS/ASA"),
    FunnelStage("Active", active=True),
    FunnelStage("Industry", active=True, industry=True),
    FunnelStage("Size", active=True, industry=True, size=True),
    FunnelStage("Profitability", active=True, industry=True, size=True, margin=True),
]

# Per-step panel copy. One entry per FUNNEL_STAGES item; the step at index 1
# carries the thesis-scope controls (text + geography + active), which the data
# model folds into the "Active" stage.
STEP_META = [
    ("All AS/ASA", "The full register of AS/ASA companies — your starting universe."),
    ("Thesis & scope", "Free-text thesis, geography, and whether to drop inactive companies."),
    ("Industry", "Narrow to a sector by its NACE industry code."),
    ("Size", "Set an employee-count range and a revenue floor."),
    ("Profitability", "Require a minimum operating margin."),
]

# Step shown on first load: the thesis-scope step (the first with controls).
DEFAULT_STEP = 1

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


def _chevron_children(index: int, stage: FunnelStage, count: int, initial: int) -> list:
    """The inner content of one chevron: number badge, stage name, surviving
    count, and an orange volume bar sized against the starting universe."""
    pct = max(count / initial * 100, 1.5) if initial else 0
    return [
        html.Div(
            [
                html.Span(str(index + 1), className="chev-num"),
                html.Span(stage.label, className="chev-name"),
            ],
            className="chev-top",
        ),
        html.Span(f"{count:,}", className="chev-count"),
        html.Span(
            html.Span(className="chev-bar-fill", style={"width": f"{pct:.1f}%"}),
            className="chev-bar",
        ),
    ]


def _step_controls(index: int) -> list:
    """The filter controls for one step. IDs are preserved from the original
    toolbar so the results/funnel callbacks read them unchanged."""
    if index == 0:
        return [html.P("Pick a stage above to start narrowing.", className="step-note")]
    if index == 1:
        return [
            dcc.Input(
                id="screen-query",
                type="text",
                placeholder="Thesis keywords…",
                debounce=True,
                className="step-field step-field-wide",
            ),
            dcc.Dropdown(
                id="screen-municipality",
                placeholder="Municipality",
                clearable=True,
                className="toolbar-filter step-select",
            ),
            dcc.Checklist(
                id="screen-active-only",
                options=[{"label": "Active companies only", "value": "yes"}],
                value=[],
                className="step-check",
            ),
        ]
    if index == 2:
        return [
            dcc.Dropdown(
                id="screen-industry",
                placeholder="Industry (NACE)",
                clearable=True,
                className="toolbar-filter step-select",
            )
        ]
    if index == 3:
        return [
            dcc.Input(
                id="screen-min-employees",
                type="number",
                placeholder="Min employees",
                debounce=True,
                className="step-field",
            ),
            dcc.Input(
                id="screen-max-employees",
                type="number",
                placeholder="Max employees",
                debounce=True,
                className="step-field",
            ),
            dcc.Input(
                id="screen-min-revenue",
                type="number",
                placeholder="Min revenue (NOK m)",
                debounce=True,
                min=0,
                className="step-field",
            ),
        ]
    if index == 4:
        return [
            dcc.Input(
                id="screen-min-margin",
                type="number",
                placeholder="Min operating margin %",
                debounce=True,
                className="step-field",
            )
        ]
    return []


def _step_panel(index: int) -> html.Div:
    title, sub = STEP_META[index]
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(
                                f"Step {index + 1} of {len(FUNNEL_STAGES)}",
                                className="step-kicker",
                            ),
                            html.H3(title, className="step-title"),
                        ]
                    ),
                    html.Span(id=f"screen-delta-{index}", className="step-delta"),
                ],
                className="step-head",
            ),
            html.P(sub, className="step-sub"),
            html.Div(_step_controls(index), className="step-controls"),
        ],
        id=f"screen-step-{index}",
        className="step-panel",
        style={} if index == DEFAULT_STEP else {"display": "none"},
    )


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


def _display_name(markdown: str) -> str:
    """Pull the display name out of a '[Name](/company/..)' markdown cell."""
    if markdown.startswith("[") and "]" in markdown:
        return markdown[1 : markdown.index("]")]
    return markdown


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
            # Horizontal flow: the sourcing funnel as a clickable chevron strip.
            html.Div(
                [
                    html.Button(id=f"screen-chev-{i}", n_clicks=0, className="chev")
                    for i in range(len(FUNNEL_STAGES))
                ],
                className="screen-flow",
            ),
            # The active step's controls, shown one at a time below the strip.
            html.Div(
                [_step_panel(i) for i in range(len(FUNNEL_STAGES))],
                className="step-stack card",
            ),
            # Results beside a persistent shortlist side panel.
            html.Div(
                [
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
                            html.H3("Shortlist", className="aside-title"),
                            html.P(id="screen-selection-summary", className="aside-count"),
                            html.Div(id="screen-shortlist-list", className="shortlist-list"),
                            html.Button(
                                "Export CSV",
                                id="screen-export-btn",
                                className="btn-primary aside-export",
                            ),
                            dcc.Download(id="screen-download"),
                        ],
                        className="screen-aside card",
                    ),
                ],
                className="screen-body",
            ),
        ],
        className="page screen-page",
    )


@callback(
    [Output(f"screen-chev-{i}", "children") for i in range(len(FUNNEL_STAGES))]
    + [Output(f"screen-delta-{i}", "children") for i in range(len(FUNNEL_STAGES))],
    Input("screen-query", "value"),
    Input("screen-industry", "value"),
    Input("screen-municipality", "value"),
    Input("screen-min-employees", "value"),
    Input("screen-max-employees", "value"),
    Input("screen-min-revenue", "value"),
    Input("screen-min-margin", "value"),
)
def render_funnel(query, industry, municipality, min_employees, max_employees, min_revenue, min_margin):
    base = _filters(query, municipality, min_employees, max_employees, min_revenue, min_margin)
    counts = _funnel_counts(base, industry)
    initial = counts[0] or 1

    chevrons = [
        _chevron_children(i, FUNNEL_STAGES[i], counts[i], initial) for i in range(len(counts))
    ]
    deltas = [
        f"{counts[i]:,} companies" if i == 0 else f"{counts[i - 1]:,} → {counts[i]:,}"
        for i in range(len(counts))
    ]
    return chevrons + deltas


@callback(
    [Output(f"screen-chev-{i}", "className") for i in range(len(FUNNEL_STAGES))]
    + [Output(f"screen-step-{i}", "style") for i in range(len(FUNNEL_STAGES))],
    [Input(f"screen-chev-{i}", "n_clicks") for i in range(len(FUNNEL_STAGES))],
)
def navigate(*_clicks):
    active = DEFAULT_STEP
    trigger = callback_context.triggered_id
    if trigger and trigger.startswith("screen-chev-"):
        active = int(trigger.rsplit("-", 1)[-1])

    classes = ["chev is-active" if i == active else "chev" for i in range(len(FUNNEL_STAGES))]
    styles = [{} if i == active else {"display": "none"} for i in range(len(FUNNEL_STAGES))]
    return classes + styles


@callback(
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
        rows,
        page_count,
        page_current,
        summary,
        industry_options,
        municipality_options,
    )


@callback(
    Output("screen-shortlist-list", "children"),
    Output("screen-selection-summary", "children"),
    Input("screen-results", "selected_rows"),
    State("screen-results", "data"),
)
def shortlist(selected_rows, data):
    selected_rows = selected_rows or []
    data = data or []

    items = [
        html.Div(_display_name(data[i].get("name", "")), className="shortlist-item")
        for i in selected_rows
        if i < len(data)
    ]
    if not items:
        items = [
            html.P(
                "Tick companies in the table to build a shortlist.",
                className="shortlist-empty",
            )
        ]
    return items, f"{len(selected_rows)} selected"


@callback(
    Output("screen-download", "data"),
    Input("screen-export-btn", "n_clicks"),
    State("screen-results", "selected_rows"),
    State("screen-results", "data"),
    prevent_initial_call=True,
)
def export(n_clicks, selected_rows, data):
    selected_rows = selected_rows or []
    if not selected_rows:
        return no_update

    fields = [c["id"] for c in COLUMNS]
    headers = [c["name"] for c in COLUMNS]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for i in selected_rows:
        if i < len(data):
            writer.writerow([data[i].get(f, "") for f in fields])

    return dcc.send_string(buffer.getvalue(), "shortlist.csv")
