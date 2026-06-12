"""App shell: sidebar navigation wrapping Dash pages (see pages/). Pages own
their layouts and callbacks; this module owns the frame around them."""

import dash
from dash import Dash, Input, Output, dcc, html

import mini_motherbrain.app.figures  # noqa: F401  — registers the Plotly template

FONTS = (
    "https://fonts.googleapis.com/css2"
    "?family=Archivo:wght@400;500;600;700"
    "&family=Fraunces:ital,opsz,wght@0,9..144,400..600;1,9..144,400..600"
    "&display=swap"
)

app = Dash(
    __name__,
    use_pages=True,
    external_stylesheets=[FONTS],
    title="Mini-Motherbrain",
    suppress_callback_exceptions=True,
)

sidebar = html.Aside(
    [
        dcc.Link(
            [
                html.Span(className="brand-mark"),
                html.Span(
                    [html.Span("Mini", className="brand-mini"), "Motherbrain"],
                    className="brand-name",
                ),
                html.Span("Nordic company intelligence", className="brand-tag"),
            ],
            href="/",
            className="brand",
        ),
        html.Nav(
            [
                html.Span("Explore", className="nav-section"),
                dcc.Link("Home", href="/", id="nav-home", className="nav-link"),
                dcc.Link("Companies", href="/companies", id="nav-companies", className="nav-link"),
                html.Span("In the works", className="nav-section"),
                html.Span(
                    ["Markets", html.Span("soon", className="nav-soon")],
                    className="nav-link nav-link--disabled",
                ),
                html.Span(
                    ["Ask", html.Span("phase 2", className="nav-soon")],
                    className="nav-link nav-link--disabled",
                ),
            ],
            className="nav",
        ),
        html.Div(
            [
                html.Span("Norway · Brønnøysundregistrene", className="meta-line"),
                html.Span("Local Elasticsearch", className="meta-line"),
            ],
            className="sidebar-meta",
        ),
    ],
    className="sidebar",
)

app.layout = html.Div(
    [dcc.Location(id="url"), sidebar, html.Main(dash.page_container, className="content")],
    className="shell",
)


@app.callback(
    Output("nav-home", "className"),
    Output("nav-companies", "className"),
    Input("url", "pathname"),
)
def mark_active(pathname: str):
    def cls(active: bool) -> str:
        return "nav-link nav-link--active" if active else "nav-link"

    # /company/<orgnr> is a drill-down from the companies page, so it keeps
    # that section highlighted.
    return cls(pathname == "/"), cls(bool(pathname) and pathname.startswith("/compan"))


def main() -> None:
    app.run(debug=True)


if __name__ == "__main__":
    main()
