"""Landing page: punchline, register-wide numbers, and a municipality map of
the whole dataset. The search bar hands off to the companies page."""

from urllib.parse import quote

import dash
from dash import Input, Output, State, callback, dcc, html

from mini_motherbrain.app.figures import GRAPH_CONFIG, norway_map_figure
from mini_motherbrain.search.service import overview

dash.register_page(__name__, path="/", name="Home", title="Mini-Motherbrain")


def _stat(value: str, label: str) -> html.Div:
    return html.Div(
        [html.Span(value, className="stat-value"), html.Span(label, className="stat-label")],
        className="stat",
    )


def layout(**_) -> html.Div:
    data = overview()
    return html.Div(
        [
            dcc.Location(id="home-redirect", refresh=True),
            html.Div(
                [
                    html.P("Norway · Full register", className="overline"),
                    html.H1(
                        [
                            f"{data.total:,}",
                            html.Br(),
                            "Norwegian companies.",
                            html.Br(),
                            html.Em("One search away."),
                        ],
                        className="hero-title",
                    ),
                    html.P(
                        "Free-text search, filters and live aggregations over every "
                        "limited company in the Brønnøysund register, indexed locally "
                        "in Elasticsearch.",
                        className="hero-lede",
                    ),
                    html.Div(
                        [
                            dcc.Input(
                                id="home-search",
                                type="text",
                                placeholder="Try “laks”, “fornybar energi”, or a company name…",
                                n_submit=0,
                                className="hero-input",
                            ),
                            html.Button(
                                "Search", id="home-go", n_clicks=0, className="btn-primary"
                            ),
                        ],
                        className="hero-searchbar",
                    ),
                    html.Div(
                        [
                            _stat(f"{data.total:,}", "companies indexed"),
                            _stat(f"{data.active / data.total:.0%}", "in active operation"),
                            _stat(f"{data.municipality_count}", "municipalities"),
                            _stat(f"{data.industry_count:,}", "industry codes"),
                        ],
                        className="hero-stats",
                    ),
                ],
                className="hero-copy",
            ),
            html.Div(
                [
                    dcc.Graph(
                        figure=norway_map_figure(data.municipalities),
                        config=GRAPH_CONFIG,
                        className="hero-map",
                    ),
                    html.P("Registered companies per municipality", className="map-caption"),
                ],
                className="hero-map-wrap",
            ),
        ],
        className="hero",
    )


@callback(
    Output("home-redirect", "href"),
    Input("home-go", "n_clicks"),
    Input("home-search", "n_submit"),
    State("home-search", "value"),
    prevent_initial_call=True,
)
def go_to_search(_clicks, _submits, value):
    query = (value or "").strip()
    return f"/companies?q={quote(query)}" if query else "/companies"
