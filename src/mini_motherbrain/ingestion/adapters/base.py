from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator

from mini_motherbrain.models import Company


class SourceAdapter(ABC):
    """One adapter per data source: fetch raw records and normalise to Company."""

    country: str

    @abstractmethod
    def fetch(self, limit: int | None = None) -> Iterator[Company]:
        """Yield up to `limit` normalised companies, or all available if None."""
        raise NotImplementedError


class EnrichmentAdapter(ABC):
    """Enrich existing company documents with extra fields from a secondary
    source. Unlike a SourceAdapter it does not produce whole companies — it
    yields partial figures to merge onto documents that already exist, so the
    pipeline drives it with bulk `update` ops rather than full-document index."""

    country: str

    @abstractmethod
    def fetch(
        self, org_numbers: Iterable[str], limit: int | None = None
    ) -> Iterator[tuple[str, dict]]:
        """Yield (org_number, partial_fields_to_merge) for companies with data."""
        raise NotImplementedError
