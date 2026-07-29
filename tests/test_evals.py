"""Offline chat evaluation suite tests."""

from recallready.evals import run_offline_cases


def test_chat_evaluation_suite_is_repeatable_and_offline() -> None:
    result = run_offline_cases()
    assert result["cases"] >= 25
    assert result["live_api_enabled"] == 0
