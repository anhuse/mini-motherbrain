"""Company profile: the full indexed record for one organisation, reached by
clicking a row on the companies page."""

import dash
from dash import dcc, html

from mini_motherbrain.models import Company
from mini_motherbrain.search.service import get_company

dash.register_page(
    __name__,
    path_template="/company/<org_number>",
    name="Company",
    title="Company — Mini-Motherbrain",
)


def layout(org_number: str | None = None, **_) -> html.Div:
    company = get_company(org_number) if org_number else None
    if company is None:
        return html.Div(
            [
                _back_link(),
                html.H1("No such company", className="page-title"),
                html.P(
                    f"Nothing in the index for organisation number {org_number}.",
                    className="result-count",
                ),
            ],
            className="page",
        )
    return html.Div(
        [
            _back_link(),
            html.Div(
                [
                    html.Div(_chips(company), className="chip-row"),
                    html.H1(company.name, className="profile-title"),
                    html.P(
                        f"Org. nr {_format_orgnr(company.org_number)}"
                        + (f" · {company.municipality.title()}" if company.municipality else ""),
                        className="profile-sub",
                    ),
                ],
                className="profile-head",
            ),
            html.Div(
                [
                    _fact("Industry", _industry(company)),
                    _fact("Municipality", (company.municipality or "—").title()),
                    _fact("Employees", f"{company.employees:,}" if company.employees else "—"),
                    _fact("Founded", str(company.founded_at or "—")),
                    _fact("Registered", str(company.registered_at or "—")),
                    _fact(
                        "Last accounts",
                        str(company.last_accounts_year) if company.last_accounts_year else "—",
                    ),
                    _fact("VAT registered", "Yes" if company.vat_registered else "No"),
                    _fact("Part of group", "Yes" if company.in_group else "No"),
                ],
                className="fact-grid card",
            ),
            html.Div(
                [
                    html.H3("Registered activity", className="card-title"),
                    html.P(company.description, className="activity-text"),
                ],
                className="card activity-card",
            )
            if company.description
            else None,
        ],
        className="page",
    )


def _back_link() -> dcc.Link:
    return dcc.Link("← All companies", href="/companies", className="back-link")


def _chips(company: Company) -> list[html.Span]:
    chips = [html.Span(company.org_form or "—", className="chip chip--form")]
    if company.bankrupt:
        chips.append(html.Span("Bankrupt", className="chip chip--negative"))
    if company.under_liquidation:
        chips.append(html.Span("Under liquidation", className="chip chip--negative"))
    if company.under_forced_liquidation:
        chips.append(html.Span("Under forced liquidation", className="chip chip--negative"))
    if len(chips) == 1:
        chips.append(html.Span("Active", className="chip chip--active"))
    return chips


def _fact(label: str, value: str) -> html.Div:
    return html.Div(
        [html.Span(label, className="fact-label"), html.Span(value, className="fact-value")],
        className="fact",
    )


def _industry(company: Company) -> str:
    if not company.industry_text:
        return "—"
    code = f" ({company.industry_code})" if company.industry_code else ""
    return f"{company.industry_text}{code}"


def _format_orgnr(orgnr: str) -> str:
    # Norwegian convention groups the nine digits in threes: 923 609 016.
    return f"{orgnr[:3]} {orgnr[3:6]} {orgnr[6:]}" if len(orgnr) == 9 else orgnr
