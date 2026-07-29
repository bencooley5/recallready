"""Altair charts with explicit product-record/event grain labels."""
from __future__ import annotations

import altair as alt
import pandas as pd


def bar_chart(rows: list[dict[str, object]], title: str) -> alt.Chart:
    """Render a restrained product-record-count bar chart."""
    frame = pd.DataFrame(rows)
    return alt.Chart(frame, title=title).mark_bar().encode(x="value:N", y="product_record_count:Q", tooltip=list(frame.columns))

def time_chart(rows: list[dict[str, object]]) -> alt.Chart:
    """Render monthly product-record and known-event counts."""
    frame = pd.DataFrame(rows).melt("period", value_vars=["product_record_count", "unique_event_count"], var_name="grain", value_name="count")
    return alt.Chart(frame, title="Historical product records and known events by report month").mark_line(point=True).encode(x="period:T", y="count:Q", color="grain:N", tooltip=["period", "grain", "count"])
