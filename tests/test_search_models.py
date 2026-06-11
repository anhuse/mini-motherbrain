import pytest
from pydantic import ValidationError

from mini_motherbrain.search.models import SearchRequest


def test_offset_window_capped_at_10k():
    SearchRequest(offset=9_980, size=20)  # exactly at the window: allowed
    with pytest.raises(ValidationError, match="result window"):
        SearchRequest(offset=9_981, size=20)


def test_negative_offset_rejected():
    with pytest.raises(ValidationError):
        SearchRequest(offset=-1)


def test_invalid_sort_field_rejected():
    with pytest.raises(ValidationError):
        SearchRequest(sort_field="bankrupt")
