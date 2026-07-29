"""Typed, environment-backed settings for RecallReady."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


class SettingsError(ValueError):
    """Raised when a configuration value is invalid."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings resolved from environment variables without storing secrets."""

    openfda_api_key: str | None
    openai_api_key: str | None
    openai_model: str | None
    chat_enabled: bool
    max_chat_turns_per_session: int
    max_chat_input_chars: int
    max_tool_result_rows: int
    log_level: str
    project_root: Path

    @property
    def chat_available(self) -> bool:
        """Return whether chat may be offered in this process."""
        return (
            self.chat_enabled
            and self.openai_api_key is not None
            and self.openai_model is not None
        )


def get_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Build validated settings from an environment mapping or process environment."""
    values = os.environ if environ is None else environ
    openai_api_key = _optional_value(values, "OPENAI_API_KEY")
    configured_chat_enabled = _optional_bool(values, "CHAT_ENABLED")
    default_chat_enabled = openai_api_key is not None
    if configured_chat_enabled is None:
        chat_enabled = default_chat_enabled
    else:
        chat_enabled = configured_chat_enabled

    return Settings(
        openfda_api_key=_optional_value(values, "OPENFDA_API_KEY"),
        openai_api_key=openai_api_key,
        openai_model=_optional_value(values, "OPENAI_MODEL"),
        chat_enabled=chat_enabled and openai_api_key is not None,
        max_chat_turns_per_session=_positive_int(
            values, "MAX_CHAT_TURNS_PER_SESSION", default=5
        ),
        max_chat_input_chars=_positive_int(values, "MAX_CHAT_INPUT_CHARS", default=500),
        max_tool_result_rows=_positive_int(values, "MAX_TOOL_RESULT_ROWS", default=50),
        log_level=_log_level(values),
        project_root=Path(__file__).resolve().parents[2],
    )


def _optional_value(values: Mapping[str, str], name: str) -> str | None:
    value = values.get(name, "").strip()
    return value or None


def _optional_bool(values: Mapping[str, str], name: str) -> bool | None:
    value = _optional_value(values, name)
    if value is None:
        return None

    normalized = value.casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise SettingsError(f"{name} must be a boolean value")


def _positive_int(values: Mapping[str, str], name: str, *, default: int) -> int:
    value = _optional_value(values, name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as error:
        raise SettingsError(f"{name} must be an integer") from error
    if parsed < 1:
        raise SettingsError(f"{name} must be greater than zero")
    return parsed


def _log_level(values: Mapping[str, str]) -> str:
    value = _optional_value(values, "LOG_LEVEL")
    level = (value or "INFO").upper()
    if level not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
        raise SettingsError("LOG_LEVEL must be a standard Python logging level")
    return level
