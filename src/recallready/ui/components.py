"""Shared Streamlit components and safe database access."""
from __future__ import annotations

import csv
import io
import json
import tempfile
from pathlib import Path
from urllib.parse import quote

import streamlit as st

from recallready.data.snapshot import build_runtime_database
from recallready.db.repository import RecallRepository
from recallready.ui.formatting import freshness_label


@st.cache_resource(max_entries=1)
def repository() -> RecallRepository | None:
    """Open the derived database read-only when a validated artifact exists."""
    snapshot = Path("data/recalls.parquet")
    if not snapshot.exists():
        return None
    runtime = Path(tempfile.gettempdir()) / "recallready-runtime.sqlite"
    if not runtime.exists() or runtime.stat().st_mtime < snapshot.stat().st_mtime:
        build_runtime_database(snapshot, runtime)
    return RecallRepository(runtime)

@st.cache_data(max_entries=1, ttl=300)
def metadata() -> dict[str, object] | None:
    """Load public snapshot metadata without reading raw records."""
    path = Path("data/snapshot_metadata.json")
    return json.loads(path.read_text()) if path.exists() else None

def chrome() -> None:
    """Render persistent safety and freshness information."""
    st.info("Historical enforcement records for informational analysis—not an alert feed or current safety determination.")
    st.caption(freshness_label(metadata()))
    st.caption("For current consumer recall information, visit the [FDA recalls, market withdrawals, and safety alerts](https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts).")

def missing_data() -> None:
    """Explain recovery without crashing when deployment data is absent or invalid."""
    st.warning("Validated snapshot data is not loaded. Run `python -m scripts.refresh_data --sample-size 25` or deploy a reviewed snapshot and SQLite artifact.")

def official_source_url(recall_number: object) -> str | None:
    """Create a safely encoded openFDA query link from a source recall number."""
    if not isinstance(recall_number, str) or not recall_number or len(recall_number) > 100:
        return None
    return "https://api.fda.gov/food/enforcement.json?search=" + quote(f'recall_number:"{recall_number}"', safe="")

def csv_export(rows: list[dict[str, object]], fields: list[str], cap: int = 200) -> str:
    """Export only allowlisted fields and a bounded number of rows."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows[:cap])
    return output.getvalue()
