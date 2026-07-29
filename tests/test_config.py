"""Configuration tests that never require network access or real secrets."""

from __future__ import annotations

import pytest

from recallready.config import SettingsError, get_settings


def test_settings_load_without_real_secrets() -> None:
    """Defaults keep the analyst unavailable when no key is present."""
    settings = get_settings({})

    assert settings.openfda_api_key is None
    assert settings.openai_api_key is None
    assert settings.openai_model is None
    assert settings.chat_enabled is False
    assert settings.chat_available is False
    assert settings.max_chat_turns_per_session == 5
    assert settings.max_chat_input_chars == 500
    assert settings.max_tool_result_rows == 50


def test_chat_cannot_be_enabled_without_a_key() -> None:
    """An explicit flag cannot override the missing-key safety default."""
    settings = get_settings({"CHAT_ENABLED": "true"})

    assert settings.chat_enabled is False
    assert settings.chat_available is False


def test_invalid_chat_limit_is_rejected() -> None:
    """Configuration values fail early instead of silently weakening safeguards."""
    with pytest.raises(SettingsError, match="MAX_CHAT_INPUT_CHARS"):
        get_settings({"MAX_CHAT_INPUT_CHARS": "0"})
