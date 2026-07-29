"""Read-only, parameterized repository API for RecallReady queries."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, replace
from pathlib import Path
from statistics import median

from recallready.db.queries import (
    CATEGORY_SQL,
    DATE_SQL,
    SORT_SQL,
    CategoryDimension,
    DateBasis,
    SortOption,
)

MAX_RESULT_ROWS = 200
MAX_ANALYTICS_ROWS = 5_000

_RECORD_SELECT = """SELECT r.*,
    COALESCE((SELECT t.tag_value FROM recall_tags t
              WHERE t.source_record_id = r.source_record_id AND t.tag_type = 'hazard'
              ORDER BY t.rule_id LIMIT 1), 'other_or_unclear') AS primary_hazard
    FROM recall_records r"""


@dataclass(frozen=True, slots=True)
class RecordFilters:
    """Typed values accepted by trusted record queries."""

    start_date: str | None = None
    end_date: str | None = None
    classifications: tuple[str, ...] = ()
    states: tuple[str, ...] = ()
    product_categories: tuple[str, ...] = ()
    include_missing_event_ids: bool = True
    keyword: str = ""
    date_basis: DateBasis = DateBasis.REPORT_DATE


class RecallRepository:
    """Expose only reviewed query operations over a read-only SQLite connection."""

    def __init__(self, database_path: Path) -> None:
        # Streamlit caches this read-only repository as a shared resource and can
        # serve different page requests from different threads. SQLite is opened
        # read-only, so cross-thread access cannot mutate the derived database.
        self._connection = sqlite3.connect(
            f"file:{database_path.resolve()}?mode=ro", uri=True, check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row

    def close(self) -> None:
        """Close the read-only connection."""
        self._connection.close()

    def search_records(
        self,
        filters: RecordFilters = RecordFilters(),
        *,
        limit: int = 50,
        sort: SortOption = SortOption.REPORT_DATE_DESC,
    ) -> list[dict[str, object]]:
        """Return filtered product-record rows using only allowlisted sort fragments."""
        where, parameters = _where_clause(filters)
        sql = f"{_RECORD_SELECT} {where} ORDER BY {SORT_SQL[sort]} LIMIT ?"
        return _rows(self._connection.execute(sql, (*parameters, _limit(limit))))

    def full_text_search(
        self, query: str, filters: RecordFilters = RecordFilters(), *, limit: int = 50
    ) -> list[dict[str, object]]:
        """Search FTS5 content with a bound query value and trusted filters."""
        if not query.strip():
            return []
        where, parameters = _where_clause(replace(filters, keyword=""), prefix="r")
        filter_sql = where.removeprefix("WHERE ")
        conditions = "recall_records_fts MATCH ?"
        if filter_sql:
            conditions = f"{conditions} AND {filter_sql}"
        sql = (
            "SELECT r.*, COALESCE((SELECT t.tag_value FROM recall_tags t "
            "WHERE t.source_record_id = r.source_record_id AND t.tag_type = 'hazard' "
            "ORDER BY t.rule_id LIMIT 1), 'other_or_unclear') AS primary_hazard "
            "FROM recall_records_fts f JOIN recall_records r ON r.rowid = f.rowid "
            f"WHERE {conditions} "
            "ORDER BY bm25(recall_records_fts) LIMIT ?"
        )
        return _rows(
            self._connection.execute(
                sql, (_safe_fts_query(query), *parameters, _limit(limit))
            )
        )

    def recall_detail(self, source_record_id: str) -> dict[str, object] | None:
        """Return one record by source ID or recall number with taxonomy tags."""
        row = self._connection.execute(
            """SELECT * FROM recall_records
            WHERE source_record_id = ? OR recall_number = ?
            ORDER BY CASE WHEN source_record_id = ? THEN 0 ELSE 1 END, report_date DESC
            LIMIT 1""",
            (source_record_id, source_record_id, source_record_id),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["tags"] = _rows(
            self._connection.execute(
                "SELECT * FROM recall_tags WHERE source_record_id = ? ORDER BY rule_id",
                (source_record_id,),
            )
        )
        return result

    def event_detail(self, event_id: str) -> list[dict[str, object]]:
        """Return all records for an explicit FDA event identifier."""
        return _rows(
            self._connection.execute(
                "SELECT * FROM recall_records WHERE event_id = ? ORDER BY recall_number",
                (event_id,),
            )
        )

    def summary_metrics(self, filters: RecordFilters = RecordFilters()) -> dict[str, int]:
        """Return exact filtered metrics at explicit product-record/event grain."""
        where, parameters = _where_clause(filters)
        sql = f"""SELECT COUNT(*) AS product_record_count,
            COUNT(DISTINCT CASE WHEN r.event_id IS NOT NULL AND r.event_id != '' THEN r.event_id END) AS unique_event_count,
            SUM(CASE WHEN r.event_id IS NULL OR r.event_id = '' THEN 1 ELSE 0 END) AS missing_event_id_count,
            COUNT(DISTINCT CASE WHEN r.firm_normalized IS NOT NULL AND r.firm_normalized != '' THEN r.firm_normalized END) AS unique_normalized_firm_count,
            SUM(CASE WHEN r.classification = 'Class I' THEN 1 ELSE 0 END) AS class_i_record_count,
            SUM(CASE WHEN r.classification IS NOT NULL AND r.classification != '' THEN 1 ELSE 0 END) AS classified_record_count,
            SUM(CASE WHEN r.reporting_lag_days IS NOT NULL THEN 1 ELSE 0 END) AS reporting_lag_eligible_count,
            SUM(CASE WHEN r.product_description IS NOT NULL AND r.product_description != '' THEN 1 ELSE 0 END) AS product_description_present_count
            FROM recall_records r {where}"""
        row = self._connection.execute(sql, parameters).fetchone()
        return {key: int(row[key] or 0) for key in row.keys()}

    def median_reporting_lag(self, filters: RecordFilters = RecordFilters()) -> float | None:
        """Return the exact median lag for filtered records with two valid source dates."""
        where, parameters = _where_clause(filters)
        where = _with_condition(where, "r.reporting_lag_days IS NOT NULL")
        rows = self._connection.execute(
            f"SELECT r.reporting_lag_days FROM recall_records r {where}", parameters
        ).fetchall()
        values = [int(row[0]) for row in rows]
        return float(median(values)) if values else None

    def time_series(self, filters: RecordFilters = RecordFilters()) -> list[dict[str, object]]:
        """Aggregate record and known-event counts by the allowlisted date basis."""
        where, parameters = _where_clause(filters)
        date_column = DATE_SQL[filters.date_basis]
        where = _with_condition(where, f"{date_column} IS NOT NULL")
        sql = f"""SELECT substr({date_column}, 1, 7) AS period, COUNT(*) AS product_record_count,
            COUNT(DISTINCT CASE WHEN r.event_id IS NOT NULL AND r.event_id != '' THEN r.event_id END) AS unique_event_count
            FROM recall_records r {where} GROUP BY period ORDER BY period"""
        return _rows(self._connection.execute(sql, parameters))

    def categorical_time_series(
        self,
        dimension: CategoryDimension,
        filters: RecordFilters = RecordFilters(),
        *,
        limit: int = MAX_ANALYTICS_ROWS,
    ) -> list[dict[str, object]]:
        """Return reviewed monthly category counts for deterministic mix comparisons."""
        column = CATEGORY_SQL[dimension]
        join = (
            " JOIN recall_tags t ON t.source_record_id = r.source_record_id"
            if dimension is CategoryDimension.TAG_VALUE
            else ""
        )
        where, parameters = _where_clause(filters)
        date_column = DATE_SQL[filters.date_basis]
        where = _with_condition(where, f"{date_column} IS NOT NULL")
        if dimension is CategoryDimension.TAG_VALUE:
            where = _with_condition(where, "t.tag_type = 'hazard'")
        sql = (
            f"SELECT substr({date_column}, 1, 7) AS period, {column} AS value, "
            "COUNT(DISTINCT r.source_record_id) AS product_record_count "
            f"FROM recall_records r{join} {where}"
            " GROUP BY period, value ORDER BY period, product_record_count DESC, value LIMIT ?"
        )
        return _rows(self._connection.execute(sql, (*parameters, _analytics_limit(limit))))

    def categorical_aggregation(
        self,
        dimension: CategoryDimension,
        filters: RecordFilters = RecordFilters(),
        *,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        """Aggregate by a reviewed categorical dimension, never a caller-supplied column."""
        column = CATEGORY_SQL[dimension]
        join = (
            " JOIN recall_tags t ON t.source_record_id = r.source_record_id"
            if dimension is CategoryDimension.TAG_VALUE
            else ""
        )
        where, parameters = _where_clause(filters)
        if dimension is CategoryDimension.TAG_VALUE:
            where = _with_condition(where, "t.tag_type = 'hazard'")
        sql = f"SELECT {column} AS value, COUNT(DISTINCT r.source_record_id) AS product_record_count, COUNT(DISTINCT r.event_id) AS unique_event_count FROM recall_records r{join} {where} GROUP BY value ORDER BY product_record_count DESC, value LIMIT ?"
        return _rows(self._connection.execute(sql, (*parameters, _limit(limit))))

    def segment_comparison(
        self, dimension: CategoryDimension, filters: RecordFilters = RecordFilters()
    ) -> list[dict[str, object]]:
        """Return a capped categorical comparison using the same trusted dimension allowlist."""
        return self.categorical_aggregation(dimension, filters, limit=MAX_RESULT_ROWS)

    def hazard_product_combinations(
        self, filters: RecordFilters = RecordFilters(), *, limit: int = 20
    ) -> list[dict[str, object]]:
        """Count derived hazard/product-category combinations from reviewed taxonomy tags."""
        where, parameters = _where_clause(filters)
        condition = "t.tag_type = 'hazard'"
        if where:
            condition = f"{condition} AND {where.removeprefix('WHERE ')}"
        sql = (
            "SELECT t.tag_value AS primary_hazard, r.derived_product_category, "
            "COUNT(DISTINCT r.source_record_id) AS product_record_count "
            "FROM recall_records r JOIN recall_tags t ON t.source_record_id = r.source_record_id "
            f"WHERE {condition} GROUP BY t.tag_value, r.derived_product_category "
            "ORDER BY product_record_count DESC, primary_hazard, derived_product_category LIMIT ?"
        )
        return _rows(self._connection.execute(sql, (*parameters, _limit(limit))))

    def available_values(
        self, dimension: CategoryDimension, *, limit: int = MAX_RESULT_ROWS
    ) -> list[str]:
        """Return bounded distinct values for an allowlisted public filter dimension."""
        column = CATEGORY_SQL[dimension]
        join = (
            " JOIN recall_tags t ON t.source_record_id = r.source_record_id"
            if dimension is CategoryDimension.TAG_VALUE
            else ""
        )
        condition = f"{column} IS NOT NULL AND {column} != ''"
        if dimension is CategoryDimension.TAG_VALUE:
            condition += " AND t.tag_type = 'hazard'"
        rows = self._connection.execute(
            f"SELECT DISTINCT {column} AS value FROM recall_records r{join} "
            f"WHERE {condition} ORDER BY value LIMIT ?",
            (_limit(limit),),
        ).fetchall()
        return [str(row["value"]) for row in rows]

    def reporting_lag_distribution(
        self, filters: RecordFilters = RecordFilters()
    ) -> list[dict[str, object]]:
        """Return transparent 30-day lag bands, keeping long lags in an explicit tail."""
        where, parameters = _where_clause(filters)
        where = _with_condition(where, "r.reporting_lag_days IS NOT NULL")
        sql = f"""SELECT
            CASE
              WHEN r.reporting_lag_days < 0 THEN -30
              WHEN r.reporting_lag_days >= 365 THEN 365
              ELSE CAST(r.reporting_lag_days / 30 AS INTEGER) * 30
            END AS bin_start,
            COUNT(*) AS product_record_count
            FROM recall_records r {where}
            GROUP BY bin_start ORDER BY bin_start"""
        return _rows(self._connection.execute(sql, parameters))

    def data_completeness(self, filters: RecordFilters = RecordFilters()) -> dict[str, int]:
        """Report source-field completeness without replacing or inferring null values."""
        where, parameters = _where_clause(filters)
        sql = f"""SELECT COUNT(*) AS total_records,
            SUM(CASE WHEN r.event_id IS NULL OR r.event_id = '' THEN 1 ELSE 0 END) AS missing_event_id,
            SUM(CASE WHEN r.product_description IS NULL OR r.product_description = '' THEN 1 ELSE 0 END) AS missing_product_description,
            SUM(CASE WHEN r.reason_for_recall IS NULL OR r.reason_for_recall = '' THEN 1 ELSE 0 END) AS missing_reason_for_recall
            FROM recall_records r {where}"""
        row = self._connection.execute(sql, parameters).fetchone()
        return {key: int(row[key] or 0) for key in row.keys()}

    def data_quality_by_year(self) -> list[dict[str, object]]:
        """Report year-level source completeness without filling missing values."""
        sql = """SELECT substr(report_date, 1, 4) AS year, COUNT(*) AS product_record_count,
        SUM(CASE WHEN event_id IS NULL OR event_id = '' THEN 1 ELSE 0 END) AS missing_event_id,
        SUM(CASE WHEN product_description IS NULL OR product_description = '' THEN 1 ELSE 0 END) AS missing_product_description,
        SUM(CASE WHEN reason_for_recall IS NULL OR reason_for_recall = '' THEN 1 ELSE 0 END) AS missing_reason_for_recall,
        SUM(CASE WHEN derived_product_category = 'unknown' THEN 1 ELSE 0 END) AS unknown_product_category
        FROM recall_records GROUP BY year ORDER BY year"""
        return _rows(self._connection.execute(sql))


def _where_clause(filters: RecordFilters, *, prefix: str = "r") -> tuple[str, list[object]]:
    clauses: list[str] = []
    parameters: list[object] = []
    date_column = DATE_SQL[filters.date_basis].replace("r.", f"{prefix}.")
    if filters.start_date is not None:
        clauses.append(f"{date_column} >= ?")
        parameters.append(filters.start_date)
    if filters.end_date is not None:
        clauses.append(f"{date_column} <= ?")
        parameters.append(filters.end_date)
    for column, values in (
        ("classification", filters.classifications),
        ("state", filters.states),
        ("derived_product_category", filters.product_categories),
    ):
        if values:
            clauses.append(f"{prefix}.{column} IN ({','.join('?' for _ in values)})")
            parameters.extend(values)
    if not filters.include_missing_event_ids:
        clauses.append(f"{prefix}.event_id IS NOT NULL AND {prefix}.event_id != ''")
    if filters.keyword.strip():
        clauses.append(
            f"{prefix}.rowid IN (SELECT rowid FROM recall_records_fts "
            "WHERE recall_records_fts MATCH ?)"
        )
        parameters.append(_safe_fts_query(filters.keyword))
    return (f"WHERE {' AND '.join(clauses)}" if clauses else "", parameters)


def _limit(value: int) -> int:
    if value < 1:
        raise ValueError("limit must be positive")
    return min(value, MAX_RESULT_ROWS)


def _analytics_limit(value: int) -> int:
    if value < 1:
        raise ValueError("limit must be positive")
    return min(value, MAX_ANALYTICS_ROWS)


def _safe_fts_query(value: str) -> str:
    """Treat public keyword text as one FTS phrase, never as FTS query syntax."""
    cleaned = " ".join(value.split())[:500]
    return f'"{cleaned.replace(chr(34), chr(34) * 2)}"'


def _with_condition(where: str, condition: str) -> str:
    return f"{where} AND {condition}" if where else f"WHERE {condition}"


def _rows(cursor: sqlite3.Cursor) -> list[dict[str, object]]:
    return [dict(row) for row in cursor.fetchall()]
