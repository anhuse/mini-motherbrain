# Plan — Company screening view with sourcing funnel

> Status: **not started** — parked for a future session. The user wants to build
> this next, as a dedicated view (not by extending the Companies search page).

## Context

The tool is being turned into a PE deal-sourcing platform. The Companies page is
a *search* tool — flat query → results table. What's wanted now is a *screening*
experience: pick core dimensions, narrow the universe stage by stage, and end up
with an explicit **selection of companies** (a short list) to act on. The
narrowing should be shown as a **funnel/flow visual** — see the standing
preference in memory ([[frontend-sourcing-funnel-layout]]): the universe narrows
thesis → long list → filters applied → short list → target, with a live count at
each stage.

This became buildable once the financials landed (revenue, operating margin — see
`plans/regnskapsregisteret-financials-adapter.md`), because those add real funnel
stages beyond name/industry/geography.

## Prerequisite — full financial enrichment (do first)

The financials adapter is built but only a ~2,000-company sample is enriched, so
revenue/margin filters barely bite. Before this view is meaningful, run the full
enrichment so financial stages have real coverage:

```
python -m mini_motherbrain.ingestion regnskap        # all filers; concurrent, disk-cached, resumable
```

Hundreds of thousands of API calls — resumable and cached under
`data/raw/regnskap/`, safe to Ctrl-C and re-run. Consider scaling in steps
(`--limit 50000`) and checking coverage before the full pull. This is the first
"next step" the user asked to save; the screening view is the second.

## What to build

A new page (e.g. `/screen`) added to the Dash pages app and the sidebar (there
are already disabled "soon" teasers in `app/dashboard.py` to slot into).

### 1. Filter on core dimensions
Controls for the dimensions a sourcing screen turns on, reusing the typed
`SearchRequest` (already carries all of these — no new query plumbing needed):
- **Employees** (min/max) — `min_employees` / `max_employees`
- **Revenue NOK** (min/max) — `min_revenue` / `max_revenue`
- **Operating margin** (min/max) — `min_operating_margin` / `max_operating_margin`
- **Industry** (NACE) — `industry_codes`
- **Geography** (municipality) — `municipalities`
- **Active only** — `exclude_inactive`
- Free text (thesis keywords) — `text`

### 2. The funnel visual
A stage-by-stage funnel/flow showing how the count narrows as each filter class is
applied, e.g.:
`All AS/ASA → active → industry → size (employees+revenue) → profitability → short list`.
Each stage shows its surviving count. Implementation approach to decide with the
user (respects the [[spar-on-design-decisions]] checkpoint — **spar the specific
visual treatment before building it**):
- Compute stage counts by issuing the search with filters added cumulatively
  (one `count`/`search size=0` per stage), or with a single query plus filter
  aggregations. Cumulative counts are simplest and reuse `build_query`.
- Render as a Plotly funnel (`go.Funnel`) or a custom flow — match the existing
  "motherbrain" template in `app/figures.py` (EQT orange on warm off-white; keep
  tokens in sync with `assets/style.css`).

### 3. End with a selection
The output is an explicit short list the user can carry forward:
- Row selection in the results table (`row_selectable`), or an "add to selection"
  action per company.
- Show the selected set (count + list), with export (CSV download via
  `dcc.Download`) as the minimum "act on it" affordance.
- Selection is the seed for the later **saved searches / watchlists / composite
  attractiveness score** work (already on the sourcing backlog).

## Notes / decisions to take with the user
- **Screening page vs. extending Companies:** the user explicitly wants a *new
  view*, distinct from the Companies search page. (The two bottom charts were
  removed from Companies as noise in the session that parked this plan.)
- **Funnel stage order and grouping** — which filters form which stage — is a
  design choice to confirm.
- **Selection persistence** — in-memory for the session first (`dcc.Store`);
  durable watchlists come with the saved-searches feature later.

## Related backlog (not in this plan)
Saved searches + watchlists + composite attractiveness score; succession/ownership
signals; similarity/look-alike search (Phase 2 RAG). The selection built here is
the natural input to the first of those.
