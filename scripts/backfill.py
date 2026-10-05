"""CLI backfill command.

Usage:
    python -m scripts.backfill --start 2026-09-01T00:00:00+00:00 --end 2026-09-08T00:00:00+00:00
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime

from app import db
from app.ingest import backfill


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill NL day-ahead prices.")
    parser.add_argument("--start", required=True, help="ISO 8601 UTC, e.g. 2026-09-01T00:00:00+00:00")
    parser.add_argument("--end", required=True, help="ISO 8601 UTC")
    parser.add_argument("--country", default=None)
    args = parser.parse_args()

    start = datetime.fromisoformat(args.start)
    end = datetime.fromisoformat(args.end)

    db.init_schema()
    kwargs = {"country": args.country} if args.country else {}
    results = asyncio.run(backfill(start, end, **kwargs))
    for r in results:
        print(r)


if __name__ == "__main__":
    main()
