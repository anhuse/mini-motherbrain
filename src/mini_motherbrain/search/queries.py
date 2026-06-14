from mini_motherbrain.search.models import SearchRequest

# Facets recomputed on every search so filter options stay consistent
# with the current query. `industries` keys on the code (the dropdown's filter
# value); `industries_text` carries human-readable labels for the chart.
AGGREGATIONS = {
    "industries": {"terms": {"field": "industry_code", "size": 20}},
    "industries_text": {"terms": {"field": "industry_text.raw", "size": 10}},
    "municipalities": {"terms": {"field": "municipality", "size": 20}},
    "org_forms": {"terms": {"field": "org_form", "size": 10}},
    "founded_years": {
        "date_histogram": {
            "field": "founded_at",
            "calendar_interval": "year",
            "format": "yyyy",
            "min_doc_count": 1,
        }
    },
}

# Maps the request's closed sort vocabulary to concrete ES fields (text fields
# need their keyword subfield to be sortable).
SORT_FIELDS = {
    "name": "name.raw",
    "industry_text": "industry_text.raw",
    "municipality": "municipality",
    "employees": "employees",
    "founded_at": "founded_at",
}


def build_sort(request: SearchRequest) -> list[dict]:
    """Translate a SearchRequest's sort into ES sort clauses. Empty list means
    relevance order. A stable org_number tiebreaker keeps pagination from
    showing duplicate rows when the primary key ties."""
    if request.sort_field is None:
        return []
    order = "desc" if request.sort_desc else "asc"
    field = SORT_FIELDS[request.sort_field]
    return [
        {field: {"order": order, "missing": "_last"}},
        {"org_number": "asc"},
    ]


def build_query(request: SearchRequest) -> dict:
    """Translate a SearchRequest into Elasticsearch query DSL. Pure function,
    no client involved, so it is unit-testable without a cluster."""
    must: list[dict] = []
    if request.text:
        must.append(
            {
                "multi_match": {
                    "query": request.text,
                    "fields": [
                        "name^3",
                        "industry_text",
                        "industry_text_all",
                        "description",
                        "purpose",
                    ],
                    # Tolerate typos and spelling variants (ø/o, aa/å); require
                    # most terms to match so fuzz + the default OR stays precise.
                    "fuzziness": "AUTO",
                    "minimum_should_match": "2<70%",
                }
            }
        )

    filters: list[dict] = []
    if request.industry_codes:
        # Match against every NACE code a company carries, not just its primary.
        filters.append({"terms": {"industry_codes": request.industry_codes}})
    if request.org_forms:
        filters.append({"terms": {"org_form": request.org_forms}})
    if request.municipalities:
        filters.append({"terms": {"municipality": request.municipalities}})

    employees: dict = {}
    if request.min_employees is not None:
        employees["gte"] = request.min_employees
    if request.max_employees is not None:
        employees["lte"] = request.max_employees
    if employees:
        filters.append({"range": {"employees": employees}})

    if request.exclude_inactive:
        filters += [
            {"term": {"bankrupt": False}},
            {"term": {"under_liquidation": False}},
            {"term": {"under_forced_liquidation": False}},
        ]

    return {"bool": {"must": must or [{"match_all": {}}], "filter": filters}}
