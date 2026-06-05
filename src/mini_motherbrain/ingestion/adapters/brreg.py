from collections.abc import Iterator

import httpx

from mini_motherbrain.ingestion.adapters.base import SourceAdapter
from mini_motherbrain.ingestion.models import Company

API_URL = "https://data.brreg.no/enhetsregisteret/api/enheter"
PAGE_SIZE = 1000


class BrregAdapter(SourceAdapter):
    """Norway — Brønnøysundregistrene (open, no auth)."""

    country = "NO"

    def fetch(self, limit: int) -> Iterator[Company]:
        fetched, page = 0, 0
        with httpx.Client(timeout=30) as client:
            while fetched < limit:
                size = min(PAGE_SIZE, limit - fetched)
                resp = client.get(API_URL, params={"page": page, "size": size})
                resp.raise_for_status()
                entities = resp.json().get("_embedded", {}).get("enheter", [])
                if not entities:
                    return
                for raw in entities:
                    yield self._normalise(raw)
                    fetched += 1
                page += 1

    @staticmethod
    def _normalise(raw: dict) -> Company:
        activity = raw.get("aktivitet")
        return Company(
            org_number=raw["organisasjonsnummer"],
            name=raw["navn"],
            country="NO",
            org_form=raw.get("organisasjonsform", {}).get("kode"),
            industry_code=raw.get("naeringskode1", {}).get("kode"),
            industry_text=raw.get("naeringskode1", {}).get("beskrivelse"),
            employees=raw.get("antallAnsatte"),
            municipality=raw.get("forretningsadresse", {}).get("kommune"),
            registered_at=raw.get("registreringsdatoEnhetsregisteret"),
            description=" ".join(activity) if activity else None,
        )
