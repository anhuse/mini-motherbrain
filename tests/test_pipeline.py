from collections.abc import Iterator
from unittest.mock import MagicMock

from mini_motherbrain.ingestion import pipeline
from mini_motherbrain.ingestion.adapters.base import SourceAdapter
from mini_motherbrain.models import Company


class StubAdapter(SourceAdapter):
    country = "NO"
    received_limit = "unset"

    def fetch(self, limit: int | None = None) -> Iterator[Company]:
        StubAdapter.received_limit = limit
        yield Company(org_number="123", name="A AS", country="NO")


def test_index_source_targets_physical_index_with_stable_ids(monkeypatch):
    captured = {}
    monkeypatch.setattr(pipeline, "ensure_index", lambda client: "companies-v2")

    def fake_streaming_bulk(client, actions, **kwargs):
        captured["actions"] = list(actions)
        for action in captured["actions"]:
            yield True, action

    monkeypatch.setattr(pipeline, "streaming_bulk", fake_streaming_bulk)

    count = pipeline.index_source(StubAdapter(), limit=1, client=MagicMock())

    assert count == 1
    [action] = captured["actions"]
    assert action["_index"] == "companies-v2"
    assert action["_id"] == "NO-123"
    assert action["_source"]["name"] == "A AS"


def test_index_source_passes_none_limit_through(monkeypatch):
    monkeypatch.setattr(pipeline, "ensure_index", lambda client: "companies-v2")
    monkeypatch.setattr(
        pipeline, "streaming_bulk", lambda client, actions, **kw: ((True, a) for a in actions)
    )

    pipeline.index_source(StubAdapter(), limit=None, client=MagicMock())

    assert StubAdapter.received_limit is None


def test_index_source_disables_then_restores_refresh(monkeypatch):
    monkeypatch.setattr(pipeline, "ensure_index", lambda client: "companies-v2")
    monkeypatch.setattr(
        pipeline, "streaming_bulk", lambda client, actions, **kw: ((True, a) for a in actions)
    )
    client = MagicMock()

    pipeline.index_source(StubAdapter(), limit=1, client=client)

    settings_calls = [c.kwargs["settings"] for c in client.indices.put_settings.call_args_list]
    assert {"refresh_interval": "-1"} in settings_calls
    assert {"refresh_interval": "1s"} in settings_calls
    client.indices.refresh.assert_called_once()
