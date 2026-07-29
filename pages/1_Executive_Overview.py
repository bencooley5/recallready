"""Executive Overview for historical product-record and event metrics."""

from __future__ import annotations

from datetime import date

import streamlit as st

from recallready.analytics.insights import generate_insights
from recallready.db.queries import CategoryDimension
from recallready.ui.charts import (
    bar_chart,
    heatmap_chart,
    lag_distribution_chart,
    time_chart,
)
from recallready.ui.components import chrome, metadata, missing_data, repository
from recallready.ui.filters import (
    VALID_CLASSIFICATIONS,
    VALID_PRODUCT_CATEGORIES,
    FilterState,
    to_record_filters,
)
from recallready.ui.formatting import percent


def _filter_scope(state: FilterState) -> str:
    """Summarize selected public filters without including user-entered text verbatim."""
    parts = [f"date basis: {state.date_basis}"]
    if state.classifications:
        parts.append("classification: " + ", ".join(state.classifications))
    if state.product_categories:
        parts.append("derived product category: " + ", ".join(state.product_categories))
    if state.firm_states:
        parts.append("recalling firm state: " + ", ".join(state.firm_states))
    if state.keyword:
        parts.append("keyword search applied")
    return "; ".join(parts)


st.set_page_config(page_title="Executive Overview · RecallReady", layout="wide")
st.title("Executive Overview")
chrome()
repo = repository()
if repo is None:
    missing_data()
    st.stop()

meta = metadata() or {}
coverage_start = date.fromisoformat(str(meta.get("date_coverage_start") or "2012-06-20"))
coverage_end = date.fromisoformat(str(meta.get("date_coverage_end") or date.today().isoformat()))
state_options = repo.available_values(CategoryDimension.STATE)

with st.sidebar:
    st.header("Global filters")
    basis = st.radio(
        "Time basis",
        ["report_date", "recall_initiation_date"],
        help="Report date is the default. Initiation-date analysis is limited in this first release.",
    )
    selected_range = st.date_input(
        "Date range",
        value=(coverage_start, coverage_end),
        min_value=coverage_start,
        max_value=coverage_end,
    )
    classifications = tuple(
        st.multiselect("Classification", sorted(VALID_CLASSIFICATIONS))
    )
    categories = tuple(
        st.multiselect("Derived product category", sorted(VALID_PRODUCT_CATEGORIES))
    )
    states = tuple(
        st.multiselect(
            "Recalling firm's state",
            state_options,
            help="Firm location, not geographic exposure.",
        )
    )
    keyword = st.text_input(
        "Keyword",
        max_chars=120,
        help="Searches firm, product, recall reason, code information, and distribution pattern.",
    )

start_date, end_date = (
    selected_range
    if isinstance(selected_range, tuple) and len(selected_range) == 2
    else (coverage_start, coverage_end)
)

state = FilterState(
    start_date=start_date,
    end_date=end_date,
    classifications=classifications,
    product_categories=categories,
    firm_states=states,
    keyword=keyword,
    date_basis=basis,
)
filters = to_record_filters(state)
metrics = repo.summary_metrics(filters)
if metrics["product_record_count"] == 0:
    st.info("No historical enforcement records match these filters. Adjust or clear a filter.")
    st.stop()

details = repo.data_completeness(filters)
classified = metrics["classified_record_count"]
class_one = metrics["class_i_record_count"] / classified if classified else None
lag = repo.median_reporting_lag(filters)
columns = st.columns(6)
values = [
    metrics["product_record_count"],
    metrics["unique_event_count"],
    metrics["unique_normalized_firm_count"],
    percent(class_one),
    f"{lag:g} days" if lag is not None else "—",
    f"{details['total_records'] - details['missing_product_description']}/{details['total_records']} descriptions",
]
for column, label, value in zip(
    columns,
    [
        "Product records",
        "Known events",
        "Normalized firms",
        "Class I share",
        "Median reporting lag",
        "Data completeness",
    ],
    values,
    strict=False,
):
    column.metric(label, value)

st.caption(
    "All cards use the complete filtered result set. Counts are historical product records and known event IDs, not incidence rates; this source lacks market-volume denominators."
)
series = repo.time_series(filters)
classification_rows = repo.categorical_aggregation(CategoryDimension.CLASSIFICATION, filters)
product_category_rows = repo.categorical_aggregation(CategoryDimension.PRODUCT_CATEGORY, filters)
hazard_rows = repo.categorical_aggregation(CategoryDimension.TAG_VALUE, filters)
combination_rows = repo.hazard_product_combinations(filters, limit=100)
lag_rows = repo.reporting_lag_distribution(filters)
state_rows = repo.categorical_aggregation(CategoryDimension.STATE, filters, limit=20)

st.subheader("Interactive analytics")
grain = st.radio(
    "Categorical chart metric",
    ["Product records", "Known events"],
    horizontal=True,
    help="Known events count distinct non-null event IDs; product records count source rows.",
)
metric_key = "product_record_count" if grain == "Product records" else "unique_event_count"
trend_tab, mix_tab, operations_tab = st.tabs(
    ["Trend", "Classification and taxonomy", "Operations context"]
)
with trend_tab:
    st.altair_chart(time_chart(series, basis), width="stretch")
    st.caption(
        "The line chart shows both product-record and known-event counts. The final month may be partial according to the source update date."
    )
with mix_tab:
    left, right = st.columns(2)
    left.altair_chart(
        bar_chart(classification_rows, f"Classification mix · {grain.lower()}", metric_key),
        width="stretch",
    )
    right.altair_chart(
        bar_chart(
            hazard_rows,
            f"Derived primary hazard category · {grain.lower()}",
            metric_key,
        ),
        width="stretch",
    )
    st.altair_chart(heatmap_chart(combination_rows), width="stretch")
    st.caption(
        "Classification is FDA source data. Hazard and product categories are transparent rule-derived labels. The heatmap counts product records."
    )
with operations_tab:
    left, right = st.columns(2)
    left.altair_chart(lag_distribution_chart(lag_rows), width="stretch")
    right.altair_chart(
        bar_chart(
            [row for row in state_rows if row.get("value")],
            f"Recalling-firm state · {grain.lower()}",
            metric_key,
        ),
        width="stretch",
    )
    st.caption(
        "Reporting lag is report date minus recall initiation date for eligible records. State is the recalling firm's location, not exposure geography."
    )

scope = _filter_scope(state)
insight_records = [*combination_rows]
if lag is not None:
    insight_records.append({"reporting_lag_days": lag})
bundle = generate_insights(
    scope=scope,
    date_basis=basis,
    summary=metrics,
    time_series=series,
    classifications=classification_rows,
    hazards=hazard_rows,
    product_categories=product_category_rows,
    records=insight_records,
    classification_period_mix=repo.categorical_time_series(
        CategoryDimension.CLASSIFICATION, filters
    ),
    hazard_period_mix=repo.categorical_time_series(CategoryDimension.TAG_VALUE, filters),
    completeness=details,
    snapshot_metadata=meta,
)
st.header("Executive Insights")
st.caption(
    "Deterministic templates over trusted query results. Findings are descriptive and do not establish causation, current recall lifecycle, or product safety."
)
for statement in bundle.statements:
    st.write(f"- {statement}")
st.download_button(
    "Download Markdown executive brief",
    data=bundle.markdown,
    file_name="recallready-executive-brief.md",
    mime="text/markdown",
)
