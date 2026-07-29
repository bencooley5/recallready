"""Deterministic tabletop packet tests."""

from __future__ import annotations

from recallready.analytics.tabletop import TabletopInputs, build_tabletop, select_analogs

INPUTS = TabletopInputs("seafood", "pathogen_contamination", "Class I", "manufacturer", 2, "regional", "introductory", ("quality",), "Finfish")
ROWS = [{"source_record_id": "2", "recall_number": "F-2", "event_id": "E-2", "report_date": "2024-01-01", "derived_product_category": "seafood", "primary_hazard": "pathogen_contamination", "classification": "Class I"}, {"source_record_id": "1", "recall_number": "F-1", "report_date": "2023-01-01", "derived_product_category": "seafood", "primary_hazard": "pathogen_contamination", "classification": "Class I"}]


def test_deterministic_analogs_and_export_evidence() -> None:
    packet = build_tabletop(INPUTS, ROWS)
    assert select_analogs(ROWS, INPUTS) == select_analogs(list(reversed(ROWS)), INPUTS)
    assert "Recall F-2" in packet.markdown
    assert "compliance" in packet.markdown.casefold()


def test_no_match_and_ftl_optional_fallback() -> None:
    empty = build_tabletop(TabletopInputs("dairy", "", None, "retailer", 1, "local", "introductory", (), None), ROWS)
    assert not empty.analogs
    assert "No matching" in empty.markdown
    assert "No FTL category" in empty.narrative
