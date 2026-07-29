# RecallReady implementation plan

## Product intent

RecallReady helps food-industry professionals, consultants, students, and researchers explore *historical* U.S. FDA food enforcement records, turn transparent aggregates into executive context, and rehearse traceability investigations using comparable past records. It is a public portfolio project, not a live recall alerting or case-management system.

### User stories

- As a quality leader, I can filter historical event and product-record metrics and see their stated time range, grain, and source freshness.
- As an analyst, I can search descriptions and recall reasons, inspect the evidence records behind an event, and export the filtered result set.
- As a consultant, I can ask a bounded question in plain language and receive a source-grounded answer with record citations and limitations.
- As an operations lead, I can select comparable historical records and generate a deterministic tabletop scenario and downloadable brief for internal preparation.
- As a student or researcher, I can understand the source, transformations, taxonomy, missingness, and limits before interpreting results.

### Non-goals

- Consumer alerts, safety determinations, live recall or recall-lifecycle status, notification workflows, forecasts, or firm risk scoring.
- Legal, medical, regulatory, or compliance advice; confidential data intake; automated external actions.
- A model that queries a database directly, writes data, or executes arbitrary SQL.

## Page-by-page specification

| Page | User outcome | Primary UI and outputs | Guardrails |
|---|---|---|---|
| Executive dashboard | Understand historical volume and composition | Global date/classification/taxonomy filters; KPI cards for event count and product-record count; monthly trend, class mix, distribution geography, and top normalized categories; download filtered executive brief | Unit shown beside every KPI; snapshot/freshness notice; no current-status language |
| Recall explorer | Find and verify historical records | FTS query, structured filters, event/product toggle, paged table, event grouping, record detail drawer, source fields, CSV export | FTS is discovery only; exact source text retained; export includes metadata and filter manifest |
| Analyst | Ask bounded historical questions | Suggested prompts, conversation transcript, evidence chips linking to explorer, citations, and a tool-activity disclosure | Tool-only factual claims; no unsupported answer; disclaimer and refusal patterns for safety/advice/current-status questions |
| Executive insights | Obtain repeatable decision context | Deterministic ranked findings, methodology note, evidence list, HTML/Markdown/PDF-ready brief download | Rules and thresholds are visible/versioned; no causal or predictive claims |
| Traceability tabletop | Rehearse a source-inspired investigation | Scenario inputs, comparable-record selection, timeline, roles, information requests, injects, and after-action worksheet download | Fictionalized exercise; historical records are cited as inspiration, not evidence of a current incident or compliance determination |
| Methodology | Assess fitness for use | Sources, snapshot metadata, schema/taxonomy, metric definitions, data-quality dashboard, exclusions, version changelog | Prominent FDA/openFDA limits and missing-field note |

Global layout: title and persistent “historical analysis, not an alert feed” banner; sidebar filters shared by dashboard, explorer, insights, and tabletop candidate search; each page links to Methodology.

## Delivery phases

1. **Foundation:** scaffold package, configuration, typed domain models, lint/type/test tooling, documentation links, and read-only database connection abstraction.
2. **Ingestion and snapshot:** implement validated openFDA client, resumable bounded-date/search-after ingest, raw audit manifest, normalization, Parquet output, and snapshot quality checks.
3. **Query layer:** build deterministic SQLite schema/FTS database from Parquet, parameterized repositories, event grouping, filters, exports, and query tests.
4. **Explorer and dashboard:** implement Streamlit shell, filters, Altair charts, metric definitions, explorer/detail/export, accessibility and empty/error states.
5. **Insights and tabletop:** add transparent insight rules, comparable-record selector, deterministic scenario/brief generators, and export tests.
6. **Analyst:** add Responses API orchestration, strict tool schemas, validated tool dispatcher, citations, rate/cost controls, and adversarial prompt tests.
7. **Release hardening:** CI, snapshot release procedure, deployment configuration, performance/accessibility review, public documentation, and acceptance sign-off.

No phase releases a capability whose relevant methodology, provenance, tests, and safety copy are absent.

## Acceptance criteria

- A fresh clone can build a read-only SQLite database from the committed Parquet snapshot without network access.
- Dashboard and explorer distinguish event from product-record counts and reproduce known fixture aggregates.
- Explorer FTS and all filters return only parameterized repository-query results; CSV contains selected fields, filter manifest, snapshot ID, and export timestamp.
- Ingestion handles API retries/rate limits, pages without skip-based full-dataset traversal, logs every request/response summary, and preserves nulls/source values.
- Every analyst factual answer is backed by returned evidence IDs; unsupported, current-safety, lifecycle, advice, prediction, and prompt-injection requests are safely limited or refused.
- Tabletop outputs are deterministic for the same input and include historical-source citations plus a fiction/preparedness disclaimer.
- CI runs Ruff, mypy, pytest, and a build/smoke test; no secrets or generated SQLite database are committed.

