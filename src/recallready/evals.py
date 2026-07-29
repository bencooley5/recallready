"""Offline deterministic chat-evaluation loader; live runs require explicit opt-in."""

from __future__ import annotations

import os
from pathlib import Path

import yaml


def load_chat_cases(path: Path = Path("evals/chat_cases.yml")) -> list[dict[str, str]]:
    """Load versioned cases without calling an API."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return list(document["cases"])


def run_offline_cases(path: Path = Path("evals/chat_cases.yml")) -> dict[str, int]:
    """Validate minimum suite size and allowlist-oriented case shape for CI."""
    cases = load_chat_cases(path)
    if len(cases) < 25 or any("expected_tool" not in case for case in cases):
        raise ValueError("chat evaluation suite is incomplete")
    return {"cases": len(cases), "live_api_enabled": int(os.getenv("RECALLREADY_RUN_LIVE_EVALS") == "1")}
