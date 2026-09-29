"""CLI for the offline SQLite to PostgreSQL tenant migration."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from ragbot.database.legacy_migration import (
    dry_run_report,
    migrate_snapshot,
    read_legacy_snapshot,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Migrate legacy TenantRAG SQLite tenant data to PostgreSQL."
    )
    parser.add_argument("--source", required=True, type=Path, help="Legacy tenants.db path")
    parser.add_argument(
        "--target-url",
        help="PostgreSQL URL. Required unless --dry-run is used.",
    )
    parser.add_argument(
        "--source-timezone",
        help="IANA timezone for naive legacy timestamps, for example Asia/Tehran.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report source rows without writing PostgreSQL.",
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    snapshot = read_legacy_snapshot(
        args.source,
        source_timezone=args.source_timezone,
    )
    if args.dry_run:
        report = dry_run_report(snapshot)
    else:
        if not args.target_url:
            raise SystemExit("--target-url is required unless --dry-run is used")
        report = await migrate_snapshot(snapshot, target_url=args.target_url)

    print(
        json.dumps(
            {
                "dry_run": report.dry_run,
                "counts": report.counts,
                "warnings": report.warnings,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def main() -> int:
    args = _parser().parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
