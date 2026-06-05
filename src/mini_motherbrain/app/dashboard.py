from dash import Dash, Input, Output, dcc, html

from mini_motherbrain.config import settings
from mini_motherbrain.es.client import get_client

client = get_client()
app = Dash(__name__)
app.title = "Mini-Motherbrain"

app.layout = html.Div(
    [
        html.H1("Mini-Motherbrain"),
        dcc.Input(id="query", type="text", placeholder="Search companies…", debounce=True),
        dcc.Dropdown(id="industry", placeholder="Filter by industry", clearable=True),
        html.Div(id="summary"),
        html.Ul(id="results"),
    ]
)


def _build_query(query: str | None, industry: str | None) -> dict:
    must: list[dict] = [{"match": {"name": query}}] if query else [{"match_all": {}}]
    filt = [{"term": {"industry_code": industry}}] if industry else []
    return {"bool": {"must": must, "filter": filt}}


@app.callback(
    Output("results", "children"),
    Output("summary", "children"),
    Output("industry", "options"),
    Input("query", "value"),
    Input("industry", "value"),
)
def search(query: str | None, industry: str | None):
    """Search results, total count, and industry facet are recomputed together so the
    available filter options stay consistent with the current query."""
    resp = client.search(
        index=settings.companies_index,
        query=_build_query(query, industry),
        size=20,
        aggs={"industries": {"terms": {"field": "industry_code", "size": 20}}},
    )
    hits = resp["hits"]["hits"]
    total = resp["hits"]["total"]["value"]
    options = [
        {"label": f"{b['key']} ({b['doc_count']})", "value": b["key"]}
        for b in resp["aggregations"]["industries"]["buckets"]
    ]
    results = [html.Li(h["_source"]["name"]) for h in hits]
    return results, f"{total} companies", options


if __name__ == "__main__":
    app.run(debug=True)
