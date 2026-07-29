"""Educational, deterministic Traceability Tabletop Lab."""

from __future__ import annotations

from datetime import date

import streamlit as st
import yaml

from recallready.analytics.tabletop import TabletopInputs, build_tabletop
from recallready.db.repository import RecordFilters
from recallready.ui.components import (
    chrome,
    missing_data,
    official_source_url,
    repository,
)


def _ftl_names() -> list[str]:
    """Read only curated educational FTL labels."""
    document = yaml.safe_load(open("data/ftl_reference.yml", encoding="utf-8"))
    return [str(item["name"]) for item in document["categories"]]


st.set_page_config(page_title="Traceability Tabletop Lab · RecallReady", layout="wide")
st.title("Traceability Tabletop Lab")
chrome()
st.info("Educational fictional exercise only. Selecting an FTL category does not determine coverage, exemptions, obligations, or compliance.")
repo = repository()
if repo is None:
    missing_data()
    st.stop()
with st.form("tabletop_inputs"):
    product = st.selectbox("Derived product category", ["dairy", "bakery_and_grain", "produce", "seafood", "meat_or_poultry", "beverage", "unknown"])
    hazard_choice = st.selectbox(
        "Derived hazard category",
        [
            "Any derived hazard",
            "pathogen_contamination",
            "undeclared_allergen",
            "foreign_material",
            "chemical_or_residue",
            "labeling_or_misbranding",
        ],
    )
    hazard = "" if hazard_choice == "Any derived hazard" else hazard_choice
    classification = st.selectbox("Classification preference", ["Any", "Class I", "Class II", "Class III"])
    date_range = st.date_input("Historical analog date range", value=(date(2019, 1, 1), date.today()))
    profile = st.selectbox("Company profile", ["manufacturer", "distributor", "retailer", "restaurant", "mixed"])
    facilities = st.number_input("Number of facilities", min_value=1, max_value=50, value=2)
    distribution = st.selectbox("Distribution scope", ["local", "regional", "national", "mixed"])
    difficulty = st.selectbox("Exercise difficulty", ["introductory", "intermediate", "advanced"])
    roles = tuple(st.multiselect("Participating roles", ["quality", "operations", "supply chain", "communications", "leadership"], default=["quality", "operations"]))
    ftl = st.selectbox("Optional FDA Food Traceability List context", ["None", *_ftl_names()])
    submitted = st.form_submit_button("Build deterministic exercise")
if submitted:
    start, end = date_range if isinstance(date_range, tuple) and len(date_range) == 2 else (None, None)
    filters = RecordFilters(start_date=start.isoformat() if start else None, end_date=end.isoformat() if end else None, classifications=() if classification == "Any" else (classification,), product_categories=(product,))
    rows = repo.search_records(filters, limit=200)
    for row in rows:
        detail = repo.recall_detail(str(row["source_record_id"]))
        row["primary_hazard"] = next((tag["tag_value"] for tag in (detail or {}).get("tags", []) if tag.get("tag_type") == "hazard"), "")
    packet = build_tabletop(TabletopInputs(product, hazard, None if classification == "Any" else classification, profile, int(facilities), distribution, difficulty, roles, None if ftl == "None" else ftl), rows)
    st.success(packet.objective)
    scenario_tab, workflow_tab, evidence_tab, debrief_tab = st.tabs(
        ["Scenario and injects", "Decision workflow", "Historical evidence", "Debrief"]
    )
    with scenario_tab:
        st.subheader("Initial incident narrative")
        st.write(packet.narrative)
        st.subheader("Timed injects")
        for inject in packet.injects:
            st.markdown(f"- {inject}")
    with workflow_tab:
        left, right = st.columns(2)
        with left:
            st.subheader("Decision points")
            for item in packet.decision_points:
                st.markdown(f"- {item}")
            st.subheader("Records and information to locate")
            for item in packet.records_to_locate:
                st.markdown(f"- {item}")
        with right:
            st.subheader("Communication checklist")
            for item in packet.communications:
                st.markdown(f"- {item}")
            st.subheader("Role assignments")
            for item in packet.role_assignments:
                st.markdown(f"- {item}")
    with evidence_tab:
        if packet.analogs:
            analog_rows = []
            for row in packet.analogs:
                analog_rows.append(
                    {
                        "recall_number": row.get("recall_number"),
                        "event_id": row.get("event_id") or "Not reported",
                        "report_date": row.get("report_date") or "Not reported",
                        "classification": row.get("classification") or "Not reported",
                        "firm": row.get("recalling_firm") or "Not reported",
                        "official_source": official_source_url(row.get("recall_number")),
                    }
                )
            st.dataframe(
                analog_rows,
                width="stretch",
                hide_index=True,
                column_config={
                    "official_source": st.column_config.LinkColumn("Official openFDA query")
                },
            )
        else:
            st.info("No matching historical analogs were found for the selected scope.")
        st.caption(
            "Analogs are selected deterministically from historical product records using the chosen derived product/hazard categories, classification, and date range."
        )
    with debrief_tab:
        st.subheader("Debrief questions")
        for item in packet.debrief:
            st.markdown(f"- {item}")
        st.subheader("Assumptions and limitations")
        for item in packet.assumptions:
            st.markdown(f"- {item}")
    st.download_button("Download Markdown exercise packet", packet.markdown, "recallready-tabletop.md", "text/markdown")
