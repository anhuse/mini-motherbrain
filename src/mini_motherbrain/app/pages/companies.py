"""Companies page: the working search tool. One callback recomputes results,
facet options and charts together so everything stays consistent with the
current query."""

from math import ceil

import dash
from dash import Input, Output, callback, callback_context, dash_table, dcc, html
from dash.dash_table.Format import Format, Group

from mini_motherbrain.app.figures import GRAPH_CONFIG, founded_figure, industry_figure
from mini_motherbrain.search.models import MAX_RESULT_WINDOW, SearchRequest
from mini_motherbrain.search.service import search

dash.register_page(
    __name__, path="/companies", name="Companies", title="Companies — Mini-Motherbrain"
)

PAGE_SIZE = 20
MAX_PAGES = MAX_RESULT_WINDOW // PAGE_SIZE  # ES from + size window cap

# DataTable column id == SortField value, so sort_by maps straight through.
# The name renders as a markdown link into the company profile page.
COLUMNS = [
    {"name": "Name", "id": "name", "presentation": "markdown"},
    {"name": "Industry", "id": "industry_text"},
    {"name": "Municipality", "id": "municipality"},
    {"name": "Employees", "id": "employees", "type": "numeric", "format": Format(group=Group.yes)},
    {"name": "Founded", "id": "founded_at"},
]


def layout(q: str | None = None, **_) -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.H1("Companies", className="page-title"),
                    html.P(id="summary", className="result-count"),
                ],
                className="page-head",
            ),
            html.Div(
                [
                    dcc.Input(
                        id="query",
                        type="text",
                        value=q,
                        placeholder="Search by name, industry or activity…",
                        debounce=True,
                        className="toolbar-search",
                    ),
                    dcc.Dropdown(
                        id="industry",
                        placeholder="Industry",
                        clearable=True,
                        className="toolbar-filter",
                    ),
                    dcc.Dropdown(
                        id="municipality",
                        placeholder="Municipality",
                        clearable=True,
                        className="toolbar-filter",
                    ),
                    dcc.Checklist(
                        id="active-only",
                        options=[{"label": "Active only", "value": "yes"}],
                        value=[],
                        className="toolbar-toggle",
                    ),
                ],
                className="toolbar",
            ),
            html.Div(
                dash_table.DataTable(
                    id="results-table",
                    columns=COLUMNS,
                    markdown_options={"link_target": "_self"},
                    page_action="custom",
                    page_current=0,
                    page_size=PAGE_SIZE,
                    sort_action="custom",
                    sort_mode="single",
                    sort_by=[],
                    cell_selectable=False,
                    style_as_list_view=True,
                    # Inline styles, because the DataTable's own defaults
                    # (monospace, centred headers) outrank stylesheet rules.
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
                        {"if": {"column_id": "founded_at"}, "width": "120px"},
                        {"if": {"column_id": "municipality"}, "width": "180px"},
                    ],
                ),
                className="card table-card",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.H3("Top industries", className="card-title"),
                            dcc.Graph(id="industry-chart", config=GRAPH_CONFIG),
                        ],
                        className="card chart-card",
                    ),
                    html.Div(
                        [
                            html.H3("Companies by founding year", className="card-title"),
                            dcc.Graph(id="founded-chart", config=GRAPH_CONFIG),
                        ],
                        className="card chart-card",
                    ),
                ],
                className="chart-row",
            ),
        ],
        className="page",
    )


@callback(
    Output("results-table", "data"),
    Output("results-table", "page_count"),
    Output("results-table", "page_current"),
    Output("summary", "children"),
    Output("industry", "options"),
    Output("municipality", "options"),
    Output("industry-chart", "figure"),
    Output("founded-chart", "figure"),
    Input("query", "value"),
    Input("industry", "value"),
    Input("municipality", "value"),
    Input("active-only", "value"),
    Input("results-table", "page_current"),
    Input("results-table", "sort_by"),
)
def update(query, industry, municipality, active_only, page_current, sort_by):
    # Any change other than paging resets to the first page — otherwise a filter
    # change could leave us on a page past the new result set.
    if callback_context.triggered_id != "results-table":
        page_current = 0

    sort_field = sort_by[0]["column_id"] if sort_by else None
    sort_desc = bool(sort_by) and sort_by[0]["direction"] == "desc"

    request = SearchRequest(
        text=query or None,
        industry_codes=[industry] if industry else [],
        municipalities=[municipality] if municipality else [],
        exclude_inactive=bool(active_only),
        size=PAGE_SIZE,
        offset=page_current * PAGE_SIZE,
        sort_field=sort_field,
        sort_desc=sort_desc,
    )
    result = search(request)

    rows = []
    for c in result.companies:
        row = c.model_dump(
            mode="json",
            include={"industry_text", "municipality", "employees", "founded_at"},
        )
        # Square brackets in a company name would break the markdown link text.
        safe_name = c.name.replace("[", "(").replace("]", ")")
        row["name"] = f"[{safe_name}](/company/{c.org_number})"
        row["municipality"] = (c.municipality or "").title()
        rows.append(row)
    page_count = min(ceil(result.total / PAGE_SIZE), MAX_PAGES) if result.total else 1

    summary = f"{result.total:,} companies"
    if result.total > MAX_RESULT_WINDOW:
        summary += f" · first {MAX_RESULT_WINDOW:,} browsable"

    def options(facet: str) -> list[dict]:
        return [
            {"label": f"{b.key.title()} ({b.count:,})", "value": b.key}
            for b in result.facets[facet]
        ]

    return (
        rows,
        page_count,
        page_current,
        summary,
        [{"label": f"{b.key} ({b.count:,})", "value": b.key} for b in result.facets["industries"]],
        options("municipalities"),
        industry_figure(result.facets["industries_text"]),
        founded_figure(result.facets["founded_years"]),
    )
