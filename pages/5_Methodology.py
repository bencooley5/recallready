"""Transparency, provenance, and data-quality page for RecallReady."""

from __future__ import annotations

import streamlit as st

from recallready.ui.components import chrome, metadata, missing_data, repository

st.set_page_config(page_title="Methodology · RecallReady", layout="wide")
st.title("Methodology and data quality")
chrome()
meta = metadata() or {}
repo = repository()
st.markdown("""RecallReady analyzes historical FDA/openFDA food enforcement records, which are updated weekly. It is not an alert feed, current recall-lifecycle tracker, product-safety determination, or legal, medical, regulatory, or compliance service.

Product records are source rows; a recall event is a distinct non-null `event_id`, so older rows without an event ID are not silently converted into events. Report date is the default time basis; recall-initiation date is separate and may be missing. Several source fields are less complete before June 2012.

`state` means the recalling firm's location, not exposure geography; distribution pattern is separate source text. FDA classification is source-provided; hazard and product categories are transparent, non-official taxonomy rules. Rules are versioned and can miss or over-tag unstructured text. Counts are not incidence rates because market-volume denominators are unavailable. The app does not rank firm safety or dangerousness.

Data are attributed to FDA/openFDA public food enforcement records. The app preserves source nulls and raw identifiers; consult FDA terms and source documentation for public-data use context.""")
st.subheader("Snapshot provenance")
st.json({key: meta.get(key) for key in ("source_name", "source_last_updated", "ingestion_completed_at", "schema_version", "taxonomy_versions", "sha256")})
if repo is None:
    missing_data()
    st.stop()
st.subheader("Data quality by report year")
st.caption("Missing values remain missing. Pre-2012 gaps are reported, not treated as repaired data.")
st.dataframe(repo.data_quality_by_year(), width="stretch")
overall = repo.data_completeness()
summary = repo.summary_metrics()
st.subheader("Selected data-quality indicators")
st.dataframe([{"records_lacking_event_id": summary["missing_event_id_count"], "unknown_or_uncategorized_hazard": "Rule-derived and reported through taxonomy tags", "unknown_product_categories": "Included in the year table", "source_date_coverage": "See report-year table", "taxonomy_version": meta.get("taxonomy_versions"), "snapshot_checksum": meta.get("sha256"), **overall}], width="stretch")
st.caption("Taxonomy rule IDs, definitions, and limitations are documented in the data dictionary and methodology Markdown.")
