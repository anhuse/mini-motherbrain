import logging
from collections.abc import Iterator

from elasticsearch import Elasticsearch
from elasticsearch.helpers import scan, streaming_bulk

from mini_motherbrain.es.client import get_client
from mini_motherbrain.es.indices import ensure_index
from mini_motherbrain.ingestion.adapters.base import EnrichmentAdapter, SourceAdapter

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


def scan_org_numbers(client: Elasticsearch, target: str) -> Iterator[str]:
    """Yield org numbers of companies that have filed accounts. We only enrich
    these — calling the accounts API for companies with no filings is wasted
    requests against a per-org-number service."""
    for hit in scan(
        client,
        index=target,
        query={"query": {"exists": {"field": "last_accounts_year"}}, "_source": ["org_number"]},
    ):
        yield hit["_source"]["org_number"]


def enrich_index(
    adapter: EnrichmentAdapter,
    limit: int | None = None,
    client: Elasticsearch | None = None,
    chunk_size: int = 1000,
) -> int:
    """Merge partial fields from an enrichment source onto existing documents.

    Mirrors index_source (refresh toggling, progress logging) but emits bulk
    `update` ops instead of full-document index ops, so it never replaces the
    company documents the source adapters built — it only adds fields.
    """
    client = client or get_client()
    target = ensure_index(client)
    actions = (
        {
            "_op_type": "update",
            "_index": target,
            "_id": f"{adapter.country}-{org}",
            "doc": fields,
        }
        for org, fields in adapter.fetch(scan_org_numbers(client, target), limit)
    )

    client.indices.put_settings(index=target, settings={"refresh_interval": "-1"})
    success = 0
    try:
        for ok, _ in streaming_bulk(client, actions, chunk_size=chunk_size, request_timeout=120):
            success += int(ok)
            if success % 10_000 == 0:
                logger.info("enriched %d documents", success)
    finally:
        client.indices.put_settings(index=target, settings={"refresh_interval": "1s"})
        client.indices.refresh(index=target)
    logger.info("done: enriched %d documents in %s", success, target)
    return success
