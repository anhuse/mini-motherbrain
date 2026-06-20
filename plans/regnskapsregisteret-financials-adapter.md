# Plan — Regnskapsregisteret financials adapter

> Status: **not started** — parked for a future session (scoped too large for one
> sitting). Picks up the first PE-sourcing feature: financial screening.

## Context

The company search is being turned into a PE deal-sourcing tool. The single
biggest unlock is **financial screening** — letting a user filter the universe
to, say, "profitable companies doing NOK 50–500m revenue". That filter is
impossible today because the index carries only `last_accounts_year` (a year
number), no actual figures.

This plan adds a **Regnskapsregisteret** (annual-accounts) adapter that enriches
existing company documents with revenue and profitability, then exposes those as
filters, table columns, and profile fields. It builds entirely on data Brreg
publishes for free and introduces no Phase-2 (RAG) dependency.

### Decisions taken with the user
- **Profitability metric:** operating profit (`driftsresultat`, ≈ EBIT) plus
  **operating margin**. EBITDA is *not* directly exposed by the open API, and
  `driftsresultat` has 100% coverage across filers. (EBITDA deferred.)
- **Currency:** convert non-NOK figures to **NOK** at fixed reference rates so a
  single revenue band is comparable across all companies. Original currency is
  retained for transparency.

### Key data-source constraints (drove the design)
- **No public bulk download.** The open API is per-org-number only:
  `GET https://data.brreg.no/regnskapsregisteret/regnskap/{orgnr}`, returning a
  JSON **array** of accounts. Bulk XML is a paid subscription. So enrichment is
  ~hundreds of thousands of individual GETs → must be **concurrent, throttled,
  disk-cached, and resumable**. We only call companies that have filed
  (`last_accounts_year` present), and `--limit` keeps early runs to a sample.
- **Latest year only** on the open tier (3-year history needs gov auth) → a
  single financial snapshot per company; no growth/CAGR yet.
- **Currency varies** (e.g. Equinor reports in USD) → convert to NOK.
- API is a flagged-temporary R&D service ("may be shut down without notice") —
  acceptable for this learning project.

### Confirmed JSON field paths (per-account object)
- year: `regnskapsperiode.tilDato` (take the year)
- revenue: `resultatregnskapResultat.driftsresultat.driftsinntekter.sumDriftsinntekter`
- operating profit: `resultatregnskapResultat.driftsresultat.driftsresultat`
- net result: `resultatregnskapResultat.aarsresultat`
- total assets: `eiendeler.sumEiendeler`
- equity: `egenkapitalGjeld.egenkapital.sumEgenkapital`
- total debt: `egenkapitalGjeld.gjeldOversikt.sumGjeld`
- currency: `valuta`

## Architectural shift: enrichment, not creation

The existing pattern is `SourceAdapter.fetch() -> Iterator[Company]` fed to
`pipeline.index_source`, which does full-document **index** (replace) ops keyed
on `NO-{orgnr}` (`src/mini_motherbrain/ingestion/pipeline.py:13`). The financials
adapter does **not** produce whole companies — it produces partial figures to
merge onto documents that already exist. So it needs a parallel **partial-update**
path (bulk `update` ops), not the replace path.

## Implementation

### 1. Data model — `src/mini_motherbrain/models.py`
Add to `Company` (all monetary fields in NOK after conversion):
```
revenue: int | None            # sumDriftsinntekter → NOK
operating_profit: int | None   # driftsresultat (≈ EBIT) → NOK
operating_margin: float | None # operating_profit / revenue (None if revenue falsy)
net_result: int | None         # aarsresultat → NOK
total_assets: int | None       # sumEiendeler → NOK
equity: int | None             # sumEgenkapital → NOK
total_debt: int | None         # sumGjeld → NOK
accounts_year: int | None      # year from regnskapsperiode.tilDato
accounts_currency: str | None  # original reported currency (pre-conversion)
```

