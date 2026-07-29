"""Tests for source-preserving record normalization."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from recallready.data.normalize import (
    clean_text,
    normalize_firm,
    normalize_record,
    parse_source_date,
    source_record_id,
)
from recallready.models import FoodEnforcementRecord, SourceFoodEnforcementRecord


@pytest.fixture
def fixture_records() -> list[dict[str, object]]:
    """Load representative records without performing a network request."""
    fixture_path = Path(__file__).parent / "fixtures" / "normalization_records.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _source(raw: dict[str, object]) -> SourceFoodEnforcementRecord:
    return SourceFoodEnforcementRecord(parsed=FoodEnforcementRecord.model_validate(raw), raw=raw)


def test_normalization_preserves_source_and_creates_separate_clean_values(
    fixture_records: list[dict[str, object]]
) -> None:
    """Raw values and identifiers remain intact alongside cleaned derived fields."""
    raw = fixture_records[0]
    normalized = normalize_record(_source(raw))

    assert normalized.raw == raw
    assert normalized.recall_number == "F-123-2011"
    assert normalized.event_id == "123456"
    assert normalized.product_description == "  Crème\tMilk Product  "
    assert normalized.product_description_clean == "Crème Milk Product"
    assert (
        normalized.reason_for_recall_clean == "Undeclared Sesame; possible Listeria monocytogenes."
    )
    assert normalized.firm_normalized == "example foods"
    assert normalized.recall_initiation_date == date(2011, 6, 1)
    assert normalized.report_date == date(2011, 6, 10)
    assert normalized.reporting_lag_days == 9
    assert normalized.hazard.primary_hazard == "pathogen_contamination"
    assert {tag.tag_value for tag in normalized.hazard.tags} >= {"sesame", "listeria"}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("20240229", date(2024, 2, 29)),
        ("20230229", None),
        ("20241301", None),
        ("2024011", None),
        (None, None),
    ],
)
def test_parse_source_date_is_nullable_and_strict(value: str | None, expected: date | None) -> None:
    """Only valid source-format dates become derived date values."""
    assert parse_source_date(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("  Café\u00a0Foods\n", "Café Foods"),
        ("\tExample\u212A\t", "ExampleK"),
        ("   ", None),
        (None, None),
    ],
)
def test_clean_text_normalizes_unicode_and_whitespace_without_mutating_source(
    value: str | None, expected: str | None
) -> None:
    """Cleaning is explicit and leaves originals available on the source record."""
    assert clean_text(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Acme Foods, Inc.", "acme foods"),
        ("ACME-Foods LLC", "acme foods"),
        ("Acme Foods & Co.", "acme foods"),
        ("The Company Store", "the company store"),
        (None, None),
    ],
)
def test_firm_normalization_only_removes_configured_terminal_legal_suffixes(
    value: str | None, expected: str | None
) -> None:
    """Firm keys are conservative comparison aids, not fuzzy entity resolution."""
    assert normalize_firm(value) == expected


def test_source_record_id_is_deterministic_and_content_sensitive() -> None:
    """Stable identifier hash is reproducible and changes with selected source content."""
    first = {"recall_number": "F-1", "event_id": "E-1", "product_description": "Food"}
    equivalent = {"product_description": "Food", "event_id": "E-1", "recall_number": "F-1"}
    changed = {"recall_number": "F-1", "event_id": "E-1", "product_description": "Other"}

    assert source_record_id(first) == source_record_id(equivalent)
    assert source_record_id(first) != source_record_id(changed)


def test_missing_historical_fields_remain_null(fixture_records: list[dict[str, object]]) -> None:
    """Pre-2012 sparsity cannot be silently filled by normalizers."""
    normalized = normalize_record(_source(fixture_records[1]))

    assert normalized.event_id is None
    assert normalized.recalling_firm is None
    assert normalized.recall_initiation_date is None
    assert normalized.reporting_lag_days is None
