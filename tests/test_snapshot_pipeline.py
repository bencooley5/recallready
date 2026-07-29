"""Fixture-only integration tests for snapshot staging and validation."""

from __future__ import annotations

import json
from pathlib import Path

from recallready.data.normalize import normalize_record
from recallready.data.snapshot import refresh_snapshot
from recallready.models import FoodEnforcementRecord, SourceFoodEnforcementRecord


def test_fixture_pipeline_writes_validated_snapshot_and_database(tmp_path: Path) -> None:
    """Recorded fixture rows run end-to-end without an HTTP request."""
    raw_rows = json.loads((Path(__file__).parent / "fixtures" / "normalization_records.json").read_text())
    records = [
        normalize_record(SourceFoodEnforcementRecord(FoodEnforcementRecord.model_validate(raw), raw))
        for raw in raw_rows
    ]
    metadata, report = refresh_snapshot(records, tmp_path, source_last_updated="2026-01-01", source_total_matches=2)

    assert report.passed
    assert metadata["normalized_record_count"] == 2
    assert (tmp_path / "recalls.parquet").exists()
    assert (tmp_path / "recallready.sqlite").exists()
    assert json.loads((tmp_path / "validation_report.json").read_text())["passed"] is True


def test_dry_run_does_not_promote_artifacts(tmp_path: Path) -> None:
    """Dry runs validate staged artifacts while leaving the output directory untouched."""
    raw = {"recall_number": "F-1", "event_id": "E-1", "report_date": "20240101", "product_description": "Bread", "reason_for_recall": "Glass"}
    record = normalize_record(SourceFoodEnforcementRecord(FoodEnforcementRecord.model_validate(raw), raw))
    _, report = refresh_snapshot([record], tmp_path, source_last_updated=None, source_total_matches=1, dry_run=True)

    assert report.passed
    assert not (tmp_path / "food_enforcement.parquet").exists()
