"""Atomic construction of the derived SQLite database from normalized records."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from recallready.data.normalize import NormalizedFoodEnforcementRecord
from recallready.db.schema import SCHEMA_SQL, SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class BuildMetadata:
    """Provenance saved alongside one immutable query-database build."""

    source_last_updated: str | None = None
    source_total_matches: int | None = None
    code_version: str = "0.1.0"


def build_database(
    records: Iterable[NormalizedFoodEnforcementRecord], target_path: Path, metadata: BuildMetadata | None = None
) -> None:
    """Build, validate, and atomically replace a SQLite database without touching source data."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = target_path.with_name(f".{target_path.name}.{uuid.uuid4().hex}.tmp")
    build_metadata = metadata or BuildMetadata()
    started_at = _timestamp()
    try:
        connection = sqlite3.connect(temporary_path)
        try:
            connection.executescript(SCHEMA_SQL)
            connection.execute("PRAGMA foreign_keys = ON")
            record_count, tag_count = _insert_records(connection, records, build_metadata)
            completed_at = _timestamp()
            connection.execute(
                "INSERT INTO ingestion_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    uuid.uuid4().hex,
                    started_at,
                    completed_at,
                    "openFDA",
                    build_metadata.source_last_updated,
                    build_metadata.source_total_matches,
                    record_count,
                    tag_count,
                    "passed",
                    build_metadata.code_version,
                    SCHEMA_VERSION,
                ),
            )
            _validate_database(connection, record_count)
            connection.commit()
        finally:
            connection.close()
        os.replace(temporary_path, target_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _insert_records(
    connection: sqlite3.Connection,
    records: Iterable[NormalizedFoodEnforcementRecord],
    metadata: BuildMetadata,
) -> tuple[int, int]:
    record_count = 0
    tag_count = 0
    for record in records:
        raw = record.raw
        connection.execute(
            """INSERT INTO recall_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.source_record_id, "openFDA", record.recall_number, record.event_id,
                _iso(record.report_date), _iso(record.recall_initiation_date), _iso(record.center_classification_date),
                _iso(record.termination_date), _text(raw, "classification"), _text(raw, "status"),
                record.recalling_firm, record.firm_normalized, _text(raw, "city"), _text(raw, "state"),
                _text(raw, "country"), record.product_description, _text(raw, "product_quantity"),
                _text(raw, "product_code"), _text(raw, "code_info"), record.reason_for_recall,
                _text(raw, "distribution_pattern"), _text(raw, "initial_firm_notification"),
                _text(raw, "voluntary_mandated"), _text(raw, "product_type"), record.reporting_lag_days,
                record.product_category.primary_category, json.dumps(record.raw, sort_keys=True),
                metadata.source_last_updated or (record.source_metadata.last_updated if record.source_metadata else None),
                _timestamp(),
            ),
        )
        record_count += 1
        for tag in record.hazard.tags:
            connection.execute(
                "INSERT INTO recall_tags VALUES (?, ?, ?, ?, ?, ?)",
                (record.source_record_id, tag.tag_type, tag.tag_value, tag.rule_id, record.hazard.confidence, record.hazard.taxonomy_version),
            )
            tag_count += 1
    return record_count, tag_count


def _validate_database(connection: sqlite3.Connection, expected_records: int) -> None:
    count = connection.execute("SELECT COUNT(*) FROM recall_records").fetchone()[0]
    fts_count = connection.execute("SELECT COUNT(*) FROM recall_records_fts").fetchone()[0]
    if count != expected_records or fts_count != expected_records:
        raise RuntimeError("SQLite build validation failed: FTS is not synchronized")
    foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
    if foreign_key_errors:
        raise RuntimeError("SQLite build validation failed: foreign key violation")


def _text(raw: Mapping[str, object], key: str) -> str | None:
    value = raw.get(key)
    return value if isinstance(value, str) else None


def _iso(value: object) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()
