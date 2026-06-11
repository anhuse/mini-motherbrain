from elasticsearch import Elasticsearch

from mini_motherbrain.config import settings
from mini_motherbrain.es.client import get_client
from mini_motherbrain.models import Company
from mini_motherbrain.search.models import FacetBucket, SearchRequest, SearchResult
from mini_motherbrain.search.queries import AGGREGATIONS, build_query


def search(request: SearchRequest, client: Elasticsearch | None = None) -> SearchResult:
    """Execute a SearchRequest against the companies alias and return typed results."""
    client = client or get_client()
    resp = client.search(
        index=settings.companies_index,
        query=build_query(request),
        size=request.size,
        aggs=AGGREGATIONS,
    )
    return SearchResult(
        total=resp["hits"]["total"]["value"],
        companies=[Company.model_validate(h["_source"]) for h in resp["hits"]["hits"]],
        facets={
            name: [FacetBucket(key=str(b["key"]), count=b["doc_count"]) for b in agg["buckets"]]
            for name, agg in resp["aggregations"].items()
        },
    )
