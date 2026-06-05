from datetime import date

from pydantic import BaseModel


class Company(BaseModel):
    """Normalised company record, source-agnostic."""

    org_number: str
    name: str
    country: str
    org_form: str | None = None
    industry_code: str | None = None
    industry_text: str | None = None
    employees: int | None = None
    municipality: str | None = None
    registered_at: date | None = None
    description: str | None = None
