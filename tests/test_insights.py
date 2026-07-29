"""Fixed-output tests for deterministic executive insight templates."""

from __future__ import annotations

from recallready.analytics.insights import generate_insights


def _bundle(**overrides: object):
    values: dict[str, object] = {
        "scope": "date basis: report_date; classification: Class I",
        "date_basis": "report_date",
        "summary": {
            "product_record_count": 20,
            "unique_event_count": 12,
            "missing_event_id_count": 2,
        },
        "time_series": [
            {"period": "2024-01", "product_record_count": 10},
            {"period": "2024-02", "product_record_count": 15},
        ],
        "classifications": [{"value": "Class I", "product_record_count": 12}],
        "hazards": [{"value": "pathogen_contamination", "product_record_count": 11}],
        "product_categories": [{"value": "produce", "product_record_count": 12}],
        "records": [
            {
                "primary_hazard": "pathogen_contamination",
                "derived_product_category": "produce",
                "reporting_lag_days": 4,
            },
            {
                "primary_hazard": "pathogen_contamination",
                "derived_product_category": "produce",
                "reporting_lag_days": 8,
            },
        ],
        "classification_period_mix": [
            {"period": "2024-01", "value": "Class I", "product_record_count": 2},
            {"period": "2024-01", "value": "Class II", "product_record_count": 8},
            {"period": "2024-02", "value": "Class I", "product_record_count": 10},
            {"period": "2024-02", "value": "Class II", "product_record_count": 5},
        ],
        "hazard_period_mix": [],
        "completeness": {
            "missing_event_id": 2,
            "missing_product_description": 1,
            "missing_reason_for_recall": 0,
        },
        "snapshot_metadata": {
            "source_last_updated": "2024-03-01",
            "ingestion_completed_at": "2024-03-02T00:00:00+00:00",
        },
    }
    values.update(overrides)
    return generate_insights(**values)  # type: ignore[arg-type]


def test_insights_include_fixed_descriptive_statements_and_markdown_scope() -> None:
    bundle = _bundle()

    assert (
        "Largest derived product category: produce (12 product records; 60.0% of selected records)."
        in bundle.statements
    )
    assert (
        "Latest visible period (2024-02) versus 2024-01: +5 product records. (+50.0%)."
        in bundle.statements
    )
    assert (
        "Material classification mix shift in the latest visible period: Class I increased by 46.7 percentage points versus 2024-01."
        in bundle.statements
    )
    assert (
        "Median reporting lag among retrieved records with both valid dates: 6 days."
        in bundle.statements
    )
    assert "Filter scope: date basis: report_date; classification: Class I" in bundle.markdown
    assert "Source last updated: 2024-03-01" in bundle.markdown


def test_zero_baseline_suppresses_percentage_change() -> None:
    bundle = _bundle(
        time_series=[
            {"period": "2024-01", "product_record_count": 0},
            {"period": "2024-02", "product_record_count": 4},
        ]
    )

    assert any(
        "Latest visible period (2024-02) versus 2024-01: +4 product records." in statement
        for statement in bundle.statements
    )
    assert any(
        "Percentage change is suppressed because the prior period has fewer than 10 product records."
        in statement
        for statement in bundle.statements
    )
    assert "+inf" not in bundle.markdown


def test_small_baseline_suppresses_unstable_percentage_change() -> None:
    bundle = _bundle(
        time_series=[
            {"period": "2024-01", "product_record_count": 9},
            {"period": "2024-02", "product_record_count": 18},
        ]
    )

    assert any(
        "Percentage change is suppressed because the prior period has fewer than 10 product records."
        in statement
        for statement in bundle.statements
    )
    assert "+100.0%" not in bundle.markdown


def test_missing_event_ids_and_dates_are_caveated_without_invention() -> None:
    bundle = _bundle(
        records=[{"reporting_lag_days": None}],
        completeness={
            "missing_event_id": 2,
            "missing_product_description": 1,
            "missing_reason_for_recall": 3,
        },
    )

    assert not any(statement.startswith("Median reporting lag") for statement in bundle.statements)
    assert (
        "2 records lack an event ID and are excluded from known-event counts"
        in bundle.statements[-1]
    )
    assert "3 records lack a recall reason" in bundle.statements[-1]


def test_empty_results_have_no_descriptive_finding() -> None:
    bundle = _bundle(
        summary={"product_record_count": 0, "unique_event_count": 0, "missing_event_id_count": 0},
        time_series=[],
        classifications=[],
        hazards=[],
        product_categories=[],
        records=[],
        completeness={},
    )

    assert bundle.statements == (
        "No historical enforcement records match the selected filter scope; no descriptive finding is produced.",
    )
    assert "Product-record count: 0" in bundle.markdown


def test_partial_source_month_is_excluded_from_comparisons() -> None:
    bundle = _bundle(
        time_series=[
            {"period": "2024-01", "product_record_count": 10},
            {"period": "2024-02", "product_record_count": 20},
            {"period": "2024-03", "product_record_count": 2},
        ],
        snapshot_metadata={"source_last_updated": "2024-03-12"},
    )
    assert any("Partial source month 2024-03" in item for item in bundle.statements)
    assert any("2024-02) versus 2024-01" in item for item in bundle.statements)
    assert not any("versus 2024-02: -18" in item for item in bundle.statements)
