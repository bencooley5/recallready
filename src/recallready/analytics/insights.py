"""Template-based executive findings and Markdown briefs."""

from __future__ import annotations

from calendar import monthrange
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from recallready.analytics.comparisons import (
    DEFAULT_MIN_PERCENT_BASELINE,
    compare_counts,
    mix_shift,
)
from recallready.analytics.metrics import (
    category_shares,
    median_reporting_lag,
    recurring_hazard_product_combinations,
)


@dataclass(frozen=True, slots=True)
class InsightBundle:
    """Rendered deterministic statements plus the reproducible Markdown brief."""

    statements: tuple[str, ...]
    markdown: str


def generate_insights(
    *,
    scope: str,
    date_basis: str,
    summary: Mapping[str, object],
    time_series: Sequence[Mapping[str, object]],
    classifications: Sequence[Mapping[str, object]],
    hazards: Sequence[Mapping[str, object]],
    product_categories: Sequence[Mapping[str, object]],
    records: Sequence[Mapping[str, object]],
    classification_period_mix: Sequence[Mapping[str, object]] = (),
    hazard_period_mix: Sequence[Mapping[str, object]] = (),
    completeness: Mapping[str, object],
    snapshot_metadata: Mapping[str, object] | None = None,
    min_percent_baseline: int = DEFAULT_MIN_PERCENT_BASELINE,
) -> InsightBundle:
    """Generate conservative descriptive insights from trusted query results only."""
    total = _int(summary, "product_record_count")
    events = _int(summary, "unique_event_count")
    missing_events = _int(summary, "missing_event_id_count", _int(completeness, "missing_event_id"))
    statements: list[str] = []
    category_rows = category_shares(product_categories, total_records=total)
    hazard_rows = category_shares(hazards, total_records=total)
    classification_rows = category_shares(classifications, total_records=total)
    completed_time_series, partial_period = _completed_periods(
        time_series, snapshot_metadata
    )
    completed_classification_mix, _ = _completed_periods(
        classification_period_mix, snapshot_metadata
    )
    completed_hazard_mix, _ = _completed_periods(hazard_period_mix, snapshot_metadata)

    if total == 0:
        statements.append(
            "No historical enforcement records match the selected filter scope; no descriptive finding is produced."
        )
    else:
        _append_largest(statements, category_rows, "derived product category")
        _append_largest(statements, hazard_rows, "derived taxonomy tag")
        if partial_period:
            statements.append(
                f"Partial source month {partial_period} is shown in charts but excluded from period-over-period insight comparisons."
            )
        _append_period_change(statements, completed_time_series, min_percent_baseline)
        _append_material_mix_shift(
            statements, completed_classification_mix, "classification"
        )
        _append_material_mix_shift(statements, completed_hazard_mix, "derived hazard")
        _append_combinations(statements, records)
        _append_lag(statements, records)
        _append_completeness(statements, total, missing_events, completeness)

    markdown = _render_markdown(
        scope=scope,
        date_basis=date_basis,
        total=total,
        events=events,
        missing_events=missing_events,
        statements=statements,
        categories=category_rows,
        classifications=classification_rows,
        snapshot_metadata=snapshot_metadata,
        min_percent_baseline=min_percent_baseline,
    )
    return InsightBundle(statements=tuple(statements), markdown=markdown)


def _completed_periods(
    rows: Sequence[Mapping[str, object]],
    snapshot_metadata: Mapping[str, object] | None,
) -> tuple[list[Mapping[str, object]], str | None]:
    """Exclude the source's incomplete final month from comparative statements."""
    raw_updated = (snapshot_metadata or {}).get("source_last_updated")
    if not isinstance(raw_updated, str):
        return list(rows), None
    try:
        updated = date.fromisoformat(raw_updated[:10])
    except ValueError:
        return list(rows), None
    if updated.day == monthrange(updated.year, updated.month)[1]:
        return list(rows), None
    partial = updated.strftime("%Y-%m")
    if not any(row.get("period") == partial for row in rows):
        return list(rows), None
    return [row for row in rows if row.get("period") != partial], partial


