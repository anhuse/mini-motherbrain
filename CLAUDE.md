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
