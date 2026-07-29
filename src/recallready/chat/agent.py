"""Bounded Responses API orchestration with validated tool calls and final output."""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Protocol

from recallready.chat.guardrails import preflight, validate_evidence
from recallready.chat.prompts import SYSTEM_PROMPT
from recallready.chat.schemas import (
    DetailArgs,
    EventArgs,
    Filters,
    FinalAnswer,
    GroupArgs,
    MethodologyArgs,
    SearchArgs,
    tool_definition,
)
from recallready.chat.tools import ToolDispatcher
from recallready.config import Settings


class ResponsesClient(Protocol):
    """Small fakeable subset of the OpenAI Responses client."""
    def create(self, **kwargs: object) -> object: ...


TOOL_DEFINITIONS = [
    tool_definition("get_summary", Filters, "Get historical product-record and known-event totals."),
    tool_definition("search_recall_records", SearchArgs, "Search historical source text."),
    tool_definition("group_recall_records", GroupArgs, "Group historical records by an allowlisted dimension."),
    {"type": "function", "name": "compare_segments", "description": "Compare two structured historical segments.", "parameters": {"type": "object", "additionalProperties": False, "properties": {"segment_a": Filters.model_json_schema(), "segment_b": Filters.model_json_schema(), "metric": {"type": "string", "enum": ["product_records", "unique_events"]}}, "required": ["segment_a", "segment_b", "metric"]}, "strict": True},
    tool_definition("get_recall_detail", DetailArgs, "Get a cited record by source ID or recall number."),
    tool_definition("get_event_detail", EventArgs, "Get product records in one event."),
    tool_definition("get_methodology", MethodologyArgs, "Get approved methodology text."),
    {"type": "function", "name": "build_tabletop_evidence", "description": "Get bounded comparable historical evidence.", "parameters": {"type": "object", "additionalProperties": False, "properties": {"filters": Filters.model_json_schema(), "limit": {"type": "integer", "minimum": 1, "maximum": 50}}, "required": ["filters", "limit"]}, "strict": True},
]


class RecallReadyAgent:
    """Execute a maximum number of safe tool rounds and validate final citations."""

    def __init__(self, client: ResponsesClient | None, settings: Settings, dispatcher: ToolDispatcher, dataset_version: str = "unknown") -> None:
        self.client, self.settings, self.dispatcher, self.dataset_version = client, settings, dispatcher, dataset_version
        self._cache: dict[str, FinalAnswer] = {}

    def answer(self, question: str) -> FinalAnswer:
        """Answer one bounded question without logging its full text."""
        blocked = preflight(question, self.settings.max_chat_input_chars)
        if blocked is not None:
            return blocked
        if not self.settings.chat_available or self.client is None or not self.settings.openai_model:
            return FinalAnswer(answer_markdown="Ask RecallReady is unavailable because an OpenAI API key and model are not configured.", answer_type="limitation", data_scope="No database query was run.", metric_definitions=[], evidence_refs=[], limitations=["Chat is disabled."], suggested_followups=[])
        key = sha256(f"{self.dataset_version}:{' '.join(question.casefold().split())}".encode()).hexdigest()
        if key in self._cache:
            return self._cache[key]
        inputs: list[object] = [{"role": "user", "content": question}]
        available: set[str] = set()
        for _ in range(min(self.settings.max_chat_turns_per_session, 4)):
            response = self.client.create(model=self.settings.openai_model, instructions=SYSTEM_PROMPT, input=inputs, tools=TOOL_DEFINITIONS, max_output_tokens=700, store=False, text={"format": {"type": "json_schema", "name": "recallready_answer", "strict": True, "schema": FinalAnswer.model_json_schema()}})
            calls = _calls(response)
            if not calls:
                try:
                    answer = FinalAnswer.model_validate_json(_text(response))
                except Exception:
                    return FinalAnswer(answer_markdown="Ask RecallReady could not validate the model response. Please try again.", answer_type="limitation", data_scope="Tool results were not presented.", metric_definitions=[], evidence_refs=[], limitations=["Malformed structured model output."], suggested_followups=[])
                answer = validate_evidence(answer, available)
                self._cache[key] = answer
                return answer
            for call_id, name, arguments in calls:
                try:
                    result = self.dispatcher.dispatch(name, arguments)
                    references = result.get("evidence_refs", [])
                    if isinstance(references, list):
                        available.update(str(value) for value in references)
                    inputs.append({"type": "function_call_output", "call_id": call_id, "output": json.dumps(result)})
                except Exception:
                    inputs.append({"type": "function_call_output", "call_id": call_id, "output": json.dumps({"error": "Invalid or unsupported tool arguments."})})
        return FinalAnswer(answer_markdown="Ask RecallReady reached its safe tool-call limit.", answer_type="limitation", data_scope="Historical data query incomplete.", metric_definitions=[], evidence_refs=[], limitations=["Tool-call limit reached."], suggested_followups=[])


def _calls(response: object) -> list[tuple[str, str, dict[str, object]]]:
    output = response.get("output", []) if isinstance(response, dict) else getattr(response, "output", [])
    if not isinstance(output, list):
        return []
    calls: list[tuple[str, str, dict[str, object]]] = []
    for item in output:
        value = item if isinstance(item, dict) else vars(item)
        if value.get("type") == "function_call":
            try:
                calls.append((str(value["call_id"]), str(value["name"]), json.loads(str(value["arguments"]))))
            except (KeyError, json.JSONDecodeError):
                calls.append((str(value.get("call_id", "invalid")), "invalid", {}))
    return calls


def _text(response: object) -> str:
    if isinstance(response, dict):
        return str(response.get("output_text", ""))
    return str(getattr(response, "output_text", ""))
