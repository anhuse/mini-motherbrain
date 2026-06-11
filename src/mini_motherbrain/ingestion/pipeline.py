from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

from mini_motherbrain.es.client import get_client
from mini_motherbrain.es.indices import ensure_index
from mini_motherbrain.ingestion.adapters.base import SourceAdapter


def index_source(adapter: SourceAdapter, limit: int, client: Elasticsearch | None = None) -> int:
    """Fetch, normalise, and bulk-index. Idempotent: re-running upserts by stable _id.

    Writes go to the physical versioned index, not the alias — ES rejects
    writes through an alias while a migration has it spanning two indices.
    """
    client = client or get_client()
    target = ensure_index(client)
    actions = (
        {
            "_index": target,
            "_id": f"{c.country}-{c.org_number}",
            "_source": c.model_dump(mode="json"),
        }
        for c in adapter.fetch(limit)
    )
    success, _ = bulk(client, actions)
    return success
