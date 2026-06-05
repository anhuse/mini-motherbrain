from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

from mini_motherbrain.config import settings
from mini_motherbrain.es.client import get_client
from mini_motherbrain.es.mappings import COMPANIES_MAPPING
from mini_motherbrain.ingestion.adapters.base import SourceAdapter


def ensure_index(client: Elasticsearch) -> None:
    if not client.indices.exists(index=settings.companies_index):
        client.indices.create(index=settings.companies_index, **COMPANIES_MAPPING)


def index_source(adapter: SourceAdapter, limit: int, client: Elasticsearch | None = None) -> int:
    """Fetch, normalise, and bulk-index. Idempotent: re-running upserts by stable _id."""
    client = client or get_client()
    ensure_index(client)
    actions = (
        {
            "_index": settings.companies_index,
            "_id": f"{c.country}-{c.org_number}",
            "_source": c.model_dump(mode="json"),
        }
        for c in adapter.fetch(limit)
    )
    success, _ = bulk(client, actions)
    return success
