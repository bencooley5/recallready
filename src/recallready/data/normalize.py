"""Deterministic normalization that keeps FDA source evidence intact."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime

from recallready.data.taxonomy import (
    HazardClassification,
    ProductCategoryClassification,
    load_hazard_taxonomy,
    load_product_category_taxonomy,
)
from recallready.models import JsonMapping, OpenFDAMetadata, SourceFoodEnforcementRecord

NORMALIZATION_VERSION = "1.0.0"
LEGAL_SUFFIXES = frozenset(
    {
        "inc",
        "incorporated",
        "llc",
        "l l c",
        "ltd",
        "limited",
        "corp",
        "corporation",
        "co",
        "company",
    }
)
_WHITESPACE_PATTERN = re.compile(r"\s+")
_PUNCTUATION_PATTERN = re.compile(r"[^\w\s]")


@dataclass(frozen=True, slots=True)
class NormalizedFoodEnforcementRecord:
    """Source-preserving normalized record ready for a later storage phase."""

    source_record_id: str
    normalization_version: str
    recall_number: str | None
    event_id: str | None
    source_metadata: OpenFDAMetadata | None
    raw: JsonMapping
    product_description: str | None
    reason_for_recall: str | None
    recalling_firm: str | None
    product_description_clean: str | None
    reason_for_recall_clean: str | None
    recalling_firm_clean: str | None
    firm_normalized: str | None
    recall_initiation_date: date | None
    center_classification_date: date | None
    termination_date: date | None
    report_date: date | None
    reporting_lag_days: int | None
    hazard: HazardClassification
    product_category: ProductCategoryClassification


def normalize_record(
    source: SourceFoodEnforcementRecord,
    *,
    source_metadata: OpenFDAMetadata | None = None,
) -> NormalizedFoodEnforcementRecord:
    """Normalize one source record without mutating source values or raw JSON."""
    parsed = source.parsed
    product_description_clean = clean_text(parsed.product_description)
    reason_for_recall_clean = clean_text(parsed.reason_for_recall)
    recalling_firm_clean = clean_text(parsed.recalling_firm)
    recall_initiation_date = parse_source_date(parsed.recall_initiation_date)
    report_date = parse_source_date(parsed.report_date)
    hazard_text = " ".join(
        value for value in (product_description_clean, reason_for_recall_clean) if value is not None
    )
    return NormalizedFoodEnforcementRecord(
        source_record_id=source_record_id(source.raw),
        normalization_version=NORMALIZATION_VERSION,
        recall_number=parsed.recall_number,
        event_id=parsed.event_id,
        source_metadata=source_metadata,
        raw=dict(source.raw),
        product_description=parsed.product_description,
        reason_for_recall=parsed.reason_for_recall,
        recalling_firm=parsed.recalling_firm,
        product_description_clean=product_description_clean,
        reason_for_recall_clean=reason_for_recall_clean,
        recalling_firm_clean=recalling_firm_clean,
        firm_normalized=normalize_firm(parsed.recalling_firm),
        recall_initiation_date=recall_initiation_date,
        center_classification_date=parse_source_date(parsed.center_classification_date),
        termination_date=parse_source_date(parsed.termination_date),
        report_date=report_date,
        reporting_lag_days=_reporting_lag_days(recall_initiation_date, report_date),
        hazard=load_hazard_taxonomy().classify(hazard_text or None),
        product_category=load_product_category_taxonomy().classify(product_description_clean),
    )


def clean_text(value: str | None) -> str | None:
    """Apply Unicode NFKC and whitespace normalization while retaining original text separately."""
    if value is None:
        return None
    return _WHITESPACE_PATTERN.sub(" ", unicodedata.normalize("NFKC", value)).strip() or None


def normalize_firm(value: str | None) -> str | None:
    """Create a conservative comparison key without fuzzy firm matching."""
    cleaned = clean_text(value)
    if cleaned is None:
        return None
    punctuation_normalized = _PUNCTUATION_PATTERN.sub(" ", cleaned.casefold())
    normalized = _WHITESPACE_PATTERN.sub(" ", punctuation_normalized).strip()
    words = normalized.split()
    while words and words[-1] in LEGAL_SUFFIXES:
        words.pop()
    return " ".join(words) or None


def parse_source_date(value: str | None) -> date | None:
    """Parse only valid openFDA YYYYMMDD source values; preserve originals elsewhere."""
    if value is None or not re.fullmatch(r"\d{8}", value):
        return None
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        return None


def source_record_id(raw: JsonMapping) -> str:
    """Hash stable source identifiers and source content fields into a reproducible ID."""
    stable_fields = (
        "recall_number",
        "event_id",
        "product_description",
        "reason_for_recall",
        "code_info",
        "more_code_info",
        "recalling_firm",
        "report_date",
    )
    identity = {field: raw.get(field) for field in stable_fields}
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _reporting_lag_days(start: date | None, end: date | None) -> int | None:
    if start is None or end is None:
        return None
    return (end - start).days
