"""Interactive Altair analytics with explicit metric-grain labels."""

from __future__ import annotations

import altair as alt
import pandas as pd


def bar_chart(
    rows: list[dict[str, object]], title: str, metric: str = "product_record_count"
) -> alt.Chart:
    """Render a categorical chart for an allowlisted count metric."""
    frame = pd.DataFrame(rows)
    if frame.empty:
        return alt.Chart(pd.DataFrame({"value": [], metric: []}), title=title).mark_bar()
    return (
        alt.Chart(frame, title=title)
        .mark_bar(cornerRadiusTopRight=3, cornerRadiusBottomRight=3)
        .encode(
            y=alt.Y("value:N", sort="-x", title=None),
            x=alt.X(f"{metric}:Q", title=metric.replace("_", " ").title()),
            tooltip=list(frame.columns),
            color=alt.Color("value:N", legend=None),
        )
        .interactive()
    )


def time_chart(rows: list[dict[str, object]], date_basis: str) -> alt.Chart:
    """Render monthly product-record and known-event counts with zoom and hover."""
    frame = pd.DataFrame(rows)
    if frame.empty:
        return alt.Chart(pd.DataFrame({"period": [], "count": []})).mark_line()
    frame = frame.melt(
        "period",
        value_vars=["product_record_count", "unique_event_count"],
        var_name="grain",
        value_name="count",
    )
    return (
        alt.Chart(
            frame,
            title=f"Historical product records and known events by {date_basis.replace('_', ' ')} month",
        )
        .mark_line(point=True)
        .encode(
            x=alt.X("period:T", title="Month"),
            y=alt.Y("count:Q", title="Count"),
            color=alt.Color("grain:N", title="Metric grain"),
            tooltip=["period:T", "grain:N", "count:Q"],
        )
        .interactive()
    )


def heatmap_chart(rows: list[dict[str, object]]) -> alt.Chart:
    """Show derived hazard/product combinations at product-record grain."""
    frame = pd.DataFrame(rows)
    if frame.empty:
        return alt.Chart(
            pd.DataFrame(
                {
                    "primary_hazard": [],
                    "derived_product_category": [],
                    "product_record_count": [],
                }
            )
        ).mark_rect()
    return (
        alt.Chart(frame, title="Derived product category × hazard · product records")
        .mark_rect()
        .encode(
            x=alt.X("derived_product_category:N", title="Derived product category"),
            y=alt.Y("primary_hazard:N", title="Derived primary hazard"),
            color=alt.Color("product_record_count:Q", title="Product records"),
            tooltip=[
                "derived_product_category:N",
                "primary_hazard:N",
                "product_record_count:Q",
            ],
        )
        .interactive()
    )


def lag_distribution_chart(rows: list[dict[str, object]]) -> alt.Chart:
    """Render reporting-lag bands with an explicit long-lag tail."""
    frame = pd.DataFrame(rows)
    if frame.empty:
        return alt.Chart(
            pd.DataFrame({"bin_start": [], "product_record_count": []})
        ).mark_bar()
    frame["lag_band"] = frame["bin_start"].map(_lag_band)
    return (
        alt.Chart(frame, title="Reporting lag distribution · eligible product records")
        .mark_bar()
        .encode(
            x=alt.X("lag_band:N", sort=frame["lag_band"].tolist(), title="Lag days"),
            y=alt.Y("product_record_count:Q", title="Product records"),
            tooltip=["lag_band:N", "product_record_count:Q"],
            color=alt.Color("product_record_count:Q", legend=None),
        )
        .interactive()
    )


def _lag_band(value: object) -> str:
    if not isinstance(value, int | float | str):
        return "Unknown"
    try:
        start = int(value)
    except ValueError:
        return "Unknown"
    if start < 0:
        return "Negative"
    if start >= 365:
        return "365+"
    return f"{start}–{start + 29}"
