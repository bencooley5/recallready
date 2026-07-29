"""Small accessible display helpers."""
from __future__ import annotations


def freshness_label(metadata: dict[str, object] | None) -> str:
    """Build a safe source freshness label."""
    if not metadata:
        return "Snapshot metadata unavailable"
    return f"Source updated: {metadata.get('source_last_updated') or 'unknown'} · ingested: {metadata.get('ingestion_completed_at') or 'unknown'}"

def percent(value: float | None) -> str:
    """Format nullable ratios without implying precision where unavailable."""
    return "—" if value is None else f"{value:.1%}"
