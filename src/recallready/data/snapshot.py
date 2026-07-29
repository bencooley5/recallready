"""Staged Parquet snapshot writing and atomic refresh orchestration."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from recallready.data.normalize import NormalizedFoodEnforcementRecord, normalize_record
from recallready.data.validation import ValidationReport, validate_records
from recallready.db.build import BuildMetadata, build_database
from recallready.db.schema import SCHEMA_VERSION
from recallready.models import FoodEnforcementRecord, SourceFoodEnforcementRecord


def refresh_snapshot(
    records: list[NormalizedFoodEnforcementRecord], output_dir: Path, *, source_last_updated: str | None,
    source_total_matches: int | None, force: bool = False, dry_run: bool = False, skip_database_build: bool = False
) -> tuple[dict[str, object], ValidationReport]:
    """Stage snapshot, report, metadata, and SQLite; promote only after validation succeeds."""
    output_dir.mkdir(parents=True, exist_ok=True)
    prior_metadata = _read_json(output_dir / "snapshot_metadata.json")
    report = validate_records(records, prior_metadata=prior_metadata, force=force)
    if not report.passed:
        raise ValueError(f"Snapshot validation failed: {', '.join(report.errors)}")
    started_at = _timestamp()
    with tempfile.TemporaryDirectory(dir=output_dir) as stage_directory:
        stage = Path(stage_directory)
        snapshot_path = stage / "recalls.parquet"
        _write_parquet(records, snapshot_path)
        metadata = _metadata(records, snapshot_path, source_last_updated, source_total_matches, started_at, report)
        (stage / "snapshot_metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
        (stage / "validation_report.json").write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
        if not skip_database_build:
            build_database(records, stage / "recallready.sqlite", BuildMetadata(source_last_updated, source_total_matches))
        if not dry_run:
            for name in ("recalls.parquet", "snapshot_metadata.json", "validation_report.json", "recallready.sqlite"):
                candidate = stage / name
                if candidate.exists():
                    os.replace(candidate, output_dir / name)
    return metadata, report


def _write_parquet(records: list[NormalizedFoodEnforcementRecord], path: Path) -> None:
    rows = [
        {
            "source_record_id": record.source_record_id, "recall_number": record.recall_number,
            "event_id": record.event_id, "report_date": record.report_date, "product_description": record.product_description,
            "reason_for_recall": record.reason_for_recall, "firm_normalized": record.firm_normalized,
            "product_category": record.product_category.primary_category, "primary_hazard": record.hazard.primary_hazard,
            "taxonomy_version": record.hazard.taxonomy_version, "raw_json": json.dumps(record.raw, sort_keys=True),
        }
        for record in records
    ]
    pl.DataFrame(rows).write_parquet(path, compression="zstd")


def build_runtime_database(snapshot_path: Path, target_path: Path) -> None:
    """Rebuild a disposable SQLite database from the committed public snapshot."""
    rows = pl.read_parquet(snapshot_path).to_dicts()
    records = []
    for row in rows:
        raw = json.loads(str(row["raw_json"]))
        source = SourceFoodEnforcementRecord(
            parsed=FoodEnforcementRecord.model_validate(raw), raw=raw
        )
        records.append(normalize_record(source))
    build_database(records, target_path)


def _metadata(records: list[NormalizedFoodEnforcementRecord], snapshot: Path, last_updated: str | None, total_matches: int | None, started_at: str, report: ValidationReport) -> dict[str, object]:
    dates = [record.report_date for record in records if record.report_date]
    return {
        "source_name": "openFDA food enforcement", "source_endpoint": "https://api.fda.gov/food/enforcement.json",
        "source_last_updated": last_updated, "ingestion_started_at": started_at, "ingestion_completed_at": _timestamp(),
        "raw_record_count": len(records), "normalized_record_count": len(records),
        "unique_recall_numbers": len({r.recall_number for r in records if r.recall_number}),
        "unique_events_with_non_null_event_id": report.unique_event_count,
        "records_lacking_event_id": report.records_lacking_event_id,
        "date_coverage_start": min(dates).isoformat() if dates else None,
        "date_coverage_end": max(dates).isoformat() if dates else None,
        "taxonomy_versions": sorted({r.hazard.taxonomy_version for r in records}),
        "schema_version": SCHEMA_VERSION, "code_commit": _git_commit(),
        "sha256": _sha256(snapshot), "source_total_matches": total_matches,
    }


def _read_json(path: Path) -> dict[str, object] | None:
    return json.loads(path.read_text()) if path.exists() else None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _git_commit() -> str | None:
    result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    return result.stdout.strip() or None
