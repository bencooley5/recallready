# RecallReady demo script

## 90-second walkthrough

Open the Executive Overview and point out the historical-analysis disclaimer, source freshness, and separate product-record/event KPIs. Apply a classification or category filter and explain that charts state their grain. Move to Recall Explorer, search for a source phrase, open a record, and show source fields plus derived taxonomy tags. Demonstrate the deterministic executive brief and then Tabletop Lab, emphasizing that its scenario is fictional and grounded in cited historical analogs. Finish with Ask RecallReady: it cites evidence, refuses current-safety questions, and remains disabled gracefully without credentials.

## Five-minute technical walkthrough

Explain the pipeline: bounded openFDA pagination, null-preserving Pydantic models, deterministic normalization/taxonomy, validation, Parquet snapshot, and disposable read-only SQLite/FTS runtime database. Show that repository queries are parameterized and dimensions/sorts are allowlisted. Explain that executive insights/tabletops use templates, while chat is constrained to strict Responses API function schemas and evidence validation. Close with snapshot metadata, test fixtures, refresh workflow, and responsible-use boundaries.

## Likely interview questions

1. **Why distinguish records and events?** One event can contain several recalled products, so mixing grains would mislead decision-makers.
2. **Why not show active recalls?** openFDA historical records do not provide a reliable current lifecycle; the product avoids unsafe consumer-alert claims.
3. **How is taxonomy trustworthy?** It is transparent and versioned, preserves matched rule IDs, and documents miss/over-tag limits.
4. **How is SQL injection prevented?** The model and UI cannot submit SQL; only typed repository functions create parameterized queries with allowlists.
5. **Why Parquet plus SQLite?** Parquet is portable deployment truth; SQLite/FTS is a disposable optimized query layer.
6. **How is chat grounded?** Strict tools return compact evidence references; outputs with unverifiable citations are withheld.
7. **What would you improve next?** Verify a scheduled refresh release, add reproducible visual regression checks, and expand source coverage only after the FDA MVP is deployed.

## Codex collaboration disclosure

Codex accelerated implementation by helping draft, inspect, test, and revise code and documentation. The project owner retained responsibility for requirements, source selection, validation, release decisions, and the accuracy and responsible use of the deployed project.

## Resume bullets — use only after verified in the deployed project

- Built and deployed a source-grounded historical food-enforcement analytics application using Python, Streamlit, Parquet, SQLite/FTS5, and deterministic taxonomies.
- Designed a validated data-refresh and quality-reporting pipeline that distinguishes product records from recall events and preserves missing-source context.
- Implemented evidence-constrained conversational analysis and deterministic tabletop-preparedness outputs with explicit safety, lifecycle, and compliance guardrails.
