"""Deterministic pre-model safety handling and evidence validation."""

from __future__ import annotations

from typing import Literal

from recallready.chat.schemas import FinalAnswer


def preflight(question: str, maximum: int) -> FinalAnswer | None:
    """Return a bounded safe reply for unsupported questions before any model call."""
    lower = question.casefold()
    if len(question) > maximum:
        return _reply("Please shorten the question and try again.", "limitation")
    if any(phrase in lower for phrase in ("safe today", "safe to eat", "should i eat", "active recall", "current recall")):
        return _reply("RecallReady cannot determine whether a product is safe today or provide consumer-action guidance. Consult current official FDA or USDA public-warning resources.", "refusal")
    if any(phrase in lower for phrase in ("worst company", "most dangerous", "dangerous company", "negligent")):
        return _reply("This historical source cannot support a ranking of companies as worst or dangerous. I can provide a descriptive comparison of historical record counts with stated limitations instead.", "limitation")
    return None


def validate_evidence(answer: FinalAnswer, available: set[str]) -> FinalAnswer:
    """Remove unsupported evidence claims and add a transparent limitation."""
    unsupported = [reference for reference in answer.evidence_refs if reference not in available]
    if not unsupported:
        return answer
    return answer.model_copy(update={"evidence_refs": [ref for ref in answer.evidence_refs if ref in available], "limitations": [*answer.limitations, "Some proposed evidence references were not returned by trusted tools and were removed."]})


def _reply(text: str, answer_type: Literal["limitation", "refusal"]) -> FinalAnswer:
    return FinalAnswer(answer_markdown=text, answer_type=answer_type, data_scope="No database query was run.", metric_definitions=[], evidence_refs=[], limitations=["Historical records cannot determine current safety or lifecycle."], suggested_followups=[])
