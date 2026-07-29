"""Executive Overview for historical product-record and event metrics."""

from __future__ import annotations

import streamlit as st

from recallready.analytics.insights import generate_insights
from recallready.db.queries import CategoryDimension
from recallready.ui.charts import bar_chart, time_chart
from recallready.ui.components import chrome, metadata, missing_data, repository
from recallready.ui.filters import FilterState, to_record_filters
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

with st.sidebar:
    st.header("Global filters")
    basis = st.radio(
        "Time basis",
        ["report_date", "recall_initiation_date"],
        help="Report date is the default. Initiation-date analysis is limited in this first release.",
    )
    classifications = tuple(
        st.multiselect("Classification", ["Class I", "Class II", "Class III", "Not Yet Classified"])
    )
    categories = tuple(
        st.multiselect(
            "Derived product category",
            [
                "dairy",
                "bakery_and_grain",
                "produce",
                "seafood",
                "meat_or_poultry",
                "beverage",
                "unknown",
            ],
        )
    )
    states = tuple(
        st.multiselect("Recalling firm's state", [], help="Firm location, not geographic exposure.")
    )
    keyword = st.text_input("Keyword")

state = FilterState(
    classifications=classifications,
    product_categories=categories,
    firm_states=states,
    keyword=keyword,
    date_basis=basis,
)
filters = to_record_filters(state)
metrics = repo.summary_metrics(filters)
records = (
    repo.full_text_search(keyword, filters, limit=200)
    if keyword
    else repo.search_records(filters, limit=200)
)
if not records:
    st.info("No historical enforcement records match these filters. Adjust or clear a filter.")
    st.stop()

details = repo.data_completeness(filters)
class_one = sum(1 for record in records if record.get("classification") == "Class I") / len(records)
lag_values = [
    record["reporting_lag_days"]
    for record in records
    if isinstance(record.get("reporting_lag_days"), int)
]
lag = sorted(lag_values)[len(lag_values) // 2] if lag_values else None
columns = st.columns(6)
values = [
    metrics["product_record_count"],
    metrics["unique_event_count"],
    len({record.get("firm_normalized") for record in records if record.get("firm_normalized")}),
    percent(class_one),
    f"{lag} days" if lag is not None else "—",
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
    "Counts are historical product records and known event IDs, not incidence rates; this source lacks market-volume denominators."
)
series = repo.time_series(filters)
classification_rows = repo.categorical_aggregation(CategoryDimension.CLASSIFICATION, filters)
product_category_rows = repo.categorical_aggregation(CategoryDimension.PRODUCT_CATEGORY, filters)
hazard_rows = repo.categorical_aggregation(CategoryDimension.TAG_VALUE, filters)
combination_rows = repo.hazard_product_combinations(filters)

st.altair_chart(time_chart(series), use_container_width=True)
left, right = st.columns(2)
left.altair_chart(
    bar_chart(classification_rows, "Classification mix · product records"), use_container_width=True
)
right.altair_chart(
    bar_chart(product_category_rows, "Derived product category · product records"),
    use_container_width=True,
)

scope = _filter_scope(state)
insight_records = [*records, *combination_rows]
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
    snapshot_metadata=metadata(),
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
