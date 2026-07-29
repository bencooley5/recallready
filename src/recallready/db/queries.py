"""Allowlisted SQL fragments used solely by the trusted repository."""

from __future__ import annotations

from enum import StrEnum


class SortOption(StrEnum):
    REPORT_DATE_DESC = "report_date_desc"
    REPORT_DATE_ASC = "report_date_asc"
    RECALL_NUMBER_ASC = "recall_number_asc"


class CategoryDimension(StrEnum):
    CLASSIFICATION = "classification"
    PRODUCT_CATEGORY = "product_category"
    STATE = "state"
    FIRM_NORMALIZED = "firm_normalized"
    TAG_VALUE = "tag_value"


SORT_SQL = {
    SortOption.REPORT_DATE_DESC: "r.report_date DESC, r.source_record_id ASC",
    SortOption.REPORT_DATE_ASC: "r.report_date ASC, r.source_record_id ASC",
    SortOption.RECALL_NUMBER_ASC: "r.recall_number ASC, r.source_record_id ASC",
}
CATEGORY_SQL = {
    CategoryDimension.CLASSIFICATION: "r.classification",
    CategoryDimension.PRODUCT_CATEGORY: "r.derived_product_category",
    CategoryDimension.STATE: "r.state",
    CategoryDimension.FIRM_NORMALIZED: "r.firm_normalized",
    CategoryDimension.TAG_VALUE: "t.tag_value",
}
