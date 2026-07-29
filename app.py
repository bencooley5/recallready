"""Streamlit entry point for RecallReady."""

from __future__ import annotations

import streamlit as st

from recallready.config import get_settings
from recallready.logging_config import configure_logging
from recallready.ui.components import chrome, metadata, missing_data, repository


def main() -> None:
    """Render the Phase 1 landing page without loading external data."""
    settings = get_settings()
    configure_logging(settings.log_level)

    st.set_page_config(page_title="RecallReady", page_icon="🧭", layout="wide")
    st.title("RecallReady")
    st.subheader("Historical U.S. food recall intelligence and preparedness")
    st.write(
        "Explore FDA/openFDA food enforcement history, compare transparent descriptive patterns, ask a source-grounded analyst, and build educational traceability exercises."
    )
    chrome()
    repo = repository()
    if repo is None:
        missing_data()
    else:
        metrics = repo.summary_metrics()
        cards = st.columns(4)
        cards[0].metric("Historical product records", f"{metrics['product_record_count']:,}")
        cards[1].metric("Known recall events", f"{metrics['unique_event_count']:,}")
        cards[2].metric(
            "Normalized firms", f"{metrics['unique_normalized_firm_count']:,}"
        )
        cards[3].metric(
            "Snapshot version", str((metadata() or {}).get("schema_version") or "unknown")
        )
        st.subheader("Explore RecallReady")
        left, right = st.columns(2)
        with left:
            st.page_link(
                "pages/1_Executive_Overview.py",
                label="Executive Overview",
                icon="📊",
            )
            st.caption("Filter exact metrics and interact with trends, category mix, and lag analytics.")
            st.page_link(
                "pages/2_Recall_Explorer.py", label="Recall Explorer", icon="🔎"
            )
            st.caption("Search historical source text, inspect records and events, and export evidence.")
        with right:
            st.page_link(
                "pages/3_Ask_RecallReady.py", label="Ask RecallReady", icon="💬"
            )
            st.caption("Ask bounded questions through trusted database tools with evidence validation.")
            st.page_link(
                "pages/4_Tabletop_Lab.py", label="Traceability Tabletop Lab", icon="🧭"
            )
            st.caption("Generate deterministic educational exercises grounded in historical analogs.")

    if not settings.chat_available:
        st.caption("The historical analyst is disabled because no OpenAI API key is configured.")

    st.page_link("pages/5_Methodology.py", label="Read methodology and data quality", icon="📚")


if __name__ == "__main__":
    main()
