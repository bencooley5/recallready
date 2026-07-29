"""Strict models and JSON schemas for the analyst's allowlisted tools."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Filters(BaseModel):
    """Bounded structured filters; never raw SQL fragments."""

    model_config = ConfigDict(extra="forbid")
    start_date: str | None = None
    end_date: str | None = None
    classifications: list[str] = Field(default_factory=list, max_length=10)
    states: list[str] = Field(default_factory=list, max_length=20)
    product_categories: list[str] = Field(default_factory=list, max_length=20)


class SearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filters: Filters = Field(default_factory=Filters)
    query: str = Field(max_length=500)
    limit: int = Field(default=25, ge=1, le=50)


class GroupArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filters: Filters = Field(default_factory=Filters)
    dimension: Literal["classification", "product_category", "state", "hazard"]
    metric: Literal["product_records", "unique_events"] = "product_records"
    top_n: int = Field(default=10, ge=1, le=25)
    time_grain: Literal["all", "month"] = "all"


class DetailArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recall_number_or_source_record_id: str = Field(min_length=1, max_length=128)


class EventArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(min_length=1, max_length=128)


class MethodologyArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: Literal["source", "taxonomy", "metrics", "limitations", "freshness"]


class FinalAnswer(BaseModel):
    """Validated model output; claims are checked against tool evidence separately."""

    model_config = ConfigDict(extra="forbid")
    answer_markdown: str = Field(max_length=4000)
    answer_type: Literal["analysis", "limitation", "methodology", "refusal"]
    data_scope: str
    metric_definitions: list[str] = Field(default_factory=list, max_length=8)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    limitations: list[str] = Field(default_factory=list, max_length=8)
    suggested_followups: list[str] = Field(default_factory=list, max_length=5)


def tool_definition(name: str, model: type[BaseModel], description: str) -> dict[str, object]:
    """Produce one strict Responses API function definition."""
    schema = model.model_json_schema()
    schema["additionalProperties"] = False
    return {"type": "function", "name": name, "description": description, "parameters": schema, "strict": True}
