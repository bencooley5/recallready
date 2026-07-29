"""Focused non-rendering tests for Recall Explorer state and exports."""
from __future__ import annotations

from datetime import date

from recallready.ui.filters import (
    FilterState,
    from_query_params,
    to_query_params,
    to_record_filters,
)


def test_query_parameter_round_trip_includes_bounded_explorer_keyword() -> None:
    state = FilterState(date(2024, 1, 1), date(2024, 2, 1), ("Class I",), ("dairy",), ("CA",), "untrusted search")
    params = to_query_params(state)
    restored = from_query_params(params)
    assert restored.keyword == "untrusted search"
    assert restored.classifications == ("Class I",)
    assert to_record_filters(restored).states == ("CA",)

def test_malicious_query_parameters_are_bounded_and_safe() -> None:
    state = from_query_params({"start": "DROP TABLE", "classification": "x" * 1000, "basis": "sql"})
    assert state.start_date is None
    assert state.classifications == ()
    assert state.date_basis == "report_date"


def test_keyword_query_parameter_is_normalized_and_bounded() -> None:
    state = from_query_params({"keyword": "  Listeria   records  " + "x" * 500})
    assert state.keyword.startswith("Listeria records")
    assert len(state.keyword) == 120
