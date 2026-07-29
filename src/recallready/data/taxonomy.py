"""Transparent, versioned rule taxonomies for historical recall text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import yaml


class TaxonomyConfigurationError(ValueError):
    """Raised when a committed taxonomy file is malformed or unsafe to use."""


@dataclass(frozen=True, slots=True)
class TaxonomyRule:
    """One human-reviewable YAML hazard rule."""

    rule_id: str
    tag_type: str
    tag_value: str
    regex: str
    priority: int
    explanation: str
    taxonomy_version: str


@dataclass(frozen=True, slots=True)
class TaxonomyTag:
    """One matched tag and its transparent rule provenance."""

    tag_type: str
    tag_value: str
    rule_id: str
    priority: int


@dataclass(frozen=True, slots=True)
class HazardClassification:
    """Multi-label hazard output with a precedence-selected primary category."""

    taxonomy_version: str
    tags: tuple[TaxonomyTag, ...]
    primary_hazard: str
    primary_rule_id: str | None
    confidence: str

    @property
    def matched_rule_ids(self) -> tuple[str, ...]:
        """Return rule IDs in stable evaluation order."""
        return tuple(tag.rule_id for tag in self.tags)


@dataclass(frozen=True, slots=True)
class ProductCategoryRule:
    """One derived product-category rule based only on product description text."""

    rule_id: str
    category: str
    regex: str
    priority: int
    explanation: str


@dataclass(frozen=True, slots=True)
class ProductCategoryClassification:
    """Derived, potentially unknown product-category output."""

    taxonomy_version: str
    matched_categories: tuple[str, ...]
    matched_rule_ids: tuple[str, ...]
    primary_category: str
    confidence: str


@dataclass(frozen=True, slots=True)
class HazardTaxonomy:
    """Loaded hazard rules plus the documented primary-hazard precedence."""

    taxonomy_version: str
    rules: tuple[TaxonomyRule, ...]
    primary_hazard_precedence: tuple[str, ...]

    def classify(self, text: str | None) -> HazardClassification:
        """Classify normalized source text with deterministic multi-label rules."""
        if not text:
            return HazardClassification(
                taxonomy_version=self.taxonomy_version,
                tags=(),
                primary_hazard="other_or_unclear",
                primary_rule_id=None,
                confidence="no_rule_match",
            )

        tags = tuple(
            TaxonomyTag(rule.tag_type, rule.tag_value, rule.rule_id, rule.priority)
            for rule in self.rules
            if re.search(rule.regex, text, flags=re.IGNORECASE)
        )
        hazard_tags = {tag.tag_value: tag for tag in tags if tag.tag_type == "hazard"}
        primary_hazard = "other_or_unclear"
        primary_rule_id: str | None = None
        for category in self.primary_hazard_precedence:
            if category in hazard_tags:
                primary_hazard = category
                primary_rule_id = hazard_tags[category].rule_id
                break

        if any(tag.tag_type in {"allergen", "pathogen"} for tag in tags):
            confidence = "specific_rule_match"
        elif tags:
            confidence = "category_rule_match"
        else:
            confidence = "no_rule_match"
        return HazardClassification(
            taxonomy_version=self.taxonomy_version,
            tags=tuple(sorted(tags, key=lambda tag: (tag.priority, tag.rule_id))),
            primary_hazard=primary_hazard,
            primary_rule_id=primary_rule_id,
            confidence=confidence,
        )


@dataclass(frozen=True, slots=True)
class ProductCategoryTaxonomy:
    """Loaded rules that provide deliberately conservative product categories."""

    taxonomy_version: str
    rules: tuple[ProductCategoryRule, ...]

    def classify(self, product_description: str | None) -> ProductCategoryClassification:
        """Classify a product description or explicitly return ``unknown``."""
        if not product_description:
            return ProductCategoryClassification(
                taxonomy_version=self.taxonomy_version,
                matched_categories=(),
                matched_rule_ids=(),
                primary_category="unknown",
                confidence="no_rule_match",
            )
        matches = [
            rule
            for rule in self.rules
            if re.search(rule.regex, product_description, flags=re.IGNORECASE)
        ]
        if not matches:
            return ProductCategoryClassification(
                taxonomy_version=self.taxonomy_version,
                matched_categories=(),
                matched_rule_ids=(),
                primary_category="unknown",
                confidence="no_rule_match",
            )
        ordered = tuple(sorted(matches, key=lambda rule: (rule.priority, rule.rule_id)))
        categories = tuple(dict.fromkeys(rule.category for rule in ordered))
        return ProductCategoryClassification(
            taxonomy_version=self.taxonomy_version,
            matched_categories=categories,
            matched_rule_ids=tuple(rule.rule_id for rule in ordered),
            primary_category=categories[0],
            confidence="category_rule_match",
        )


@lru_cache(maxsize=1)
def load_hazard_taxonomy(path: Path | None = None) -> HazardTaxonomy:
    """Load and validate the committed hazard taxonomy once per process."""
    source = path or _project_root() / "data" / "taxonomy.yml"
    document = _load_document(source)
    version = _required_str(document, "taxonomy_version", source)
    precedence = _required_str_list(document, "primary_hazard_precedence", source)
    raw_rules = _required_list(document, "rules", source)
    rules = tuple(_hazard_rule(raw_rule, source, version) for raw_rule in raw_rules)
    return HazardTaxonomy(version, rules, tuple(precedence))


@lru_cache(maxsize=1)
def load_product_category_taxonomy(path: Path | None = None) -> ProductCategoryTaxonomy:
    """Load and validate the committed product-category taxonomy once per process."""
    source = path or _project_root() / "data" / "product_categories.yml"
    document = _load_document(source)
    version = _required_str(document, "taxonomy_version", source)
    raw_rules = _required_list(document, "rules", source)
    rules = tuple(_product_rule(raw_rule, source) for raw_rule in raw_rules)
    return ProductCategoryTaxonomy(version, rules)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_document(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            document = yaml.safe_load(handle)
    except OSError as error:
        raise TaxonomyConfigurationError(f"Cannot load taxonomy file: {path.name}") from error
    except yaml.YAMLError as error:
        raise TaxonomyConfigurationError(f"Invalid YAML taxonomy file: {path.name}") from error
    if not isinstance(document, dict):
        raise TaxonomyConfigurationError(f"Taxonomy document must be a mapping: {path.name}")
    return cast(dict[str, Any], document)


def _hazard_rule(raw_rule: object, source: Path, version: str) -> TaxonomyRule:
    values = _rule_mapping(raw_rule, source)
    rule = TaxonomyRule(
        rule_id=_required_str(values, "rule_id", source),
        tag_type=_required_str(values, "tag_type", source),
        tag_value=_required_str(values, "tag_value", source),
        regex=_required_str(values, "regex", source),
        priority=_required_int(values, "priority", source),
        explanation=_required_str(values, "explanation", source),
        taxonomy_version=_required_str(values, "taxonomy_version", source),
    )
    if rule.taxonomy_version != version:
        raise TaxonomyConfigurationError(f"Rule version mismatch: {rule.rule_id}")
    _validate_regex(rule.regex, rule.rule_id)
    return rule


def _product_rule(raw_rule: object, source: Path) -> ProductCategoryRule:
    values = _rule_mapping(raw_rule, source)
    rule = ProductCategoryRule(
        rule_id=_required_str(values, "rule_id", source),
        category=_required_str(values, "category", source),
        regex=_required_str(values, "regex", source),
        priority=_required_int(values, "priority", source),
        explanation=_required_str(values, "explanation", source),
    )
    _validate_regex(rule.regex, rule.rule_id)
    return rule


def _rule_mapping(raw_rule: object, source: Path) -> dict[str, Any]:
    if not isinstance(raw_rule, dict):
        raise TaxonomyConfigurationError(f"Taxonomy rule must be a mapping: {source.name}")
    return raw_rule


def _required_str(values: dict[str, Any], key: str, source: Path) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise TaxonomyConfigurationError(f"Missing string {key} in {source.name}")
    return value


def _required_str_list(values: dict[str, Any], key: str, source: Path) -> list[str]:
    value = values.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise TaxonomyConfigurationError(f"Missing string list {key} in {source.name}")
    return value


def _required_list(values: dict[str, Any], key: str, source: Path) -> list[object]:
    value = values.get(key)
    if not isinstance(value, list):
        raise TaxonomyConfigurationError(f"Missing list {key} in {source.name}")
    return value


def _required_int(values: dict[str, Any], key: str, source: Path) -> int:
    value = values.get(key)
    if not isinstance(value, int):
        raise TaxonomyConfigurationError(f"Missing integer {key} in {source.name}")
    return value


def _validate_regex(expression: str, rule_id: str) -> None:
    try:
        re.compile(expression)
    except re.error as error:
        raise TaxonomyConfigurationError(f"Invalid regex for rule {rule_id}") from error
