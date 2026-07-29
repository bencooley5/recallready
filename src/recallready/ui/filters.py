"""Safe UI filter state and translation to trusted repository filters."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from recallready.db.repository import RecordFilters


@dataclass(frozen=True, slots=True)
class FilterState:
    start_date: date | None = None
    end_date: date | None = None
    classifications: tuple[str, ...] = ()
    product_categories: tuple[str, ...] = ()
    firm_states: tuple[str, ...] = ()
    keyword: str = ""
    date_basis: str = "report_date"

def to_record_filters(state: FilterState) -> RecordFilters:
    """Translate typed UI values into trusted repository filter values."""
    return RecordFilters(
        start_date=state.start_date.isoformat() if state.start_date else None,
        end_date=state.end_date.isoformat() if state.end_date else None,
        classifications=state.classifications,
        product_categories=state.product_categories,
        states=state.firm_states,
    )


def to_query_params(state: FilterState) -> dict[str, str]:
    """Create a bounded, secret-free shareable filter representation."""
    values: dict[str, str] = {"basis": state.date_basis}
    for key, value in (("start", state.start_date), ("end", state.end_date)):
        if value:
            values[key] = value.isoformat()
    if state.classifications:
        values["classification"] = ",".join(state.classifications)
    if state.product_categories:
        values["category"] = ",".join(state.product_categories)
    if state.firm_states:
        values["firm_state"] = ",".join(state.firm_states)
    return values


def from_query_params(values: dict[str, str]) -> FilterState:
    """Parse only valid bounded filter values; discard free text and malformed dates."""
    def parsed_date(key: str) -> date | None:
        try:
            return date.fromisoformat(values[key]) if key in values else None
        except ValueError:
            return None
    def split(key: str) -> tuple[str, ...]:
        return tuple(item for item in values.get(key, "").split(",") if item and len(item) <= 80)[:20]
    basis = values.get("basis", "report_date")
    return FilterState(parsed_date("start"), parsed_date("end"), split("classification"), split("category"), split("firm_state"), "", basis if basis in {"report_date", "recall_initiation_date"} else "report_date")
