"""Structured logging that avoids recording user or credential content."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

_SENSITIVE_KEY_PATTERN = re.compile(r"(api[_-]?key|authorization|token|secret|password)", re.I)


class JsonFormatter(logging.Formatter):
    """Emit small JSON log records suitable for public deployment diagnostics."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a record while redacting sensitive structured attributes."""
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": _redact_text(record.getMessage()),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, sort_keys=True, default=str)


def configure_logging(level: str = "INFO") -> logging.Logger:
    """Configure and return the application logger without logging request contents."""
    logger = logging.getLogger("recallready")
    logger.setLevel(level)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)

    return logger


def _redact_text(message: str) -> str:
    """Redact values in common secret-bearing key/value log fragments."""
    redacted_parts: list[str] = []
    for part in message.split():
        key, separator, _value = part.partition("=")
        if separator and _SENSITIVE_KEY_PATTERN.search(key):
            redacted_parts.append(f"{key}=[REDACTED]")
        else:
            redacted_parts.append(part)
    return " ".join(redacted_parts)
