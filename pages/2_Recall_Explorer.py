"""Recall Explorer for historical food enforcement product records."""
from __future__ import annotations

import streamlit as st

from recallready.db.queries import SortOption
from recallready.ui.components import (
    chrome,
    csv_export,
    missing_data,
    official_source_url,
    repository,
)
from recallready.ui.filters import (
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
params = {key: value for key, value in st.query_params.items() if isinstance(value, str)}
shared = from_query_params(params)
with st.sidebar:
    st.header("Global filters")
    classifications = tuple(st.multiselect("Classification", ["Class I", "Class II", "Class III"], default=list(shared.classifications)))
    categories = tuple(st.multiselect("Derived product category", ["dairy", "bakery_and_grain", "produce", "seafood", "meat_or_poultry", "beverage", "unknown"], default=list(shared.product_categories)))
    states = tuple(st.multiselect("Recalling firm's state", [], default=list(shared.firm_states), help="This is the firm's location, not recall exposure geography."))
    query = st.text_input("Keyword", help="FTS5 searches firm, product, recall reason, code information, and distribution pattern.")
    mode = st.radio("View", ["Product records", "Event groups"])
    sort = SortOption(st.selectbox("Sort", [item.value for item in SortOption]))
state = FilterState(shared.start_date, shared.end_date, classifications, categories, states, query)
st.query_params.clear()
st.query_params.update(to_query_params(state))
filters = to_record_filters(state)
rows = repo.full_text_search(query, filters, limit=200) if query else repo.search_records(filters, limit=200, sort=sort)
st.caption(f"Showing {len(rows)} of at most 200 historical enforcement product records. CSV export is capped at 200 rows.")
if not rows:
    st.info("No historical enforcement records match these filters. Clear a filter or change the keyword.")
    st.stop()
display = []
for row in rows:
    item = {key: row.get(key) for key in FIELDS}
    detail = repo.recall_detail(str(row["source_record_id"]))
    item["primary_hazard"] = detail.get("tags", [{}])[0].get("tag_value") if detail and detail.get("tags") else "other_or_unclear"
    display.append(item)
if mode == "Event groups":
    known = {str(row["event_id"]) for row in rows if row.get("event_id")}
    st.caption(f"{len(known)} known event groups; rows with no event ID remain ungrouped historical product records.")
    event_id = st.selectbox("Event ID", sorted(known)) if known else None
    if event_id:
        st.dataframe([{key: row.get(key) for key in FIELDS} for row in repo.event_detail(event_id)], use_container_width=True)
else:
    st.dataframe(display, use_container_width=True)
selected = st.selectbox("Record detail", [str(row["source_record_id"]) for row in rows])
detail = repo.recall_detail(selected)
if detail:
    with st.expander("Source fields, derived tags, and limitations", expanded=True):
        st.json(detail)
        st.caption("Descriptions and categories are historical source/derived data. Missing fields, especially before 2012, are preserved; tags are non-official rules-based classifications.")
        url = official_source_url(detail.get("recall_number"))
        if url:
            st.link_button("Search official openFDA record", url)
st.download_button("Download filtered CSV (capped)", csv_export(display, FIELDS + ["primary_hazard"]), "recallready_filtered_records.csv", "text/csv")
