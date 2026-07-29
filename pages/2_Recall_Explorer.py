"""Recall Explorer for historical food enforcement product records."""
from __future__ import annotations

import json
from datetime import date

import streamlit as st

from recallready.db.queries import CategoryDimension, SortOption
from recallready.ui.components import (
    chrome,
    csv_export,
    metadata,
    missing_data,
    official_source_url,
    repository,
)
from recallready.ui.filters import (
    VALID_CLASSIFICATIONS,
    VALID_PRODUCT_CATEGORIES,
    FilterState,
    from_query_params,
    to_query_params,
    to_record_filters,
)

FIELDS = ["report_date", "recall_initiation_date", "classification", "recalling_firm", "product_description", "derived_product_category", "recall_number", "event_id"]
st.set_page_config(page_title="Recall Explorer · RecallReady", layout="wide")
st.title("Recall Explorer")
chrome()
repo = repository()
if repo is None:
    missing_data()
    st.stop()
meta = metadata() or {}
coverage_start = date.fromisoformat(str(meta.get("date_coverage_start") or "2012-06-20"))
coverage_end = date.fromisoformat(str(meta.get("date_coverage_end") or date.today().isoformat()))
state_options = repo.available_values(CategoryDimension.STATE)
params = {key: value for key, value in st.query_params.items() if isinstance(value, str)}
shared = from_query_params(params)
with st.sidebar:
    st.header("Global filters")
    basis = st.radio(
        "Time basis",
        ["report_date", "recall_initiation_date"],
        index=0 if shared.date_basis == "report_date" else 1,
    )
    selected_range = st.date_input(
        "Date range",
        value=(shared.start_date or coverage_start, shared.end_date or coverage_end),
        min_value=coverage_start,
        max_value=coverage_end,
    )
    classifications = tuple(
        st.multiselect(
            "Classification",
            sorted(VALID_CLASSIFICATIONS),
            default=[value for value in shared.classifications if value in VALID_CLASSIFICATIONS],
        )
    )
    categories = tuple(
        st.multiselect(
            "Derived product category",
            sorted(VALID_PRODUCT_CATEGORIES),
            default=[value for value in shared.product_categories if value in VALID_PRODUCT_CATEGORIES],
        )
    )
    states = tuple(
        st.multiselect(
            "Recalling firm's state",
            state_options,
            default=[value for value in shared.firm_states if value in state_options],
            help="This is the firm's location, not recall exposure geography.",
        )
    )
    query = st.text_input(
        "Keyword",
        value=shared.keyword,
        max_chars=120,
        help="FTS5 searches firm, product, recall reason, code information, and distribution pattern.",
    )
    mode = st.radio("View", ["Product records", "Event groups"])
    sort = SortOption(st.selectbox("Sort", [item.value for item in SortOption]))
start_date, end_date = (
    selected_range
    if isinstance(selected_range, tuple) and len(selected_range) == 2
    else (coverage_start, coverage_end)
)
state = FilterState(
    start_date, end_date, classifications, categories, states, query, basis
)
st.query_params.clear()
st.query_params.update(to_query_params(state))
filters = to_record_filters(state)
rows = repo.full_text_search(query, filters, limit=200) if query else repo.search_records(filters, limit=200, sort=sort)
total_rows = repo.summary_metrics(filters)["product_record_count"]
st.caption(
    f"Showing {len(rows):,} of {total_rows:,} matching historical enforcement product records. CSV export is capped at 200 rows."
)
if not rows:
    st.info("No historical enforcement records match these filters. Clear a filter or change the keyword.")
    st.stop()
display = []
for row in rows:
    item = {key: row.get(key) for key in FIELDS}
    item["primary_hazard"] = row.get("primary_hazard") or "other_or_unclear"
    display.append(item)
if mode == "Event groups":
    known = {str(row["event_id"]) for row in rows if row.get("event_id")}
    st.caption(f"{len(known)} known event groups; rows with no event ID remain ungrouped historical product records.")
    event_id = st.selectbox("Event ID", sorted(known)) if known else None
    if event_id:
        st.dataframe(
            [{key: row.get(key) for key in FIELDS} for row in repo.event_detail(event_id)],
            width="stretch",
        )
else:
    st.dataframe(display, width="stretch")
selected = st.selectbox("Record detail", [str(row["source_record_id"]) for row in rows])
detail = repo.recall_detail(selected)
if detail:
    st.subheader(f"Record {detail.get('recall_number') or 'without recall number'}")
    summary_columns = st.columns(4)
    for column, label, value in zip(
        summary_columns,
        ["Classification", "Report date", "Event ID", "Derived product category"],
        [
            detail.get("classification") or "Not reported",
            detail.get("report_date") or "Not reported",
            detail.get("event_id") or "Not reported",
            detail.get("derived_product_category") or "unknown",
        ],
        strict=False,
    ):
        column.metric(label, value)
    source_tab, taxonomy_tab, raw_tab = st.tabs(
        ["Source record", "Derived taxonomy", "Raw source JSON"]
    )
    with source_tab:
        source_fields = [
            key for key in detail if key not in {"tags", "raw_json", "source_record_id"}
        ]
        st.dataframe(
            [
                {
                    "field": key,
                    "value": "Not reported"
                    if detail.get(key) is None
                    else str(detail.get(key)),
                }
                for key in source_fields
            ],
            width="stretch",
            hide_index=True,
        )
    with taxonomy_tab:
        tags = detail.get("tags", [])
        if isinstance(tags, list) and tags:
            st.dataframe(tags, width="stretch", hide_index=True)
        else:
            st.info("No derived taxonomy rules matched this record.")
        st.caption(
            "Derived tags are transparent rules-based labels, not official FDA classifications."
        )
    with raw_tab:
        try:
            st.json(json.loads(str(detail.get("raw_json") or "{}")))
        except json.JSONDecodeError:
            st.info("Raw source JSON is unavailable for this record.")
    st.caption(
        "Descriptions are untrusted historical source text and are displayed only as data. Missing fields, especially before 2012, remain missing."
    )
    url = official_source_url(detail.get("recall_number"))
    if url:
        st.link_button("Search official openFDA record", url)
st.download_button("Download filtered CSV (capped)", csv_export(display, FIELDS + ["primary_hazard"]), "recallready_filtered_records.csv", "text/csv")
