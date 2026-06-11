import gzip
import logging
import os
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import httpx
import ijson

from mini_motherbrain.config import settings
from mini_motherbrain.ingestion.adapters.base import SourceAdapter
from mini_motherbrain.models import Company

logger = logging.getLogger(__name__)

API_URL = "https://data.brreg.no/enhetsregisteret/api/enheter"
PAGE_SIZE = 1000
# Deep pagination is capped at 10k results by the API; the bulk adapter below
# is the route past that.
PAGINATION_CAP = 10_000

BULK_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/lastned"
BULK_ACCEPT = "application/vnd.brreg.enhetsregisteret.enhet.v2+gzip;charset=UTF-8"


class BrregAdapter(SourceAdapter):
    """Norway — Brønnøysundregistrene (open, no auth)."""

    country = "NO"
    # Limited-liability companies only — the PE deal-sourcing universe. Filtered
    # server-side so we never pull associations, sole proprietorships, etc.
    ORG_FORMS = ("AS", "ASA")

    def fetch(self, limit: int | None = None) -> Iterator[Company]:
        # Deep pagination is capped at 10k results by the API; for the full
        # register use BrregBulkAdapter instead. The API offsets results by
        # page × size, so size must stay constant across requests; we trim to
        # `limit` client-side instead.
        if limit is None:
            limit = PAGINATION_CAP
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


class BrregBulkAdapter(BrregAdapter):
    """Full register via Brreg's nightly bulk download (regenerated ~05:00).

    The dump is a single, multi-gigabyte gzipped JSON array of every entity.
    We stream it with ijson so memory stays bounded, filter client-side to
    AS/ASA, and reuse the parent's `_normalise`. The downloaded file is kept
    on disk as a raw landing zone and reused for the rest of the day.
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = Path(data_dir) if data_dir is not None else settings.data_dir

    def fetch(self, limit: int | None = None) -> Iterator[Company]:
        path = self._ensure_file()
        seen = matched = 0
        for raw in self._stream_entities(path):
            seen += 1
            if raw.get("organisasjonsform", {}).get("kode") not in self.ORG_FORMS:
                continue
            yield self._normalise(raw)
            matched += 1
            if limit is not None and matched >= limit:
                break
        logger.info("bulk file: %d entities seen, %d AS/ASA matched", seen, matched)

    def _ensure_file(self) -> Path:
        target = self.data_dir / "raw" / f"enheter-{date.today().isoformat()}.json.gz"
        if target.exists():
            logger.info("reusing today's bulk file %s", target)
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        self._download(target)
        return target

    def _download(self, target: Path) -> None:
        # Write to a .part file then atomically rename, so a half-finished
        # download is never mistaken for a complete landing-zone artefact.
        partial = target.with_suffix(".part")
        logger.info("downloading bulk register to %s", target)
        # Read timeout disabled: the dump is large and streamed over minutes.
        with httpx.Client(timeout=httpx.Timeout(30.0, read=None)) as client:
            with client.stream("GET", BULK_URL, headers={"Accept": BULK_ACCEPT}) as resp:
                resp.raise_for_status()
                with open(partial, "wb") as fh:
                    for chunk in resp.iter_bytes():
                        fh.write(chunk)
        os.replace(partial, target)

    @staticmethod
    def _stream_entities(path: Path) -> Iterator[dict]:
        # The dump is a single top-level JSON array; "item" yields each element.
        # Fail loudly on a truncated download or a format change rather than
        # silently yielding a partial register.
        try:
            with gzip.open(path, "rb") as fh:
                yield from ijson.items(fh, "item")
        except (ijson.JSONError, OSError, EOFError) as exc:
            raise ValueError(f"Could not parse Brreg bulk file {path}: {exc}") from exc
