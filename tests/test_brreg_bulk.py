import gzip
import json
from datetime import date

import pytest

from mini_motherbrain.ingestion.adapters import brreg
from mini_motherbrain.ingestion.adapters.brreg import BrregBulkAdapter

ENTITIES = [
    {"organisasjonsnummer": "1", "navn": "ALPHA AS", "organisasjonsform": {"kode": "AS"}},
    {"organisasjonsnummer": "2", "navn": "BETA ASA", "organisasjonsform": {"kode": "ASA"}},
    {"organisasjonsnummer": "3", "navn": "GAMMA ENK", "organisasjonsform": {"kode": "ENK"}},
    {"organisasjonsnummer": "4", "navn": "DELTA (no form)"},
]


def _place_file(data_dir, entities=ENTITIES):
    target = data_dir / "raw" / f"enheter-{date.today().isoformat()}.json.gz"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(gzip.compress(json.dumps(entities).encode()))
    return target


def test_fetch_streams_and_filters_to_as_asa(tmp_path):
    _place_file(tmp_path)

    companies = list(BrregBulkAdapter(data_dir=tmp_path).fetch())

    assert [c.org_number for c in companies] == ["1", "2"]
    assert companies[0].name == "ALPHA AS"
    assert companies[0].country == "NO"


def test_normalise_collects_all_nace_codes_and_purpose(tmp_path):
    raw = {
        "organisasjonsnummer": "5",
        "navn": "OMEGA AS",
        "organisasjonsform": {"kode": "AS"},
        "naeringskode1": {"kode": "06.200", "beskrivelse": "Utvinning av naturgass"},
        "naeringskode2": {"kode": "06.100", "beskrivelse": "Utvinning av råolje"},
        "vedtektsfestetFormaal": ["Utvinning av", "olje og gass."],
    }
    _place_file(tmp_path, [raw])

    [company] = list(BrregBulkAdapter(data_dir=tmp_path).fetch())

    # Primary stays for display; all codes collected for filtering.
    assert company.industry_code == "06.200"
    assert company.industry_codes == ["06.200", "06.100"]
    assert "Utvinning av råolje" in company.industry_text_all
    assert company.purpose == "Utvinning av olje og gass."


def test_fetch_respects_limit(tmp_path):
    _place_file(tmp_path)

    companies = list(BrregBulkAdapter(data_dir=tmp_path).fetch(limit=1))

    assert len(companies) == 1
    assert companies[0].org_number == "1"


def test_skips_download_when_todays_file_exists(tmp_path, monkeypatch):
    _place_file(tmp_path)

    def no_download(*args, **kwargs):
        raise AssertionError("should not download when today's file exists")

    monkeypatch.setattr(brreg.httpx, "Client", no_download)

    companies = list(BrregBulkAdapter(data_dir=tmp_path).fetch())

    assert len(companies) == 2


class _FakeStream:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        pass

    def iter_bytes(self):
        # Two chunks, to exercise the chunked write path.
        mid = len(self._payload) // 2
        yield self._payload[:mid]
        yield self._payload[mid:]


class _FakeClient:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def stream(self, method, url, headers=None):
        return _FakeStream(self._payload)


def test_download_writes_file_atomically(tmp_path, monkeypatch):
    payload = gzip.compress(json.dumps(ENTITIES).encode())
    monkeypatch.setattr(brreg.httpx, "Client", lambda *a, **k: _FakeClient(payload))

    companies = list(BrregBulkAdapter(data_dir=tmp_path).fetch())

    raw_dir = tmp_path / "raw"
    final = raw_dir / f"enheter-{date.today().isoformat()}.json.gz"
    assert final.exists()
    assert not list(raw_dir.glob("*.part"))
    assert [c.org_number for c in companies] == ["1", "2"]


def test_corrupt_file_raises(tmp_path):
    target = tmp_path / "raw" / f"enheter-{date.today().isoformat()}.json.gz"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"not gzip at all")

    with pytest.raises(ValueError, match="Could not parse Brreg bulk file"):
        list(BrregBulkAdapter(data_dir=tmp_path).fetch())
