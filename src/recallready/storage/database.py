"""Read-only SQLite connection helper for future snapshot queries."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def connect_readonly(database_path: Path) -> sqlite3.Connection:
    """Open an existing SQLite database in read-only mode."""
    resolved_path = database_path.resolve(strict=True)
    connection = sqlite3.connect(f"file:{resolved_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection
