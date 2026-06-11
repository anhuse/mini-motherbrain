from mini_motherbrain.search.models import SearchRequest

# Facets recomputed on every search so filter options stay consistent
# with the current query.
AGGREGATIONS = {
    "industries": {"terms": {"field": "industry_code", "size": 20}},
    "municipalities": {"terms": {"field": "municipality", "size": 20}},
    "org_forms": {"terms": {"field": "org_form", "size": 10}},
}


def build_query(request: SearchRequest) -> dict:
    """Translate a SearchRequest into Elasticsearch query DSL. Pure function,
    no client involved, so it is unit-testable without a cluster."""
    must: list[dict] = []
    if request.text:
        must.append(
            {
                "multi_match": {
                    "query": request.text,
                    "fields": ["name^3", "industry_text", "description"],
                }
            }
        )

    filters: list[dict] = []
    if request.industry_codes:
        filters.append({"terms": {"industry_code": request.industry_codes}})
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
