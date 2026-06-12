import logging

from elasticsearch import Elasticsearch
from elasticsearch.helpers import streaming_bulk

from mini_motherbrain.es.client import get_client
from mini_motherbrain.es.indices import ensure_index
from mini_motherbrain.ingestion.adapters.base import SourceAdapter

logger = logging.getLogger(__name__)


def index_source(
    adapter: SourceAdapter,
    limit: int | None = None,
    client: Elasticsearch | None = None,
    chunk_size: int = 1000,
) -> int:
    """Fetch, normalise, and bulk-index. Idempotent: re-running upserts by stable _id.

    Writes go to the physical versioned index, not the alias — ES rejects
    writes through an alias while a migration has it spanning two indices.
    Refresh is disabled during the load and restored afterwards, which is a
    meaningful win at full-register scale and harmless for small samples.
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

    client.indices.put_settings(index=target, settings={"refresh_interval": "-1"})
    success = 0
    try:
        for ok, _ in streaming_bulk(client, actions, chunk_size=chunk_size, request_timeout=120):
            success += int(ok)
            if success % 10_000 == 0:
                logger.info("indexed %d documents", success)
    finally:
        client.indices.put_settings(index=target, settings={"refresh_interval": "1s"})
        client.indices.refresh(index=target)
    logger.info("done: indexed %d documents into %s", success, target)
    return success
