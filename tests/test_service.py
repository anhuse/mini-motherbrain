from mini_motherbrain.search.models import SearchRequest
from mini_motherbrain.search.service import search


class RecordingClient:
    """Records the kwargs passed to search() and returns a canned response
    carrying both a terms agg and a date_histogram agg."""

    def __init__(self):
        self.kwargs = {}

    def search(self, **kwargs):
        self.kwargs = kwargs
        return {
            "hits": {
                "total": {"value": 1},
                "hits": [{"_source": {"org_number": "1", "name": "ALPHA AS", "country": "NO"}}],
            },
            "aggregations": {
                "industries": {"buckets": [{"key": "06.100", "doc_count": 3}]},
                "founded_years": {
                    "buckets": [{"key": 63072000000, "key_as_string": "1972", "doc_count": 5}]
                },
            },
        }


def test_offset_and_sort_passed_through():
    client = RecordingClient()

    search(SearchRequest(offset=40, sort_field="employees", sort_desc=True), client=client)

    assert client.kwargs["from_"] == 40
    assert client.kwargs["sort"][0] == {"employees": {"order": "desc", "missing": "_last"}}


def test_relevance_sort_passes_none():
    client = RecordingClient()

    search(SearchRequest(), client=client)

    assert client.kwargs["sort"] is None


def test_tracks_true_total():
    client = RecordingClient()

    search(SearchRequest(), client=client)

    assert client.kwargs["track_total_hits"] is True


def test_date_histogram_uses_key_as_string():
    client = RecordingClient()

    result = search(SearchRequest(), client=client)

    assert result.total == 1
    assert result.companies[0].name == "ALPHA AS"
    assert result.facets["founded_years"][0].key == "1972"
    assert result.facets["industries"][0].key == "06.100"
