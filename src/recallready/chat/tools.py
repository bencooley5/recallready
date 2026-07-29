"""Validated dispatchers over the trusted repository; no SQL is accepted here."""

from __future__ import annotations

from pathlib import Path

from recallready.chat.schemas import (
    CompareArgs,
    DetailArgs,
    EventArgs,
    Filters,
    GroupArgs,
    MethodologyArgs,
    SearchArgs,
    TabletopEvidenceArgs,
)
from recallready.db.queries import CategoryDimension
from recallready.db.repository import RecallRepository, RecordFilters


class ToolDispatcher:
    """Expose only compact, safe database operations to the model."""

    def __init__(self, repository: RecallRepository, metadata: dict[str, object] | None, max_rows: int) -> None:
        self.repository, self.metadata, self.max_rows = repository, metadata or {}, max_rows

    def dispatch(self, name: str, arguments: dict[str, object]) -> dict[str, object]:
        """Validate and execute an exact allowlisted tool name."""
        handlers = {"get_summary": self.summary, "search_recall_records": self.search, "group_recall_records": self.group, "get_recall_detail": self.detail, "get_event_detail": self.event, "get_methodology": self.methodology, "build_tabletop_evidence": self.tabletop, "compare_segments": self.compare}
        if name not in handlers:
            raise ValueError("unsupported tool")
        return handlers[name](arguments)

    def summary(self, raw: dict[str, object]) -> dict[str, object]:
        filters = _filters(Filters.model_validate(raw.get("filters", {})))
        return self._result(self.repository.summary_metrics(filters), [])

    def search(self, raw: dict[str, object]) -> dict[str, object]:
        args = SearchArgs.model_validate(raw)
        rows = self.repository.full_text_search(args.query, _filters(args.filters), limit=min(args.limit, self.max_rows))
        return self._result(rows, _refs(rows))

    def group(self, raw: dict[str, object]) -> dict[str, object]:
        args = GroupArgs.model_validate(raw)
        dimension = {"classification": CategoryDimension.CLASSIFICATION, "product_category": CategoryDimension.PRODUCT_CATEGORY, "state": CategoryDimension.STATE, "hazard": CategoryDimension.TAG_VALUE}[args.dimension]
        rows = self.repository.categorical_time_series(dimension, _filters(args.filters), limit=args.top_n) if args.time_grain == "month" else self.repository.categorical_aggregation(dimension, _filters(args.filters), limit=args.top_n)
        return self._result(rows, [])

    def detail(self, raw: dict[str, object]) -> dict[str, object]:
        args = DetailArgs.model_validate(raw)
        detail = self.repository.recall_detail(args.recall_number_or_source_record_id)
        return self._result(detail or {}, _refs([detail] if detail else []))

    def event(self, raw: dict[str, object]) -> dict[str, object]:
        rows = self.repository.event_detail(EventArgs.model_validate(raw).event_id)
        return self._result(rows[:self.max_rows], _refs(rows))

    def methodology(self, raw: dict[str, object]) -> dict[str, object]:
        topic = MethodologyArgs.model_validate(raw).topic
        text = Path("docs/METHODOLOGY.md").read_text(encoding="utf-8") if Path("docs/METHODOLOGY.md").exists() else "Methodology text unavailable."
        return self._result({"topic": topic, "approved_methodology": text[:3000]}, [])

    def tabletop(self, raw: dict[str, object]) -> dict[str, object]:
        args = TabletopEvidenceArgs.model_validate(raw)
        rows = self.repository.search_records(_filters(args.filters), limit=min(args.limit, self.max_rows))
        return self._result(rows, _refs(rows))

    def compare(self, raw: dict[str, object]) -> dict[str, object]:
        # Segments are structured filters; comparison is descriptive counts only.
        args = CompareArgs.model_validate(raw)
        a, b = _filters(args.segment_a), _filters(args.segment_b)
        return self._result({"segment_a": self.repository.summary_metrics(a), "segment_b": self.repository.summary_metrics(b)}, [])

    def _result(self, data: object, refs: list[str]) -> dict[str, object]:
        return {"data": data, "data_scope": "Historical openFDA food enforcement records; report_date basis unless tool output specifies otherwise.", "source_last_updated": self.metadata.get("source_last_updated"), "metric_definitions": ["Product records are source product-record rows; known events are distinct non-null event IDs."], "evidence_refs": refs[:20]}


def _filters(value: Filters) -> RecordFilters:
    return RecordFilters(
        start_date=value.start_date,
        end_date=value.end_date,
        classifications=tuple(value.classifications),
        states=tuple(value.states),
        product_categories=tuple(value.product_categories),
    )


def _refs(rows: list[dict[str, object]]) -> list[str]:
    return [str(row.get("recall_number") or row.get("source_record_id")) for row in rows if row.get("recall_number") or row.get("source_record_id")]
