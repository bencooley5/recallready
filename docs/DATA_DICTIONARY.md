# Data dictionary

## Data contract and grains

The source is the openFDA Food Enforcement API, derived from FDA Recall Enterprise System enforcement-report information. Source coverage is 2004 onward and weekly updates; it is a historical reference, not an alert or current-lifecycle feed. Snapshot identifiers and timestamps make every derived value reproducible.

| Concept | Grain | Definition |
|---|---|---|
| Product record | One API result / `recall_number`-oriented record | The canonical source-grain row. A product record is not necessarily one physical SKU, lot, or unique product. |
| Recall event | `event_id` where available | FDA states an event may contain multiple recalled products. Event metrics deduplicate by validated `event_id`; missing IDs are labeled fallback/unknown. |
| Snapshot | One immutable ingestion/build run | A versioned historical capture with API/query metadata, data checksum, transform versions, and freshness time. |
| Taxonomy assignment | One product record | Conservative derived category with a version and rule/provenance. It never replaces source text. |

## Source fields retained in `recall_products`

| Field | Type | Meaning / handling |
|---|---|---|
| `recall_number` | nullable text | FDA tracking designation for a specific classified recalled product; preserve formatting. |
| `event_id` | nullable text | FDA numerical recall-event designation; store as text, never coerce to number. |
| `product_description` | nullable text | Source brief product description; FTS indexed and rendered as untrusted text. |
| `reason_for_recall` | nullable text | Source defect/reason text; FTS indexed and never interpreted as an instruction or root-cause fact. |
| `classification` | nullable text | FDA Class I/II/III or not-yet-classified source value; historical classification, not a current safety assessment. |
| `status` | nullable text | Historical source progress value; never interpreted as current lifecycle state. |
| `recalling_firm` | nullable text | Firm that initiated the recall according to FDA definition; do not treat as a firm-risk measure. |
| `product_quantity` | nullable text | Unstructured source amount; retain text, no cross-record sum until unit normalization is explicitly validated. |
| `code_info`, `more_code_info` | nullable text | Lots, dates, product codes, or label information; rendered safely and searched only as text. |
| `product_code` | nullable text | Source product code; retain as text. |
| `distribution_pattern` | nullable text | Initial distribution description; may omit subsequent distribution and must not be converted into a safety/location alert. |
| `address_1`, `address_2`, `city`, `state`, `country` | nullable text | Recalling-firm location fields; country/state may be absent or not a distribution geography. |
| `voluntary_mandated` | nullable text | Source recall initiation designation. |
| `initial_firm_notification` | nullable text | Source initial consignee/public notification method. |
| `recall_initiation_date` | nullable date + raw text | Firm notification start date when parseable from source `YYYYMMDD`; raw value remains preserved. |
| `center_classification_date` | nullable date + raw text | FDA classification date; absence can be expected for not-yet-classified records. |
| `termination_date` | nullable date + raw text | Historical FDA termination date when supplied; not a current-status assertion. |
| `report_date` | nullable date + raw text | Enforcement-report date; default partition/refresh field. |
| `openfda_json`, `raw_json` | nullable JSON text | Original nested and complete source payload for audit/rebuild; never used as executable content. |

The API's searchable-fields reference includes these source fields and should be consulted before adding source mappings. [openFDA searchable fields](https://open.fda.gov/apis/food/enforcement/searchable-fields/)

## Derived fields

| Field | Type | Derivation and permitted use |
|---|---|---|
| `product_row_id` | text | Stable deterministic ID from snapshot and canonical source hash. |
| `source_record_hash` | SHA-256 text | Hash of canonical raw payload; used for idempotence/audit, not an FDA identifier. |
| `event_key` | text | `event:{event_id}` if present; otherwise marked deterministic fallback. Use fallback events cautiously. |
| `*_clean` | nullable text | Separate Unicode NFKC + whitespace-normalized text for search/rules; source field remains authoritative. |
| `firm_normalized` | nullable text | Lowercased punctuation/spacing key with only configured terminal legal suffixes removed; not fuzzy entity resolution. |
| `source_record_id` | SHA-256 text | Deterministic hash of selected stable IDs/content fields; a RecallReady reproducibility key, not an FDA identifier. |
| `*_date` | nullable date | Parsed only from valid source `YYYYMMDD` strings; original text remains retained. |
| `reporting_lag_days` | nullable integer | `report_date - recall_initiation_date` only when both dates are valid; not a lifecycle or timeliness measure. |
| `product_category` | enum/text | Versioned product-description rule output that may be `unknown`; descriptive, not an FDA determination. |
| `hazard_tags`, `primary_hazard` | multi-label enum/text | Versioned rule tags and documented-precedence primary category; not root cause, severity, or safety prediction. |
| `matched_rule_ids`, `match_confidence` | list/text enum | Rule lineage and specificity label (`specific_rule_match`, `category_rule_match`, `no_rule_match`), never a probability. |
| `snapshot_id`, `normalization_version`, `taxonomy_version` | text | Reproducibility keys included in all exports and briefs. |
| `source_last_checked_at_utc`, `ingested_at_utc` | UTC timestamp | Source/snapshot freshness facts, not evidence of current recall status. |

## Metric definitions

| Metric | Calculation | Caveat |
|---|---|---|
| Product-record count | `COUNT(*)` on filtered `recall_products` | Counts source rows, not unique consumer products, lots, firms, or events. |
| Event count | `COUNT(DISTINCT event_id)` on filtered records with valid IDs | Excludes/labels rows missing event ID by default; do not compare as complete event coverage without the missingness rate. |
| Classification mix | Product-record or event count by raw classification, named in chart subtitle | “Not yet classified”/null are categories, not zero risk. |
| Trend | Selected grain grouped by `report_date` month | A report date is not necessarily initiation or current status; revisions can change past counts. |
| Category share | Selected grain grouped by taxonomy version/category | Rule-derived and dependent on unclassified share. |
| Comparable records | Deterministic filter/rank against stated historical criteria | Similarity is for tabletop inspiration, not causation, risk prediction, or compliance applicability. |

## Quality checks and known limitations

- Reject malformed response envelopes, unexpected non-food product types, impossible parsed dates, duplicate source hashes in one snapshot, and missing required snapshot provenance.
- Report—not silently repair—invalid dates, source-field null rate, missing `event_id`, taxonomy coverage, duplicate recall numbers, partition-count reconciliation differences, and source revisions.
- Fields may be unavailable before June 2012; all analyses touching affected fields display period-specific completeness.
- FDA can correct or expand previously disclosed information. Snapshot comparison explains changes without overwriting the prior artifact.
- Product quantity and distribution pattern are unstructured strings; no aggregate quantity or precise geographic exposure metric is in scope initially.
- Recall text is unstructured. Versioned regex rules can miss, over-tag, or ambiguously tag records; all derived taxonomy outputs are non-official and must be read with the source record.

## Transparency and attribution

The source is FDA/openFDA historical food enforcement data, refreshed from the published endpoint on the project snapshot schedule. Snapshot metadata records source freshness, taxonomy versions, schema version, and SHA-256 checksum. `state` is the recalling firm's state; it is not distribution or exposure geography. Counts are records or known events, never incidence rates because market-volume denominators are not available. FDA classifications are source fields; product and hazard labels are rule-derived, non-official tags. RecallReady does not rank firms for safety and is not a consumer alert or recall-lifecycle service.
