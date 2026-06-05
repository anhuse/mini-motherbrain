from abc import ABC, abstractmethod
from collections.abc import Iterator

from mini_motherbrain.ingestion.models import Company


class SourceAdapter(ABC):
    """One adapter per data source: fetch raw records and normalise to Company."""

    country: str

    @abstractmethod
    def fetch(self, limit: int) -> Iterator[Company]:
        """Yield up to `limit` normalised companies."""
        raise NotImplementedError
