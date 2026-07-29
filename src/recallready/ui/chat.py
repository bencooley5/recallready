"""Small, session-only helpers for the Ask RecallReady page."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from recallready.chat.schemas import FinalAnswer

MAX_VISIBLE_TURNS = 5
COOLDOWN_SECONDS = 2.0


@dataclass(frozen=True, slots=True)
class ChatTurn:
    """A safe, bounded transcript item kept only in Streamlit session state."""

    question: str
    answer: FinalAnswer


def can_submit(turns: list[ChatTurn], question: str, *, max_turns: int, last_request: float | None) -> str | None:
    """Return a user-safe reason a question cannot be submitted, if any."""
    if not question.strip():
        return "Enter a short historical-analysis question."
    if len(turns) >= min(max_turns, MAX_VISIBLE_TURNS):
        return "This session has reached its chat-turn limit. Clear chat to begin again."
    if last_request is not None and monotonic() - last_request < COOLDOWN_SECONDS:
        return "Please wait a moment before sending another question."
    return None


def append_turn(turns: list[ChatTurn], question: str, answer: FinalAnswer) -> list[ChatTurn]:
    """Keep only the bounded, recent in-memory chat transcript."""
    return [*turns, ChatTurn(question, answer)][-MAX_VISIBLE_TURNS:]


def answer_has_valid_evidence(answer: FinalAnswer, known_refs: set[str]) -> bool:
    """Require every rendered factual evidence reference to be resolvable."""
    return all(reference in known_refs for reference in answer.evidence_refs)
