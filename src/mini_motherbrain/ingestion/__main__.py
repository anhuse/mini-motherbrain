import argparse

from mini_motherbrain.ingestion.adapters.brreg import BrregAdapter
from mini_motherbrain.ingestion.pipeline import index_source

ADAPTERS = {"brreg": BrregAdapter}


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest company data into Elasticsearch.")
    parser.add_argument("source", choices=ADAPTERS, help="Data source adapter")
    parser.add_argument("--limit", type=int, default=2000, help="Max records to fetch")
    args = parser.parse_args()

    count = index_source(ADAPTERS[args.source](), args.limit)
    print(f"Indexed {count} companies from {args.source}.")


if __name__ == "__main__":
    main()
