from pydantic import BaseModel, Field

from mini_motherbrain.models import Company


class SearchRequest(BaseModel):
    """Structured search input. Filled from dashboard widgets today; the
    Phase 2 LLM translator will produce the same shape from plain language."""

    text: str | None = None
    industry_codes: list[str] = Field(default_factory=list)
    org_forms: list[str] = Field(default_factory=list)
    municipalities: list[str] = Field(default_factory=list)
    min_employees: int | None = None
    max_employees: int | None = None
    exclude_inactive: bool = False
    size: int = 20


class FacetBucket(BaseModel):
    key: str
    count: int


class SearchResult(BaseModel):
    total: int
    companies: list[Company]
    facets: dict[str, list[FacetBucket]]
