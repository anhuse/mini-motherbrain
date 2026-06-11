from collections.abc import Iterator

from mini_motherbrain.ingestion import pipeline
from mini_motherbrain.ingestion.adapters.base import SourceAdapter
from mini_motherbrain.models import Company


class StubAdapter(SourceAdapter):
    country = "NO"

    def fetch(self, limit: int) -> Iterator[Company]:
        yield Company(org_number="123", name="A AS", country="NO")


def test_index_source_targets_physical_index_with_stable_ids(monkeypatch):
    captured = {}
    monkeypatch.setattr(pipeline, "ensure_index", lambda client: "companies-v1")

    def fake_bulk(client, actions):
        captured["actions"] = list(actions)
        return len(captured["actions"]), []

    monkeypatch.setattr(pipeline, "bulk", fake_bulk)

    count = pipeline.index_source(StubAdapter(), limit=1, client=object())

    assert count == 1
    [action] = captured["actions"]
    assert action["_index"] == "companies-v1"
    assert action["_id"] == "NO-123"
    assert action["_source"]["name"] == "A AS"
