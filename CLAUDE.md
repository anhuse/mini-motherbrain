# Mini-Motherbrain

## Vision
Search and analytics platform for Nordic companies, modelled on EQT's Motherbrain. Built to learn Elasticsearch and demo a PE deal-sourcing pattern.

## Phases
- **Phase 1 — Search layer (current scope):** Ingest Norwegian company data from Brønnøysund, normalise, bulk-index into Elasticsearch, Dash front end with free-text search, filters, and aggregations. Done when a user can load Norwegian data, search by free text, apply filters, and see aggregated counts — locally, end to end.
- **Phase 2 — RAG layer (do not start until Phase 1 ships):** LLM translates plain-language questions into Elasticsearch queries; vector embeddings on descriptions for hybrid search; orchestrate with LlamaIndex or LangChain.

## Data sources (Phase 1)
- Norway — Brønnøysundregistrene (data.brreg.no): open, no auth. Primary source.
- Finland — PRH/YTJ (avoindata.prh.fi): open registry.
- Denmark — CVR: public API.
- Sweden — Bolagsverket/SCB: partly paid; add later.
- Listed — Euronext Oslo Børs, Nasdaq Nordic: ticker, sector.

## Stack
- Elasticsearch locally via Docker Compose (Basic tier, free for local dev)
- Python with elasticsearch-py
- Dash (Plotly) front end — interdependent filter callbacks, not a linear script
- Ingestion as a separate idempotent module: fetch → normalise → bulk-index; one adapter per source

## Constraints
- British English, plain prose, no buzzwords
- Source adapters isolated and independently testable
- No secrets in the repo
- Sample a few thousand Norwegian companies before scaling
- Keep off work hardware

## Development workflow
- HTTP client: `httpx` throughout (not `requests`) — match `BrregAdapter`
- Monetary ES fields: use `long`, not `integer` — NOK revenues exceed int32 (~2.1bn)
- ES index migrations: `migrate()` reindexes old `_source` (safe when new fields are empty); use `swap_alias()` instead when a new field is populated during ingestion (migrate would clobber it)
- ES client default timeout is too short for full-register reindexes — the reindex runs to completion server-side, but the client drops before the alias swap; recover with `swap_alias()`
- Dash DataTable: inline `style_*` props outrank CSS — always style table cells inline
- Dash pages: importing a page module standalone raises `PageError` (register_page needs the app instantiated first) — not a bug; test via `from mini_motherbrain.app.dashboard import app` first
- `gh` CLI auth is expired and the PAT lacks PR-create scope — give the browser compare URL instead
- Docker Desktop: launch via PowerShell `Start-Process`, not Bash (Start-Process not in PATH there)
