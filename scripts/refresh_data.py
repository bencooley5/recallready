"""Fetch, normalize, validate, and stage a reproducible RecallReady snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from recallready.config import get_settings
from recallready.data.normalize import normalize_record
from recallready.data.openfda_client import OpenFDAClient, OpenFDAClientError
from recallready.data.snapshot import refresh_snapshot


def parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse bounded refresh options; snapshots are written only after validation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-size", type=int)
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-database-build", action="store_true")
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the safe refresh pipeline and return documented process exit codes."""
    args = parse_args(arguments)
    if args.sample_size is not None and args.sample_size < 1:
        print("--sample-size must be greater than zero", file=sys.stderr)
        return 2
    settings = get_settings()
    try:
        with OpenFDAClient(api_key=settings.openfda_api_key) as client:
            records = [normalize_record(record, source_metadata=client.last_metadata) for record in client.iter_records(sample_size=args.sample_size)]
            metadata, report = refresh_snapshot(
                records, args.output_dir, source_last_updated=client.last_metadata.last_updated if client.last_metadata else None,
                source_total_matches=client.last_metadata.total_matches if client.last_metadata else None,
                force=args.force, dry_run=args.dry_run, skip_database_build=args.skip_database_build,
            )
    except (OpenFDAClientError, ValueError, OSError) as error:
        print(f"Refresh failed safely: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"metadata": metadata, "validation": report.as_dict()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
