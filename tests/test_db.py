"""Fixture-database tests for atomic SQLite builds and trusted repository queries."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from recallready.data.normalize import normalize_record
from recallready.db.build import BuildMetadata, build_database
from recallready.db.queries import CategoryDimension, SortOption
from recallready.db.repository import MAX_RESULT_ROWS, RecallRepository, RecordFilters
from recallready.models import FoodEnforcementRecord, SourceFoodEnforcementRecord


def _normalized(**overrides: str | None):
    raw: dict[str, str | None] = {
        "recall_number": "F-001", "event_id": "E-1", "report_date": "20240110",
        "recall_initiation_date": "20240101", "product_description": "Sesame bread",
        "reason_for_recall": "Undeclared sesame", "recalling_firm": "Acme Foods, Inc.",
        "classification": "Class I", "state": "CA", "country": "US", "product_type": "Food",
    }
    raw.update(overrides)
    source = SourceFoodEnforcementRecord(parsed=FoodEnforcementRecord.model_validate(raw), raw=raw)
    return normalize_record(source)


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    """Build a compact test database in a disposable directory."""
    records = [_normalized(), _normalized(recall_number="F-002", event_id="E-1", state="NY"), _normalized(recall_number="F-003", event_id=None, report_date="20230201", product_description="Baked roll", reason_for_recall="Glass fragment")]
    path = tmp_path / "recalls.sqlite"
    build_database(records, path, BuildMetadata(source_last_updated="2026-01-01", source_total_matches=3))
    return path


def test_fixture_database_builds_with_synced_fts(database_path: Path) -> None:
    """An atomic build persists rows, tags, run provenance, and FTS content."""
    repository = RecallRepository(database_path)
    try:
        assert repository.summary_metrics()["product_record_count"] == 3
        assert len(repository.full_text_search("sesame")) == 2
        assert repository.recall_detail(_normalized().source_record_id) is not None
    finally:
        repository.close()


def test_filters_date_ranges_and_missing_event_ids(database_path: Path) -> None:
    """Dates and older missing event IDs are explicit query conditions."""
    repository = RecallRepository(database_path)
    try:
        filtered = repository.search_records(RecordFilters(start_date="2024-01-01", include_missing_event_ids=False))
        assert len(filtered) == 2
        assert repository.summary_metrics()["unique_event_count"] == 1
        assert repository.summary_metrics()["missing_event_id_count"] == 1
        assert repository.data_completeness()["missing_event_id"] == 1
    finally:
        repository.close()


def test_event_detail_groups_product_records(database_path: Path) -> None:
    """Event details intentionally group multiple product-record rows."""
    repository = RecallRepository(database_path)
    try:
        assert len(repository.event_detail("E-1")) == 2
        assert repository.event_detail("missing") == []
    finally:
        repository.close()


def test_allowlists_and_bound_values_block_sql_injection(database_path: Path) -> None:
    """User text remains values; dimensions and sorts are enums, not raw SQL paths."""
    repository = RecallRepository(database_path)
    try:
        injected = repository.search_records(RecordFilters(classifications=("Class I'); DROP TABLE recall_records;--",)))
        assert injected == []
        assert repository.summary_metrics()["product_record_count"] == 3
        with pytest.raises(ValueError):
            CategoryDimension("state; DROP TABLE recall_records")
        with pytest.raises(ValueError):
            SortOption("report_date DESC")
    finally:
        repository.close()


def test_empty_filters_aggregations_and_row_limits(database_path: Path) -> None:
    """Empty filters are valid and result-size requests are safely capped."""
    repository = RecallRepository(database_path)
    try:
        assert len(repository.search_records(limit=10_000)) == 3
        assert MAX_RESULT_ROWS == 200
        assert repository.time_series()[0]["period"] == "2023-02"
        assert repository.categorical_aggregation(CategoryDimension.TAG_VALUE)
        assert repository.segment_comparison(CategoryDimension.STATE)
        with pytest.raises(ValueError, match="limit"):
            repository.search_records(limit=0)
    finally:
        repository.close()


def test_atomic_rebuild_preserves_prior_database_on_failure(database_path: Path) -> None:
    """A failed replacement leaves the previously validated target queryable."""
    record = _normalized(recall_number="F-NEW", event_id="E-9")
    with pytest.raises(sqlite3.IntegrityError):
        build_database([record, record], database_path)
    repository = RecallRepository(database_path)
    try:
        assert repository.summary_metrics()["product_record_count"] == 3
    finally:
        repository.close()
