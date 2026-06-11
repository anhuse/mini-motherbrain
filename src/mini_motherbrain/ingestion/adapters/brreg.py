from collections.abc import Iterator

import httpx

from mini_motherbrain.ingestion.adapters.base import SourceAdapter
from mini_motherbrain.models import Company

API_URL = "https://data.brreg.no/enhetsregisteret/api/enheter"
PAGE_SIZE = 1000


class BrregAdapter(SourceAdapter):
    """Norway — Brønnøysundregistrene (open, no auth)."""

    country = "NO"
    # Limited-liability companies only — the PE deal-sourcing universe. Filtered
    # server-side so we never pull associations, sole proprietorships, etc.
    ORG_FORMS = ("AS", "ASA")

    def fetch(self, limit: int) -> Iterator[Company]:
        # Deep pagination is capped at 10k results by the API; fine for samples,
        # but scaling beyond that needs search_after/scroll.
        # The API offsets results by page × size, so size must stay constant
        # across requests; we trim to `limit` client-side instead.
        fetched, page = 0, 0
        with httpx.Client(timeout=30) as client:
            while fetched < limit:
                params = [("page", page), ("size", PAGE_SIZE)]
                params += [("organisasjonsform", form) for form in self.ORG_FORMS]
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                entities = resp.json().get("_embedded", {}).get("enheter", [])
                if not entities:
                    return
                for raw in entities:
                    yield self._normalise(raw)
                    fetched += 1
                    if fetched >= limit:
                        return
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
            founded_at=raw.get("stiftelsesdato"),
            last_accounts_year=raw.get("sisteInnsendteAarsregnskap"),
            bankrupt=raw.get("konkurs", False),
            under_liquidation=raw.get("underAvvikling", False),
            under_forced_liquidation=raw.get("underTvangsavviklingEllerTvangsopplosning", False),
            vat_registered=raw.get("registrertIMvaregisteret", False),
            in_group=raw.get("erIKonsern", False),
            description=" ".join(activity) if activity else None,
        )
