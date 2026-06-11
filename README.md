# Mini-Motherbrain

Search and analytics platform for Nordic companies, modelled on EQT's Motherbrain.
See [CLAUDE.md](CLAUDE.md) for vision, phases, and constraints.

## Quickstart

```bash
# 1. Configure
cp .env.example .env            # adjust MMB_ES_PASSWORD if needed

# 2. Start Elasticsearch
docker compose up -d

# 3. Install
python -m venv .venv && . .venv/Scripts/activate   # PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# 4. Ingest a sample of Norwegian companies
mmb-ingest brreg --limit 2000

# 5. Run the dashboard
mmb-dashboard
```

## Layout

```
src/mini_motherbrain/
├── config.py              # settings (env-driven)
├── models.py              # Company — the shared, source-agnostic domain model
├── es/                    # client, mappings, versioned indices behind an alias
├── ingestion/             # fetch → normalise → bulk-index
│   └── adapters/          # one isolated adapter per source (brreg = Norway)
├── search/                # SearchRequest → ES query DSL → typed results
└── app/                   # Dash front end (widgets only, no query DSL)
tests/                     # adapter, pipeline, and query-builder tests (no network)
```

## Index migrations

Searches go through the `companies` alias; documents live in `companies-v1`.
When the mapping changes, bump `INDEX_VERSION` in `es/indices.py` and call
`migrate()` — it reindexes into the new version and swaps the alias.

## Search layer

`search/` is the seam Phase 2 plugs into: the dashboard fills a `SearchRequest`
from widgets today, and the future LLM translator will produce the same shape
from plain-language questions. Query DSL lives only in `search/queries.py`.

## Adding a source

Subclass `SourceAdapter` in `ingestion/adapters/`, implement `fetch()` to yield
normalised `Company` records, and register it in `ingestion/__main__.py`.

## Future improvements

- More Nordic sources (per CLAUDE.md "Data sources"): Finland (PRH/YTJ),
  Denmark (CVR), Sweden (Bolagsverket/SCB), and listed-company tickers from
  Euronext Oslo Børs / Nasdaq Nordic. 2000 NO companies (AS/ASA via Brreg) is
  the current sample; revisit the limit once more sources are added.
