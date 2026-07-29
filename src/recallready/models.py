"""Typed source and domain models shared across RecallReady phases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ConfigDict

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonMapping = dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class SnapshotMetadata:
    """Immutable provenance metadata for a future historical snapshot."""

    snapshot_id: str
    source_last_checked_at_utc: datetime
    record_count: int


class FoodEnforcementRecord(BaseModel):
    """Known fields of one openFDA food enforcement result.

    API records are intentionally permissive: absent historical fields stay ``None`` and
    newly introduced fields are retained as Pydantic extras. The client separately retains
    the exact JSON-compatible source mapping for audit and future transformations.
    """

    model_config = ConfigDict(extra="allow")

    address_1: str | None = None
    address_2: str | None = None
    center_classification_date: str | None = None
    city: str | None = None
    classification: str | None = None
    code_info: str | None = None
    country: str | None = None
    distribution_pattern: str | None = None
    event_id: str | None = None
    initial_firm_notification: str | None = None
    more_code_info: str | None = None
    openfda: dict[str, object] | None = None
    product_code: str | None = None
    product_description: str | None = None
    product_quantity: str | None = None
    product_type: str | None = None
    reason_for_recall: str | None = None
    recall_initiation_date: str | None = None
    recall_number: str | None = None
    recalling_firm: str | None = None
    report_date: str | None = None
    state: str | None = None
    status: str | None = None
    termination_date: str | None = None
    voluntary_mandated: str | None = None


class OpenFDAResultMetadata(BaseModel):
    """Optional result metadata supplied by openFDA."""

    model_config = ConfigDict(extra="allow")

    total: int | None = None
    skip: int | None = None
    limit: int | None = None


class OpenFDAMetadata(BaseModel):
    """Optional envelope metadata supplied by openFDA."""

    model_config = ConfigDict(extra="allow")

    last_updated: str | None = None
    results: OpenFDAResultMetadata | None = None

    @property
    def total_matches(self) -> int | None:
        """Return API-reported total matches when it is supplied."""
        return self.results.total if self.results is not None else None


@dataclass(frozen=True, slots=True)
class SourceFoodEnforcementRecord:
    """A typed record paired with its unmodified JSON-compatible source mapping."""

    parsed: FoodEnforcementRecord
    raw: JsonMapping
