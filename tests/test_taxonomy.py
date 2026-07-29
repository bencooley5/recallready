"""Focused deterministic tests for transparent hazard and product taxonomies."""

from __future__ import annotations

import pytest

from recallready.data.taxonomy import load_hazard_taxonomy, load_product_category_taxonomy


@pytest.mark.parametrize(
    ("text", "primary_hazard", "specific_tag"),
    [
        ("Possible Listeria monocytogenes contamination", "pathogen_contamination", "listeria"),
        ("Potential Salmonella contamination", "pathogen_contamination", "salmonella"),
        ("E. coli O157:H7 was detected", "pathogen_contamination", "e_coli_stec"),
        ("STEC contamination", "pathogen_contamination", "e_coli_stec"),
        ("Undeclared milk", "undeclared_allergen", "milk"),
        ("Milk product packaged for retail", "other_or_unclear", None),
        ("Undeclared egg ingredient", "undeclared_allergen", "egg"),
        ("Missing fish allergen declaration", "undeclared_allergen", "fish"),
        ("Undeclared shellfish", "undeclared_allergen", "crustacean_shellfish"),
        ("Contains undeclared tree nuts", "undeclared_allergen", "tree_nuts"),
        ("Undeclared walnut", "undeclared_allergen", "tree_nuts"),
        ("Undeclared peanut", "undeclared_allergen", "peanut"),
        ("Omitted wheat from label", "undeclared_allergen", "wheat"),
        ("Missing soy allergen", "undeclared_allergen", "soy"),
        ("Undeclared sesame", "undeclared_allergen", "sesame"),
        ("Foreign material: glass fragment", "foreign_material", None),
        ("Metal pieces found in product", "foreign_material", None),
        ("Plastic foreign material", "foreign_material", None),
        ("Pesticide residue above limit", "chemical_or_residue", None),
        ("Lead contamination", "chemical_or_residue", None),
        ("Product was underprocessed", "process_control_or_underprocessing", None),
        ("Insufficiently pasteurized beverage", "process_control_or_underprocessing", None),
        ("Broken seal on package", "packaging_integrity", None),
        ("Compromised package integrity", "packaging_integrity", None),
        ("Unauthorized food additive", "unapproved_ingredient_or_additive", None),
        ("Misbranding due to incorrect label", "labeling_or_misbranding", None),
        ("Spoiled product with off odor", "quality_or_spoilage", None),
        ("Mold observed in finished product", "quality_or_spoilage", None),
        ("General product quality concern", "other_or_unclear", None),
        ("Product may be defective", "other_or_unclear", None),
    ],
)
def test_hazard_rules_cover_positive_negative_and_ambiguous_text(
    text: str, primary_hazard: str, specific_tag: str | None
) -> None:
    """Each explicit rule is stable while unsupported text remains unclassified."""
    result = load_hazard_taxonomy().classify(text)

    assert result.primary_hazard == primary_hazard
    tag_values = {tag.tag_value for tag in result.tags}
    if specific_tag is None:
        assert result.confidence in {"category_rule_match", "no_rule_match"}
    else:
        assert specific_tag in tag_values
        assert result.confidence == "specific_rule_match"


def test_overlapping_hazards_keep_all_tags_and_use_documented_precedence() -> None:
    """A mixed reason preserves both findings; pathogen precedes foreign material."""
    result = load_hazard_taxonomy().classify("Listeria detected with glass fragments")

    assert result.primary_hazard == "pathogen_contamination"
    assert {tag.tag_value for tag in result.tags} >= {"listeria", "foreign_material"}
    assert result.primary_rule_id == "hazard-pathogen"


@pytest.mark.parametrize(
    ("description", "primary_category"),
    [
        ("Pasteurized milk", "dairy"),
        ("Cheese crackers", "dairy"),
        ("Wheat bread", "bakery_and_grain"),
        ("Romaine lettuce", "produce"),
        ("Frozen shrimp", "seafood"),
        ("Chicken sausage", "meat_or_poultry"),
        ("Apple juice", "beverage"),
        ("Milk and cookies", "bakery_and_grain"),
        ("Unspecified prepared food", "unknown"),
        ("", "unknown"),
    ],
)
def test_product_category_rules_are_derived_and_can_return_unknown(
    description: str, primary_category: str
) -> None:
    """Product categories use only description rules and never force a classification."""
    result = load_product_category_taxonomy().classify(description)

    assert result.primary_category == primary_category
    assert result.taxonomy_version == "1.0.0"


def test_taxonomy_output_is_deterministic() -> None:
    """Repeated classifications return exactly the same immutable result."""
    taxonomy = load_hazard_taxonomy()

    assert taxonomy.classify("Undeclared sesame and Listeria") == taxonomy.classify(
        "Undeclared sesame and Listeria"
    )