def _append_largest(
    statements: list[str], rows: Sequence[Mapping[str, object]], label: str
) -> None:
    if not rows:
        return
    row = rows[0]
    share = _float(row.get("share"))
    count = _int(row, "product_record_count")
    value = _text(row, "value", "unknown")
    statements.append(
        f"Largest {label}: {value} ({count} product records; {share:.1%} of selected records)."
    )


def _append_period_change(
    statements: list[str], time_series: Sequence[Mapping[str, object]], min_percent_baseline: int
) -> None:
    usable = [
        row
        for row in time_series
        if isinstance(row.get("product_record_count"), int) and isinstance(row.get("period"), str)
    ]
    if len(usable) < 2:
        return
    prior, current = usable[-2:]
    comparison = compare_counts(
        _int(prior, "product_record_count"),
        _int(current, "product_record_count"),
        min_percent_baseline=min_percent_baseline,
    )
    direction = "+" if comparison.absolute_difference >= 0 else ""
    current_period = _text(current, "period", "unknown")
    prior_period = _text(prior, "period", "unknown")
    statement = (
        f"Latest visible period ({current_period}) versus {prior_period}: "
        f"{direction}{comparison.absolute_difference} product records."
    )
    if comparison.percentage_difference is None:
        statement += f" Percentage change is suppressed because the prior period has fewer than {min_percent_baseline} product records."
    else:
        statement += f" ({comparison.percentage_difference:+.1%})."
    statements.append(statement)


def _append_material_mix_shift(
    statements: list[str], rows: Sequence[Mapping[str, object]], label: str
) -> None:
    periods = sorted({period for row in rows if isinstance((period := row.get("period")), str)})
    if len(periods) < 2:
        return
    prior_period, current_period = periods[-2:]
    prior = _mix_by_value(rows, prior_period)
    current = _mix_by_value(rows, current_period)
    prior_total = sum(prior.values())
    current_total = sum(current.values())
    if not prior_total or not current_total:
        return
    shifts = [
        (value, mix_shift(prior.get(value, 0) / prior_total, count / current_total))
        for value, count in current.items()
    ]
    material = [(value, shift) for value, shift in shifts if shift is not None]
    if not material:
        return
    value, shift = sorted(
        material,
        key=lambda item: (-round(abs(_float(item[1])), 12), item[0]),
    )[0]
    shift_value = _float(shift)
    direction = "increased" if shift_value > 0 else "decreased"
    statements.append(
        f"Material {label} mix shift in the latest visible period: {value} {direction} by "
        f"{abs(shift_value) * 100:.1f} percentage points versus {prior_period}."
    )


def _append_combinations(statements: list[str], records: Sequence[Mapping[str, object]]) -> None:
    combinations = recurring_hazard_product_combinations(records)
    if not combinations:
        return
    top = combinations[0]
    if _int(top, "product_record_count") > 1:
        statements.append(
            "Most frequent observed derived hazard/product combination in the retrieved detail rows: "
            f"{top['primary_hazard']} / {top['derived_product_category']} ({top['product_record_count']} product records)."
        )


def _mix_by_value(rows: Sequence[Mapping[str, object]], period: str) -> dict[str, int]:
    values: dict[str, int] = {}
    for row in rows:
        value = row.get("value")
        count = row.get("product_record_count")
        if row.get("period") == period and isinstance(value, str) and isinstance(count, int):
            values[value] = count
    return values


def _append_lag(statements: list[str], records: Sequence[Mapping[str, object]]) -> None:
    lag = median_reporting_lag(records)
    if lag is not None:
        statements.append(
            f"Median reporting lag among retrieved records with both valid dates: {lag:g} days."
        )


