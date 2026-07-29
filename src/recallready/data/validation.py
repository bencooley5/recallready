"""Deterministic snapshot quality checks and machine-readable reporting."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date

from recallready.data.normalize import NormalizedFoodEnforcementRecord


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Snapshot validation result that retains warnings without dropping records."""

    passed: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    classification_counts: dict[str, int]
    pre_2012_missing_event_ids: int
    product_record_count: int
    unique_event_count: int
    records_lacking_event_id: int

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-ready report."""
        return asdict(self)


def validate_records(
    records: list[NormalizedFoodEnforcementRecord], *, prior_metadata: dict[str, object] | None = None, force: bool = False
) -> ValidationReport:
    """Validate identity, completeness, coverage, and event-grain expectations."""
    errors: list[str] = []
    warnings: list[str] = []
    ids = [record.source_record_id for record in records]
    if len(ids) != len(set(ids)):
        errors.append("duplicate_source_record_id")
    total = len(records)
    for name, values in (("product_description", [r.product_description for r in records]), ("reason_for_recall", [r.reason_for_recall for r in records])):
        if total and sum(value is not None and value != "" for value in values) / total < 0.5:
            errors.append(f"completeness_below_threshold:{name}")
    coverage = [record.report_date for record in records if record.report_date is not None]
    prior_start = _date_value(prior_metadata, "date_coverage_start")
    if prior_start and coverage and min(coverage) > prior_start and not force:
        errors.append("date_coverage_unexpectedly_shrunk")
    prior_count = _int_value(prior_metadata, "normalized_record_count")
    if prior_count and total < prior_count and not force:
        errors.append("row_count_unexpectedly_fell")
    classifications: dict[str, int] = {}
    for record in records:
        value = record.raw.get("classification")
        key = value if isinstance(value, str) and value else "<missing>"
        classifications[key] = classifications.get(key, 0) + 1
    if "<missing>" in classifications:
        warnings.append("classification_missing_values_retained")
    missing_events = sum(record.event_id is None or record.event_id == "" for record in records)
    pre_2012 = sum(
        (record.report_date is not None and record.report_date.year < 2012 and not record.event_id)
        for record in records
    )
    if pre_2012:
        warnings.append("pre_2012_missing_event_ids_reported")
    events = {record.event_id for record in records if record.event_id}
    return ValidationReport(
        passed=not errors, errors=tuple(errors), warnings=tuple(warnings),
        classification_counts=classifications, pre_2012_missing_event_ids=pre_2012,
        product_record_count=total, unique_event_count=len(events), records_lacking_event_id=missing_events,
    )


def _date_value(metadata: dict[str, object] | None, key: str) -> date | None:
    value = metadata.get(key) if metadata else None
    return date.fromisoformat(value) if isinstance(value, str) else None


def _int_value(metadata: dict[str, object] | None, key: str) -> int | None:
    value = metadata.get(key) if metadata else None
    return value if isinstance(value, int) else None
