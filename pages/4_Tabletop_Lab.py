"""Educational, deterministic Traceability Tabletop Lab."""

from __future__ import annotations

from datetime import date

import streamlit as st
import yaml

from recallready.analytics.tabletop import TabletopInputs, build_tabletop
from recallready.db.repository import RecordFilters
from recallready.ui.components import chrome, missing_data, repository


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
    hazard = st.selectbox("Derived hazard category", ["", "pathogen_contamination", "undeclared_allergen", "foreign_material", "chemical_or_residue", "labeling_or_misbranding"])
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
    st.subheader("Exercise objective")
    st.write(packet.objective)
    st.subheader("Initial incident narrative")
    st.write(packet.narrative)
    st.subheader("Timed injects")
    st.write(list(packet.injects))
    st.subheader("Historical analogs")
    st.write([{"recall_number": row.get("recall_number"), "event_id": row.get("event_id"), "report_date": row.get("report_date")} for row in packet.analogs])
    st.subheader("Assumptions and limitations")
    st.write(list(packet.assumptions))
    st.download_button("Download Markdown exercise packet", packet.markdown, "recallready-tabletop.md", "text/markdown")