def _append_completeness(
    statements: list[str], total: int, missing_events: int, completeness: Mapping[str, object]
) -> None:
    missing_description = _int(completeness, "missing_product_description")
    missing_reason = _int(completeness, "missing_reason_for_recall")
    caveats: list[str] = []
    if missing_events:
        caveats.append(
            f"{missing_events} records lack an event ID and are excluded from known-event counts"
        )
    if missing_description:
        caveats.append(f"{missing_description} records lack a product description")
    if missing_reason:
        caveats.append(f"{missing_reason} records lack a recall reason")
    if caveats:
        statements.append("Data coverage caveat: " + "; ".join(caveats) + ".")
    elif total:
        statements.append(
            "Data coverage: selected records contain event IDs, product descriptions, and recall reasons in the queried completeness fields."
        )


def _render_markdown(
    *,
    scope: str,
    date_basis: str,
    total: int,
    events: int,
    missing_events: int,
    statements: Sequence[str],
    categories: Sequence[Mapping[str, object]],
    classifications: Sequence[Mapping[str, object]],
    snapshot_metadata: Mapping[str, object] | None,
    min_percent_baseline: int,
) -> str:
    freshness = _metadata_value(snapshot_metadata, "source_last_updated", "Not available")
    ingested_at = _metadata_value(snapshot_metadata, "ingestion_completed_at", "Not available")
    lines = [
        "# RecallReady executive brief",
        "",
        "Historical openFDA food enforcement records for informational analysis; not an alert feed or current safety determination.",
        "",
        "## Scope and source",
        "",
        f"- Filter scope: {scope}",
        f"- Date basis: {date_basis}",
        f"- Product-record count: {total}",
        f"- Known unique-event count: {events}",
        f"- Records without event ID: {missing_events}",
        f"- Source last updated: {freshness}",
        f"- Snapshot ingestion completed: {ingested_at}",
        "",
        "## Deterministic descriptive findings",
        "",
    ]
    lines.extend(f"- {statement}" for statement in statements)
    lines.extend(
        [
            "",
            "## Summary tables",
            "",
            "### Derived product categories",
            "",
            "| Category | Product records | Share |",
            "| --- | ---: | ---: |",
        ]
    )
    lines.extend(
        f"| {_text(row, 'value', 'unknown')} | {_int(row, 'product_record_count')} | {_float(row.get('share')):.1%} |"
        for row in categories[:10]
    )
    lines.extend(
        [
            "",
            "### Classification",
            "",
            "| Classification | Product records | Share |",
            "| --- | ---: | ---: |",
        ]
    )
    lines.extend(
        f"| {_text(row, 'value', 'unknown')} | {_int(row, 'product_record_count')} | {_float(row.get('share')):.1%} |"
        for row in classifications[:10]
    )
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- Counts are historical product-record and known-event counts, not incidence rates; market-volume denominators are unavailable.",
            "- Derived taxonomy labels are transparent rules over unstructured source text and can miss or over-tag records.",
            "- Missing source values, including fields frequently unavailable before June 2012, remain missing.",
            f"- Percentage changes are suppressed when the prior period has fewer than {min_percent_baseline} product records.",
            "- Findings are descriptive only and do not establish causation, current recall lifecycle, or product safety.",
        ]
    )
    return "\n".join(lines) + "\n"


def _int(values: Mapping[str, object], key: str, default: int = 0) -> int:
    value = values.get(key, default)
    return value if isinstance(value, int) else default


def _metadata_value(metadata: Mapping[str, object] | None, key: str, default: str) -> str:
    if metadata is None:
        return default
    value = metadata.get(key)
    return str(value) if value not in (None, "") else default


def _float(value: object) -> float:
    """Return a numeric computed value without coercing untrusted text."""
    return float(value) if isinstance(value, int | float) else 0.0


def _text(values: Mapping[str, object], key: str, default: str) -> str:
    """Return a text value while preserving a safe display fallback."""
    value = values.get(key)
    return value if isinstance(value, str) else default
