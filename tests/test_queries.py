from mini_motherbrain.search.models import SearchRequest
from mini_motherbrain.search.queries import build_query


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
