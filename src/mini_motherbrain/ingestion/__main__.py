import argparse
import logging

from mini_motherbrain.ingestion.adapters.brreg import BrregAdapter, BrregBulkAdapter
from mini_motherbrain.ingestion.pipeline import index_source

ADAPTERS = {"brreg": BrregAdapter, "brreg-bulk": BrregBulkAdapter}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Ingest company data into Elasticsearch.")
    parser.add_argument("source", choices=ADAPTERS, help="Data source adapter")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max records to index (default: all available; paginated brreg caps at 10000)",
    )
    args = parser.parse_args()

    count = index_source(ADAPTERS[args.source](), args.limit)
    print(f"Indexed {count} companies from {args.source}.")


if __name__ == "__main__":
    main()
