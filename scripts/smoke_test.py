"""Offline deployment smoke test for public snapshot artifacts."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from recallready.data.snapshot import build_runtime_database
from recallready.db.repository import RecallRepository


def main() -> None:
    """Verify a snapshot database, one summary query, one FTS query, and page imports."""
    data = Path("data")
    if not (data / "recalls.parquet").exists() or not (data / "snapshot_metadata.json").exists():
        raise SystemExit("Missing committed public snapshot artifacts: recalls.parquet and snapshot_metadata.json")
    database = Path("/tmp/recallready-smoke.sqlite")
    build_runtime_database(data / "recalls.parquet", database)
    repo = RecallRepository(database)
    try:
        repo.summary_metrics()
        repo.full_text_search("food", limit=1)
    finally:
        repo.close()
    for page in Path("pages").glob("*.py"):
        if importlib.util.spec_from_file_location(page.stem, page) is None:
            raise SystemExit(f"Cannot import page specification: {page}")
    print("RecallReady smoke test passed")


if __name__ == "__main__":
    main()
