"""Print the last machine-readable snapshot validation report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    path = args.output_dir / "validation_report.json"
    if not path.exists():
        print("No validation report found", file=sys.stderr)
        return 1
    report = json.loads(path.read_text(encoding="utf-8"))
    print(json.dumps(report, sort_keys=True))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
