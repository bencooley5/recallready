"""Pure descriptive metric helpers for deterministic executive insights."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from statistics import median


def category_shares(
    rows: Iterable[Mapping[str, object]],
    *,
    total_records: int,
) -> list[dict[str, object]]:
    """Return deterministic category shares from trusted aggregation rows."""
    if total_records <= 0:
        return []
    values: list[dict[str, object]] = []
    for row in rows:
        label = row.get("value")
        count = row.get("product_record_count")
        if not isinstance(label, str) or not isinstance(count, int) or count < 0:
            continue
        values.append(
            {
                "value": label,
                "product_record_count": count,
                "share": count / total_records,
            }
        )
    return sorted(
        values,
        key=lambda item: (-_int_value(item["product_record_count"]), str(item["value"])),
    )


def median_reporting_lag(records: Iterable[Mapping[str, object]]) -> float | None:
    """Return the median available reporting lag, preserving missing values."""
    values = [
        value
        for record in records
        if isinstance((value := record.get("reporting_lag_days")), int | float)
    ]
    return float(median(values)) if values else None


def recurring_hazard_product_combinations(
    records: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Count observed derived hazard/product pairs; no causal inference is made."""
    combinations: Counter[tuple[str, str]] = Counter()
    for record in records:
        hazard = record.get("primary_hazard")
        category = record.get("derived_product_category")
        if isinstance(hazard, str) and hazard and isinstance(category, str) and category:
            combinations[(hazard, category)] += 1
    return [
        {
            "primary_hazard": hazard,
            "derived_product_category": category,
            "product_record_count": count,
        }
        for (hazard, category), count in sorted(
            combinations.items(), key=lambda item: (-item[1], item[0][0], item[0][1])
        )
    ]


def _int_value(value: object) -> int:
    """Return an already validated integer for a typed sort key."""
    return value if isinstance(value, int) else 0
