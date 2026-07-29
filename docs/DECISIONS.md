# Architecture decision record

## Accepted decisions

| ID | Decision | Rationale and consequence |
|---|---|---|
| ADR-001 | Use a committed, versioned Parquet snapshot as deployment source of truth; build SQLite/FTS5 deterministically. | Public Streamlit deployments remain usable without API availability, while Parquet preserves a portable typed archive. SQLite is disposable/read-only. |
| ADR-002 | Keep product-record and event-grain tables and label every metric. | FDA states one recall event can include multiple recalled products; one undifferentiated count would mislead. |
| ADR-003 | Treat all openFDA fields as nullable source evidence and preserve raw JSON plus provenance. | Fields are incomplete historically and records can be corrected. Normalization must not erase auditability. |
| ADR-004 | Initial ingestion uses `search_after` within bounded `report_date` partitions, not corpus-wide `skip`. | openFDA documents a 26,000-hit skip limit and recommends search-after for larger traversals. |
| ADR-005 | Use a conservative, versioned rules taxonomy with `unclassified`. | It enables transparent aggregation without presenting NLP guesses as facts. |
| ADR-006 | Analyst uses Responses API strict function calling, Pydantic validation, and allowlisted query functions. | The model can select a safe capability but cannot author/execute SQL or mutate the database. |
| ADR-007 | Insights and tabletop materials are deterministic templates driven by repository queries. | Repeatability, reviewability, and clear separation of historical evidence from generated prose are more valuable than unconstrained generation. |
| ADR-008 | Keep all inference local to historical description and avoid safety/current-status/advice claims. | This honors openFDA's explicit disclaimer that the data is not an alert feed and status is not maintained after classification. |
| ADR-009 | Require a validated committed `data/recalls.parquet` and `snapshot_metadata.json` before public release. | Community Cloud rebuilds disposable SQLite locally; without the public snapshot the app must remain in an explicit data-not-loaded state rather than fetching live data. |
| ADR-010 | Apply date basis, date range, classification, product category, recalling-firm state, and keyword in the repository filter object used by every metric and aggregate. | Dashboard cards and charts must describe one identical filtered population; sampled rows are reserved for display/export and never drive executive KPIs. |
| ADR-011 | Replay every Responses API output item during tool continuations and generate strict schemas with all object properties required. | This follows the current Responses function-calling and Structured Outputs contracts while keeping optional values explicitly nullable and all tool inputs validated. |

## Risks and limitations

- **Coverage and revision risk:** records are publicly releasable FDA enforcement records from 2004 onward and update weekly; historical snapshots can lag or differ from later corrections. Mitigation: snapshot timestamps, immutable manifests, rolling reingest, change reports, and source links.
- **Lifecycle/status risk:** source `status` is historical and not maintained after classification. Mitigation: never use it as a current condition; show this near status fields and omit it from executive “current” framing.
- **Missingness risk:** several fields are absent before June 2012. Mitigation: null-preserving model, missingness profile, date-scoped caveats, no zero-fill.
- **Event identity risk:** absent/reused/ambiguous IDs can impair grouping. Mitigation: use FDA `event_id` where available; deterministic fallback keys are explicitly marked and excluded from high-confidence event analyses by default.
- **Taxonomy risk:** keywords can misclassify product or hazard context. Mitigation: versioned rules, precedence, `unclassified`, source-text drill-down, and manual review samples.
- **Model risk:** hallucination, prompt injection in source text, cost, and tool misuse. Mitigation: strict schemas, validation, fixed dispatcher, compact evidence, call/time limits, output citation check, and no arbitrary SQL/network tools.
- **Public hosting risk:** repository/data size and cold starts may constrain Community Cloud. Mitigation: compact Parquet, SQLite build benchmarks, checksum validation, release fallback, and a last-known-good snapshot.

## Recommended defaults for unresolved choices

- Use Polars for snapshot transformation and pandas only where Streamlit/Altair interop is simplest; Pydantic v2 for boundaries.
- Use `report_date` partitions, 1,000-record pages, 20,000-hit partition warning threshold, 24-month rolling refresh, quarterly full reconciliation, and monthly public snapshot releases.
- Retain all source records; default dashboard window is the latest five complete calendar years, with an “all available history” option.
- Default dashboard grain is events; explorer defaults to product records because that is source grain. The UI never switches grain implicitly.
- Start with text-based national distribution patterns and only derive state facets conservatively; do not infer nationwide coverage from absent text.
- Launch analyst behind an explicit “historical evidence only” consent notice, max four tool rounds, max 25 search results, and no user-uploaded documents.
- Make downloadable briefs Markdown/HTML first; add PDF generation only after layout and dependency stability are proven.

## Source basis

The openFDA food-enforcement overview says the records cover 2004–present, update weekly, should not be used for public alerts, and do not maintain recall status after classification. [openFDA Food Enforcement Overview](https://open.fda.gov/apis/food/enforcement/)

openFDA documents API-key limits and HTTPS use, and its paging guidance recommends search-after for result sets beyond skip pagination's 26,000-hit limit. [Authentication](https://open.fda.gov/apis/authentication/) and [Paging](https://open.fda.gov/apis/paging/)

FDA distinguishes product and event views and states that an event may include more than one recalled product. [Enforcement Report Information and Definitions](https://www.fda.gov/safety/enforcement-reports/enforcement-report-information-and-definitions)

The tabletop scope may educate users about traceability concepts such as Critical Tracking Events and Key Data Elements, but must not determine applicability or compliance. [FDA Food Traceability Final Rule](https://www.fda.gov/food/food-safety-modernization-act-fsma/fsma-final-rule-requirements-additional-traceability-records-certain-foods)

The analyst design uses strict function schemas and response-loop function outputs as documented for the Responses API. [OpenAI function calling guide](https://developers.openai.com/api/docs/guides/function-calling)

Streamlit secrets must be uncommitted locally and configured in deployment settings. [Streamlit secrets management](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)
