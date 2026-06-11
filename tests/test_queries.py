from mini_motherbrain.search.models import SearchRequest
from mini_motherbrain.search.queries import AGGREGATIONS, build_query, build_sort


def test_empty_request_matches_all():
    query = build_query(SearchRequest())

    assert query == {"bool": {"must": [{"match_all": {}}], "filter": []}}


def test_free_text_searches_name_industry_and_description():
    query = build_query(SearchRequest(text="oil"))

    [match] = query["bool"]["must"]
    assert match["multi_match"]["query"] == "oil"
    assert "name^3" in match["multi_match"]["fields"]


def test_filters_combine():
    request = SearchRequest(
        industry_codes=["06.100"],
        municipalities=["STAVANGER"],
        min_employees=10,
        max_employees=500,
    )

    filters = build_query(request)["bool"]["filter"]

    assert {"terms": {"industry_code": ["06.100"]}} in filters
    assert {"terms": {"municipality": ["STAVANGER"]}} in filters
    assert {"range": {"employees": {"gte": 10, "lte": 500}}} in filters


def test_exclude_inactive_filters_all_status_flags():
    filters = build_query(SearchRequest(exclude_inactive=True))["bool"]["filter"]

    assert {"term": {"bankrupt": False}} in filters
    assert {"term": {"under_liquidation": False}} in filters
    assert {"term": {"under_forced_liquidation": False}} in filters


def test_build_sort_default_is_relevance():
    assert build_sort(SearchRequest()) == []


def test_build_sort_maps_field_and_adds_tiebreaker():
    sort = build_sort(SearchRequest(sort_field="industry_text"))

    assert sort[0] == {"industry_text.raw": {"order": "asc", "missing": "_last"}}
    assert sort[-1] == {"org_number": "asc"}


def test_build_sort_desc_sets_order():
    sort = build_sort(SearchRequest(sort_field="employees", sort_desc=True))

    assert sort[0] == {"employees": {"order": "desc", "missing": "_last"}}


def test_aggregations_include_founded_year_histogram():
    assert AGGREGATIONS["founded_years"]["date_histogram"]["calendar_interval"] == "year"
    assert AGGREGATIONS["industries_text"]["terms"]["field"] == "industry_text.raw"
