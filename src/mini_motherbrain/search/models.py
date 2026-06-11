from typing import Literal

from pydantic import BaseModel, Field, model_validator

from mini_motherbrain.models import Company

# Closed vocabulary of sortable fields. Keeping it a Literal means the Phase 2
# LLM translator gets a validated set of names and no ES field names leak out
# of the search package.
SortField = Literal["name", "industry_text", "municipality", "employees", "founded_at"]

# ES rejects from + size beyond this window; we cap requests rather than fail.
MAX_RESULT_WINDOW = 10_000


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
    offset: int = Field(default=0, ge=0)
    sort_field: SortField | None = None  # None = relevance order
    sort_desc: bool = False

    @model_validator(mode="after")
    def _cap_window(self) -> "SearchRequest":
        if self.offset + self.size > MAX_RESULT_WINDOW:
            raise ValueError(
                f"offset + size ({self.offset} + {self.size}) exceeds the "
                f"{MAX_RESULT_WINDOW}-document result window"
            )
        return self


class FacetBucket(BaseModel):
    key: str
    count: int


class SearchResult(BaseModel):
    total: int
    companies: list[Company]
    facets: dict[str, list[FacetBucket]]