### 2. Index mapping + version — `src/mini_motherbrain/es/mappings.py`, `es/indices.py`
Add to `COMPANIES_MAPPING.properties`:
```
revenue, operating_profit, net_result, total_assets, equity, total_debt: {"type": "long"}
operating_margin: {"type": "float"}
accounts_year:    {"type": "integer"}
accounts_currency:{"type": "keyword"}
```
**Use `long`, not `integer`** — large-cap revenues in NOK exceed the int32 ceiling
(~2.1bn); Equinor alone is ~700bn NOK. Then bump `INDEX_VERSION` 3 → 4 in
`es/indices.py:9`. The existing `migrate()` (`es/indices.py:28`) reindexes v3 → v4
and swaps the alias atomically; financial fields stay empty until enrichment runs.

### 3. Enrichment adapter base — `src/mini_motherbrain/ingestion/adapters/base.py`
Add alongside `SourceAdapter`:
```python
class EnrichmentAdapter(ABC):
    """Enrich existing company documents with extra fields from a secondary source."""
    country: str
    @abstractmethod
    def fetch(self, org_numbers: Iterable[str], limit: int | None = None
              ) -> Iterator[tuple[str, dict]]:
        """Yield (org_number, partial_fields_to_merge)."""
```

### 4. New adapter — `src/mini_motherbrain/ingestion/adapters/regnskap.py`
- Constants: `API_URL = "https://data.brreg.no/regnskapsregisteret/regnskap"`,
  `FX_RATES = {"NOK": 1.0, "USD": 10.5, "EUR": 11.5, "SEK": 0.95, "DKK": 1.55, "GBP": 13.5}`
  (fixed reference rates, documented as approximations), cache dir
  `settings.data_dir / "raw" / "regnskap"`.
- `RegnskapAdapter(EnrichmentAdapter)`, `country = "NO"`.
- `fetch(org_numbers, limit)`: for each orgnr (capped at `limit`), read cache
  `{orgnr}.json` if present else GET + write cache; skip 404/empty (no accounts);
  parse array, take latest account, `_normalise()` it, yield `(orgnr, fields)`.
  Use a `ThreadPoolExecutor` (modest worker count, e.g. 8–16) with a shared
  `requests.Session` and a short politeness delay; cache hits skip the network so
  re-runs are fast and resumable. Mirrors the disk-cache spirit of
  `BrregBulkAdapter` (`adapters/brreg.py:95`).
- `_normalise(account: dict) -> dict` (static, unit-testable like
  `BrregAdapter._normalise`): pull the nested paths above, convert each monetary
  field to NOK via `FX_RATES[currency]`, compute `operating_margin`, return the
  field dict. Tolerate missing nested keys (return None for absent figures).

### 5. Enrichment pipeline — `src/mini_motherbrain/ingestion/pipeline.py`
- `scan_org_numbers(client, target)`: `elasticsearch.helpers.scan` over the index
  with `{"exists": {"field": "last_accounts_year"}}`, `_source=["org_number"]`,
  yielding org numbers that have filed (so we don't call the API for companies
  with no accounts).
- `enrich_index(adapter, limit=None, client=None, chunk_size=1000)`: mirror
  `index_source` (refresh-interval toggling, progress logging), but build
  **update** actions:
  ```python
  {"_op_type": "update", "_index": target, "_id": f"{adapter.country}-{org}", "doc": fields}
  ```
  streamed through `streaming_bulk`. `target = ensure_index(client)`.

### 6. CLI — `src/mini_motherbrain/ingestion/__main__.py`
Add an `ENRICHERS = {"regnskap": RegnskapAdapter}` dict next to `ADAPTERS`
(`__main__.py:7`); in `main`, branch: if the name is an enricher call
`enrich_index(ENRICHERS[name](), limit)`, else the existing `index_source` path.
Usage: `mmb-ingest regnskap --limit 2000`.

### 7. Search layer — `src/mini_motherbrain/search/models.py`, `search/queries.py`
- `SearchRequest`: add `min_revenue / max_revenue` and
  `min_operating_margin / max_operating_margin` (margin as a fraction, e.g. 0.10).
  Extend the `SortField` Literal with `revenue` and `operating_profit`.
