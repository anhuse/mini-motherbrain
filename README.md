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
python -m mini_motherbrain.ingestion brreg --limit 2000

# 5. Run the dashboard
python -m mini_motherbrain.app.dashboard
```

## Layout

```
src/mini_motherbrain/
├── config.py              # settings (env-driven)
├── es/                    # Elasticsearch client + index mappings
├── ingestion/             # fetch → normalise → bulk-index
│   └── adapters/          # one isolated adapter per source (brreg = Norway)
└── app/                   # Dash front end
tests/                     # adapter normalisation tests (no network)
```

## Adding a source

Subclass `SourceAdapter` in `ingestion/adapters/`, implement `fetch()` to yield
normalised `Company` records, and register it in `ingestion/__main__.py`.
