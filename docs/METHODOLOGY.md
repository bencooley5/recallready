# Methodology and taxonomy limits

RecallReady analyzes historical openFDA food enforcement records. It is not a consumer alert feed, does not determine whether a product is currently safe or unsafe, and does not represent the current lifecycle of a recall.

## Normalization

Source text and raw JSON are retained unchanged. Separate cleaned fields apply Unicode NFKC normalization and collapse whitespace; they do not replace source fields. Only source strings matching valid `YYYYMMDD` dates become nullable derived dates. `reporting_lag_days` is calculated only when both recall-initiation and report dates parse successfully.

`source_record_id` is a SHA-256 hash of selected stable identifiers and content fields (`recall_number`, `event_id`, product description, reason, code information, firm, and report date). It is a RecallReady reproducibility key, not an FDA identifier. `firm_normalized` lowercases, standardizes punctuation/spacing, and strips only configured terminal legal suffixes. It is not entity resolution and RecallReady never fuzzy-merges firms.

## Rule taxonomies

`data/taxonomy.yml` is versioned and declares each regex rule, rule ID, tag type/value, priority, explanation, and taxonomy version. A record may receive several hazard, pathogen, and allergen tags. Primary hazard selection uses the documented YAML precedence order; all matched tags and rule IDs remain available. Confidence labels mean `specific_rule_match`, `category_rule_match`, or `no_rule_match`—they are rule-specificity labels, not probabilities.

`data/product_categories.yml` derives a conservative product category strictly from `product_description`; it may return `unknown`. Neither hazard nor product categories are official FDA classifications, FDA determinations, root-cause findings, safety determinations, or predictions. No runtime LLM classification is used in the MVP.

## Important limitations

Recall reasons and product descriptions are unstructured source text. Rules can miss relevant wording, over-tag a word used in another context, and change as the versioned taxonomy evolves. Derived categories must be reviewed with the cited source record and should not be treated as legal, medical, regulatory, or compliance advice. Missing source fields—especially before June 2012—remain missing and are never inferred.

## Deterministic executive insights

Executive insights are rendered from reviewed repository aggregates and templates; they do not use an LLM. They state the filter scope, date basis, product-record count, known-event count, source freshness, and caveats. A percentage change is shown only when the comparison period contains at least 10 product records; otherwise the absolute difference is retained and the percentage is explicitly suppressed. Derived taxonomy/product combinations are descriptive observations only. The brief does not infer causation, current recall lifecycle, product safety, or a firm's conduct.

## Traceability tabletop lab

The Tabletop Lab is a deterministic, fictional preparedness exercise grounded in selected historical records. It never determines whether a food or business is covered by the Food Traceability Rule and does not establish compliance. Users may select a curated Food Traceability List category only for educational context; independent review is required for coverage, exemptions, and obligations. FDA describes a 24-hour records-production context for persons subject to the rule; this is background for exercises, not advice or an applicability decision. [FDA Food Traceability Final Rule](https://www.fda.gov/food/food-safety-modernization-act-fsma/fsma-final-rule-requirements-additional-traceability-records-certain-foods)

## Snapshot metrics

`raw_record_count` and `normalized_record_count` are source product-record rows. `unique_recall_numbers` counts non-null FDA recall-number values; `unique_events_with_non_null_event_id` counts non-null FDA event IDs; `records_lacking_event_id` is reported separately and is not treated as zero events. Date coverage uses parsed `report_date`. Validation requires unique source IDs and at least 50% non-null product descriptions and reasons, profiles all classification values without dropping unknowns, and reports pre-2012 missing event IDs as a limitation. Snapshot SHA-256 and database schema version identify every build.
