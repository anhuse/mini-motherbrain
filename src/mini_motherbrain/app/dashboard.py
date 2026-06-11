from dash import Dash, Input, Output, dcc, html

from mini_motherbrain.search.models import SearchRequest
from mini_motherbrain.search.service import search

app = Dash(__name__)
app.title = "Mini-Motherbrain"

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
        html.Ul(id="results"),
    ]
)


@app.callback(
    Output("results", "children"),
    Output("summary", "children"),
    Output("industry", "options"),
    Output("municipality", "options"),
    Input("query", "value"),
    Input("industry", "value"),
    Input("municipality", "value"),
    Input("active-only", "value"),
)
def update(query, industry, municipality, active_only):
    """Results and facet options are recomputed together so the available
    filter options stay consistent with the current query."""
    request = SearchRequest(
        text=query or None,
        industry_codes=[industry] if industry else [],
        municipalities=[municipality] if municipality else [],
        exclude_inactive=bool(active_only),
    )
    result = search(request)

    rows = [
        html.Li(
            f"{c.name} — {c.municipality or '—'}"
            + (f" · {c.employees} employees" if c.employees is not None else "")
        )
        for c in result.companies
    ]

    def options(facet: str) -> list[dict]:
        return [{"label": f"{b.key} ({b.count})", "value": b.key} for b in result.facets[facet]]

    return rows, f"{result.total} companies", options("industries"), options("municipalities")


def main() -> None:
    app.run(debug=True)


if __name__ == "__main__":
    main()
