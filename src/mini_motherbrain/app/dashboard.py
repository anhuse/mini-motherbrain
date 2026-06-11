from math import ceil

import plotly.graph_objects as go
from dash import Dash, Input, Output, callback_context, dash_table, dcc, html

from mini_motherbrain.search.models import MAX_RESULT_WINDOW, SearchRequest
from mini_motherbrain.search.service import search

app = Dash(__name__)
app.title = "Mini-Motherbrain"

PAGE_SIZE = 20
MAX_PAGES = MAX_RESULT_WINDOW // PAGE_SIZE  # ES from + size window cap

# DataTable column id == SortField value, so sort_by maps straight through.
COLUMNS = [
    {"name": "Name", "id": "name"},
    {"name": "Industry", "id": "industry_text"},
    {"name": "Municipality", "id": "municipality"},
    {"name": "Employees", "id": "employees", "type": "numeric"},
    {"name": "Founded", "id": "founded_at"},
]

app.layout = html.Div(
    [
        html.H1("Mini-Motherbrain"),
        dcc.Input(id="query", type="text", placeholder="Search companies…", debounce=True),
        dcc.Dropdown(id="industry", placeholder="Filter by industry", clearable=True),
        dcc.Dropdown(id="municipality", placeholder="Filter by municipality", clearable=True),
        dcc.Checklist(
            id="active-only",
            options=[{"label": " Active companies only", "value": "yes"}],
            value=[],
        ),
        html.Div(id="summary"),
        dash_table.DataTable(
            id="results-table",
            columns=COLUMNS,
            page_action="custom",
            page_current=0,
            page_size=PAGE_SIZE,
            sort_action="custom",
            sort_mode="single",
            sort_by=[],
        ),
        html.Div(
            [dcc.Graph(id="industry-chart"), dcc.Graph(id="founded-chart")],
            style={"display": "flex", "flexWrap": "wrap"},
        ),
    ]
)


@app.callback(
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
    """Results, facet options, and charts are recomputed together so everything
    stays consistent with the current query."""
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

    rows = [
        c.model_dump(
            mode="json",
            include={"name", "industry_text", "municipality", "employees", "founded_at"},
        )
        for c in result.companies
    ]
    page_count = min(ceil(result.total / PAGE_SIZE), MAX_PAGES) if result.total else 1

    summary = f"{result.total:,} companies"
    if result.total > MAX_RESULT_WINDOW:
        summary += f" (first {MAX_RESULT_WINDOW:,} browsable)"

    def options(facet: str) -> list[dict]:
        return [{"label": f"{b.key} ({b.count})", "value": b.key} for b in result.facets[facet]]

    return (
        rows,
        page_count,
        page_current,
        summary,
        options("industries"),
        options("municipalities"),
        _industry_figure(result),
        _founded_figure(result),
    )


def _industry_figure(result) -> go.Figure:
    buckets = list(reversed(result.facets["industries_text"]))  # largest at top
    fig = go.Figure(
        go.Bar(x=[b.count for b in buckets], y=[b.key for b in buckets], orientation="h")
    )
    fig.update_layout(title="Top industries", margin={"l": 0, "r": 0, "t": 40, "b": 0})
    return fig


def _founded_figure(result) -> go.Figure:
    buckets = result.facets["founded_years"]
    fig = go.Figure(go.Bar(x=[b.key for b in buckets], y=[b.count for b in buckets]))
    fig.update_layout(title="Companies by founding year", margin={"r": 0, "t": 40, "b": 0})
    return fig


def main() -> None:
    app.run(debug=True)


if __name__ == "__main__":
    main()
