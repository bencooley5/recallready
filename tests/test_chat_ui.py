"""Non-rendering smoke tests for session-only Ask RecallReady behavior."""

from __future__ import annotations

from recallready.chat.schemas import FinalAnswer
from recallready.ui.chat import ChatTurn, answer_has_valid_evidence, append_turn, can_submit


def _answer(refs: list[str] | None = None) -> FinalAnswer:
    return FinalAnswer(answer_markdown="Historical answer", answer_type="analysis", data_scope="historical", metric_definitions=[], evidence_refs=refs or [], limitations=[], suggested_followups=[])


def test_disabled_mode_and_session_limit_are_bounded() -> None:
    turns = [ChatTurn("q", _answer()) for _ in range(5)]
    assert "limit" in str(can_submit(turns, "next", max_turns=5, last_request=None))


def test_successful_fake_answer_and_invalid_evidence() -> None:
    answer = _answer(["F-1"])
    assert answer_has_valid_evidence(answer, {"F-1"})
    assert not answer_has_valid_evidence(answer, set())


def test_append_turn_is_session_only_and_bounded() -> None:
    turns: list[ChatTurn] = []
    for index in range(7):
        turns = append_turn(turns, f"q{index}", _answer())
    assert len(turns) == 5
