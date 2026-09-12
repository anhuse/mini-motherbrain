"""Norway — Regnskapsregisteret (annual accounts), the open per-org-number API.

Enriches existing company documents with revenue and profitability. There is no
public bulk download on the open tier, so enrichment is hundreds of thousands of
individual GETs: we run them concurrently, cache each response on disk keyed by
org number, and treat cache hits as skips so re-runs are fast and resumable.
Only the latest filed year is available on the open tier.
"""

import json
import logging
import time
from collections.abc import Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from itertools import islice
from pathlib import Path

import httpx

from mini_motherbrain.config import settings
from mini_motherbrain.ingestion.adapters.base import EnrichmentAdapter

logger = logging.getLogger(__name__)

API_URL = "https://data.brreg.no/regnskapsregisteret/regnskap"

# Fixed reference rates to NOK. Approximations, held constant so a single revenue
# band is comparable across all filers regardless of reporting currency. The
# originally reported currency is retained on the document for transparency.
FX_RATES: dict[str, float] = {
    "NOK": 1.0,
    "USD": 10.5,
    "EUR": 11.5,
    "SEK": 0.95,
    "DKK": 1.55,
    "GBP": 13.5,
}

# Small per-request pause so a poolful of workers stays polite to a flagged
# temporary R&D service.
REQUEST_DELAY = 0.05


class RegnskapAdapter(EnrichmentAdapter):
    """Enrich companies with their latest annual accounts from Regnskapsregisteret."""

    country = "NO"

    def __init__(self, data_dir: Path | None = None, max_workers: int = 12) -> None:
        base = Path(data_dir) if data_dir is not None else settings.data_dir
        self.cache_dir = base / "raw" / "regnskap"
        self.max_workers = max_workers

    def fetch(
        self, org_numbers: Iterable[str], limit: int | None = None
    ) -> Iterator[tuple[str, dict]]:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        targets = list(islice(org_numbers, limit)) if limit is not None else list(org_numbers)
        seen = enriched = 0
        with httpx.Client(timeout=30) as client:
            with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                for org, accounts in pool.map(lambda o: (o, self._accounts(o, client)), targets):
                    seen += 1
                    account = self._select_latest(accounts)
                    if account is None:
                        continue
                    yield org, self._normalise(account)
                    enriched += 1
                    if enriched % 5_000 == 0:
                        logger.info("enriched %d of %d fetched", enriched, seen)
        logger.info("regnskap: %d org numbers fetched, %d enriched", seen, enriched)

    def _accounts(self, org: str, client: httpx.Client) -> list[dict]:
        """Return the raw accounts array for an org number, from disk cache if
        present else the network. Companies with no accounts (404/empty) cache
        as an empty array so a re-run skips them without another request."""
        cached = self.cache_dir / f"{org}.json"
        if cached.exists():
            try:
                return json.loads(cached.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass  # corrupt cache entry — refetch below
        time.sleep(REQUEST_DELAY)
        try:
            resp = client.get(f"{API_URL}/{org}")
            accounts = resp.json() if resp.status_code == 200 else []
        except (httpx.HTTPError, json.JSONDecodeError):
            logger.warning("regnskap fetch failed for %s", org)
            return []
        if not isinstance(accounts, list):
            accounts = []
        cached.write_text(json.dumps(accounts), encoding="utf-8")
        return accounts

    @staticmethod
    def _select_latest(accounts: list[dict]) -> dict | None:
        """Pick the most recent company (non-consolidated) accounts. The API can
        return both company ('SELSKAP') and group ('KONSERN') figures; we want
        the company's own. Falls back to all entries if type is unmarked."""
        if not accounts:
            return None
        company = [a for a in accounts if a.get("regnskapstype") == "SELSKAP"]
        candidates = company or accounts

        def year(account: dict) -> str:
            return account.get("regnskapsperiode", {}).get("tilDato", "")

        return max(candidates, key=year)

    @staticmethod
    def _normalise(account: dict) -> dict:
        """Pull the figures we track from one accounts object, converting each
        monetary field to NOK. Tolerates missing nested keys (returns None for
        absent figures). Unit-testable like BrregAdapter._normalise."""
        result = account.get("resultatregnskapResultat", {})
        operating = result.get("driftsresultat", {})
        assets = account.get("eiendeler", {})
        equity_debt = account.get("egenkapitalGjeld", {})

        currency = account.get("valuta") or "NOK"
        rate = FX_RATES.get(currency, 1.0)

        def to_nok(value) -> int | None:
            return round(value * rate) if isinstance(value, (int, float)) else None

        revenue = to_nok(operating.get("driftsinntekter", {}).get("sumDriftsinntekter"))
        operating_profit = to_nok(operating.get("driftsresultat"))
        # Margin is meaningless when revenue is ~0 (holding companies) — leave None.
        operating_margin = (
            operating_profit / revenue if revenue and operating_profit is not None else None
        )
        to_date = account.get("regnskapsperiode", {}).get("tilDato", "")
        accounts_year = int(to_date[:4]) if to_date[:4].isdigit() else None

        return {
            "revenue": revenue,
            "operating_profit": operating_profit,
            "operating_margin": operating_margin,
            "net_result": to_nok(result.get("aarsresultat")),
            "total_assets": to_nok(assets.get("sumEiendeler")),
            "equity": to_nok(equity_debt.get("egenkapital", {}).get("sumEgenkapital")),
            "total_debt": to_nok(equity_debt.get("gjeldOversikt", {}).get("sumGjeld")),
            "accounts_year": accounts_year,
            "accounts_currency": currency,
        }
