from abc import ABC, abstractmethod
from collections.abc import Iterator

from mini_motherbrain.models import Company


class SourceAdapter(ABC):
    """One adapter per data source: fetch raw records and normalise to Company."""

    country: str

    @abstractmethod
    def fetch(self, limit: int | None = None) -> Iterator[Company]:
        """Yield up to `limit` normalised companies, or all available if None."""
        raise NotImplementedError
