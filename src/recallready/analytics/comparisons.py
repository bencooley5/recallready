"""Transparent comparison helpers with a small-baseline safeguard."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_MIN_PERCENT_BASELINE = 10
"""Minimum prior product-record count required to state a percentage change."""


@dataclass(frozen=True, slots=True)
class PeriodComparison:
    """A descriptive comparison between two visible time periods."""

    prior_count: int
    current_count: int
    absolute_difference: int
    percentage_difference: float | None
    percentage_suppressed: bool


def compare_counts(
    prior_count: int,
    current_count: int,
    *,
    min_percent_baseline: int = DEFAULT_MIN_PERCENT_BASELINE,
) -> PeriodComparison:
    """Compare counts, suppressing unstable percentages below the threshold."""
    if min_percent_baseline < 1:
        raise ValueError("min_percent_baseline must be positive")
    absolute_difference = current_count - prior_count
    percentage_difference = (
        None if prior_count < min_percent_baseline else absolute_difference / prior_count
    )
    return PeriodComparison(
        prior_count=prior_count,
        current_count=current_count,
        absolute_difference=absolute_difference,
        percentage_difference=percentage_difference,
        percentage_suppressed=percentage_difference is None,
    )


def mix_shift(
    prior_share: float,
    current_share: float,
    *,
    material_percentage_points: float = 0.10,
) -> float | None:
    """Return a material percentage-point shift, otherwise ``None``."""
    difference = current_share - prior_share
    return difference if abs(difference) >= material_percentage_points else None
