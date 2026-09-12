import argparse
import logging

from mini_motherbrain.ingestion.adapters.brreg import BrregAdapter, BrregBulkAdapter
from mini_motherbrain.ingestion.adapters.regnskap import RegnskapAdapter
from mini_motherbrain.ingestion.pipeline import enrich_index, index_source

# Source adapters build whole company documents; enrichers merge extra fields
# onto documents that already exist (a bulk `update` path, not replace).
ADAPTERS = {"brreg": BrregAdapter, "brreg-bulk": BrregBulkAdapter}
ENRICHERS = {"regnskap": RegnskapAdapter}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Ingest company data into Elasticsearch.")
    parser.add_argument("source", choices=list(ADAPTERS) + list(ENRICHERS), help="Adapter name")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max records to index (default: all available; paginated brreg caps at 10000)",
    )
    args = parser.parse_args()

    if args.source in ENRICHERS:
        count = enrich_index(ENRICHERS[args.source](), args.limit)
        print(f"Enriched {count} companies from {args.source}.")
    else:
        count = index_source(ADAPTERS[args.source](), args.limit)
        print(f"Indexed {count} companies from {args.source}.")


if __name__ == "__main__":
    main()
