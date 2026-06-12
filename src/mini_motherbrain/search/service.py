from elasticsearch import Elasticsearch
from pydantic import BaseModel

from mini_motherbrain.config import settings
from mini_motherbrain.es.client import get_client
from mini_motherbrain.models import Company
from mini_motherbrain.search.models import FacetBucket, SearchRequest, SearchResult
from mini_motherbrain.search.queries import AGGREGATIONS, build_query, build_sort


def search(request: SearchRequest, client: Elasticsearch | None = None) -> SearchResult:
    """Execute a SearchRequest against the companies alias and return typed results."""
    client = client or get_client()
    resp = client.search(
        index=settings.companies_index,
        query=build_query(request),
        size=request.size,
        from_=request.offset,
        sort=build_sort(request) or None,
        aggs=AGGREGATIONS,
        # Report the true match count, not ES's default 10k cap — the summary
        # and "first N browsable" note depend on it at full-register scale.
        track_total_hits=True,
    )
    return SearchResult(
        total=resp["hits"]["total"]["value"],
        companies=[Company.model_validate(h["_source"]) for h in resp["hits"]["hits"]],
        facets={
            # date_histogram buckets key on epoch millis but carry a formatted
            # key_as_string ("1972"); prefer it so the histogram reads cleanly.
            name: [
                FacetBucket(key=str(b.get("key_as_string", b["key"])), count=b["doc_count"])
                for b in agg["buckets"]
            ]
            for name, agg in resp["aggregations"].items()
        },
    )


def get_company(org_number: str, client: Elasticsearch | None = None) -> Company | None:
    """Fetch a single company by organisation number, or None if absent."""
    client = client or get_client()
    resp = client.search(
        index=settings.companies_index,
        query={"term": {"org_number": org_number}},
        size=1,
    )
    hits = resp["hits"]["hits"]
    return Company.model_validate(hits[0]["_source"]) if hits else None


class Overview(BaseModel):
    """Register-wide aggregates for the landing page."""

    total: int
    active: int
    municipality_count: int
    industry_count: int
    municipalities: list[FacetBucket]  # every municipality, for the map


def overview(client: Elasticsearch | None = None) -> Overview:
    """One register-wide aggregation pass: headline counts plus a full
    per-municipality breakdown (Norway has ~360 municipalities, so a terms
    aggregation sized at 500 is exhaustive, not a top-N sample)."""
    client = client or get_client()
    resp = client.search(
        index=settings.companies_index,
        size=0,
        track_total_hits=True,
        aggs={
            "active": {
                "filter": {
                    "bool": {
                        "filter": [
                            {"term": {"bankrupt": False}},
                            {"term": {"under_liquidation": False}},
                            {"term": {"under_forced_liquidation": False}},
                        ]
                    }
                }
            },
            "municipality_count": {"cardinality": {"field": "municipality"}},
            "industry_count": {"cardinality": {"field": "industry_code"}},
            "municipalities": {"terms": {"field": "municipality", "size": 500}},
        },
    )
    aggs = resp["aggregations"]
    return Overview(
        total=resp["hits"]["total"]["value"],
        active=aggs["active"]["doc_count"],
        municipality_count=aggs["municipality_count"]["value"],
        industry_count=aggs["industry_count"]["value"],
        municipalities=[
            FacetBucket(key=str(b["key"]), count=b["doc_count"])
            for b in aggs["municipalities"]["buckets"]
        ],
    )
