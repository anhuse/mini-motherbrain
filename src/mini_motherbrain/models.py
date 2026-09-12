from datetime import date

from pydantic import BaseModel, Field


class Company(BaseModel):
    """Normalised company record, source-agnostic. Produced by ingestion
    adapters and returned by the search layer."""

    org_number: str
    name: str
    country: str
    org_form: str | None = None
    industry_code: str | None = None  # primary NACE code (display, primary facet)
    industry_text: str | None = None  # primary NACE label (display, facet)
    # All NACE codes (primary + secondary + tertiary), for industry filtering.
    industry_codes: list[str] = Field(default_factory=list)
    # All NACE labels joined, for free-text matching across every line of business.
    industry_text_all: str | None = None
    employees: int | None = None
    municipality: str | None = None
    registered_at: date | None = None
    founded_at: date | None = None
    last_accounts_year: int | None = None
    bankrupt: bool = False
    under_liquidation: bool = False
    under_forced_liquidation: bool = False
    vat_registered: bool = False
    in_group: bool = False
    description: str | None = None
    purpose: str | None = None  # articles-of-association purpose clause

    # Financials from the Regnskapsregisteret (annual-accounts) enrichment.
    # Latest filed year only (the open API tier exposes no history). Monetary
    # fields are converted to NOK so a single band is comparable across filers;
    # accounts_currency keeps the originally reported currency for transparency.
    revenue: int | None = None  # sumDriftsinntekter → NOK
    operating_profit: int | None = None  # driftsresultat (≈ EBIT) → NOK
    operating_margin: float | None = None  # operating_profit / revenue
    net_result: int | None = None  # aarsresultat → NOK
    total_assets: int | None = None  # sumEiendeler → NOK
    equity: int | None = None  # sumEgenkapital → NOK
    total_debt: int | None = None  # sumGjeld → NOK
    accounts_year: int | None = None  # year from regnskapsperiode.tilDato
    accounts_currency: str | None = None  # originally reported currency (pre-conversion)