- `build_query` (`search/queries.py:46`): add two `range` filters following the
  **exact `employees` pattern** at `queries.py:79` (build a dict with optional
  `gte`/`lte`, append `{"range": {"revenue": ...}}` / `operating_margin` only if
  populated). Add `revenue` and `operating_profit` to `SORT_FIELDS`
  (`queries.py:32`). Optionally add a `revenue_ranges` bucket to `AGGREGATIONS`
  (`queries.py:6`) for a size-distribution chart (nice-to-have).

### 8. Front end — `src/mini_motherbrain/app/pages/companies.py` and `pages/company.py`
- **companies.py**: add min/max revenue inputs and a min operating-margin input to
  the toolbar (after the `active-only` control, ~`companies.py:70`); add `Revenue
  (NOK)` and `Operating margin` to `COLUMNS` (`companies.py:24`) and to the row
  `include={...}` set (`companies.py:179`); wire the new `Input(...)`s into the
  `update` callback (`companies.py:138`) and the `SearchRequest`. Format revenue
  in millions for readability (e.g. "1,234" with an "NOK m" header).
- **company.py**: add `_fact(...)` rows to the fact grid (`company.py:47`) for
  Revenue, Operating profit, Operating margin, Net result, Total assets, Equity,
  and Accounts year — showing currency note where original ≠ NOK.

### 9. Tests
- `tests/test_regnskap.py` (new): `_normalise()` on a fixture account — NOK case,
  USD conversion case (assert NOK figures), margin computation, missing-figure
  handling, and empty-array (no accounts) handling. Mirror `tests/test_brreg.py`.
- `tests/test_pipeline.py`: add an `enrich_index` case asserting it emits
  `_op_type: "update"` actions with the right `_id` and `doc` (mock client /
  `streaming_bulk`).
- `tests/test_queries.py` (or wherever `build_query` is tested): revenue and
  operating-margin range-filter cases.

## Verification

1. **Units (no ES needed):** `pytest` — adapter normalisation/conversion,
   enrichment action shape, query range filters all green.
2. **Bring up ES + base data:** Docker compose up; ensure Enhetsregisteret data
   is indexed (`mmb-ingest brreg-bulk`, or a `--limit` sample).
3. **Migrate:** bump `INDEX_VERSION` to 4 and run `migrate()` so v4 (with the new
   mapping) holds the companies and the alias points to it.
4. **Enrich a sample:** `mmb-ingest regnskap --limit 2000`. Confirm raw cache
   files appear under `data/raw/regnskap/` and a second run is fast (cache hits).
5. **Spot-check the data:** query a known orgnr in the index — revenue and
   operating_profit populated and in NOK; verify a USD filer (e.g. Equinor,
   923609016) shows converted NOK figures and `accounts_currency = "USD"`.
6. **End to end in the app:** run the Dash app, apply revenue 50–500m + margin
   ≥10%, confirm the result set and the true count shrink sensibly; open a profile
   and confirm the financials show on the fact grid; sort the table by revenue.

## Effort & risk

- **Effort:** ~1 focused session. Front-end/query/model plumbing is mechanical
  (the `employees` filter is a working template). The real work is the adapter:
  concurrency, disk caching, resumability, currency conversion, and nested-JSON
  parsing with missing-field tolerance.
- **Risks:** (a) full-register enrichment is hundreds of thousands of calls —
  sample first, scale later, lean on the cache; (b) `long` mapping is essential to
  avoid int32 overflow; (c) the API is flagged temporary — cache protects us if it
  goes away; (d) operating margin is meaningless when revenue is ~0 (holding cos) —
  store None and exclude from the margin filter rather than divide by near-zero.

## When picked up — related sourcing follow-ups (not in this plan)
- Visualise the sourcing funnel/flow on the front end (see layout preference in
  memory) once financial filters give the funnel real stages to show.
- Succession/ownership signals; saved searches + watchlists + composite score.
