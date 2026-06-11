from elasticsearch import Elasticsearch

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
