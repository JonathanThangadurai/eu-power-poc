"""Orchestrates one ingestion run: fetch -> normalize -> upsert -> quality checks -> record run."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import httpx

from app import config, db
from app.energyzero_client import EnergyZeroClientError, fetch
from app.monitoring import run_all_checks
from app.transform import normalize_rows

logger = logging.getLogger("ingest")


async def run_ingest(start: datetime, end: datetime, country: str = config.COUNTRY_LABEL) -> dict:
    started_at = datetime.now(UTC)

    try:
        result = await fetch(start, end)
    except (EnergyZeroClientError, httpx.HTTPError) as exc:
        logger.error("EnergyZero fetch failed for %s-%s: %s", start, end, exc)
        db.insert_pipeline_run(
            started_at=started_at,
            status="failure",
            finished_at=datetime.now(UTC),
            rows_loaded=0,
            error_message=str(exc),
        )
        return {"status": "failure", "error": str(exc)}

    hours = normalize_rows(result.rows, country)

    # An empty result is only a fault if we expected published data (yesterday/today).
    # Querying a future, not-yet-published day legitimately returns no rows.
    if not hours and end <= datetime.now(UTC):
        error = "EnergyZero returned no rows for a window that should already be published"
        logger.error(error)
        db.insert_pipeline_run(
            started_at=started_at,
            status="failure",
            finished_at=datetime.now(UTC),
            rows_loaded=0,
            source_http_status=result.http_status,
            error_message=error,
        )
        return {"status": "failure", "error": error}

    rows_loaded = db.upsert_prices(hours)
    latest = db.max_hour_start(country)
    checks = run_all_checks(hours, latest)

    status = "success" if checks["all_passed"] else "failure"
    db.insert_pipeline_run(
        started_at=started_at,
        status=status,
        finished_at=datetime.now(UTC),
        rows_loaded=rows_loaded,
        source_http_status=result.http_status,
        checks=checks,
    )
    return {"status": status, "rows_loaded": rows_loaded, "checks": checks}


async def ingest_latest() -> dict:
    """Pull yesterday through tomorrow - cheap, idempotent, and picks up tomorrow's
    prices the moment EnergyZero publishes them (~15:00 CET)."""
    now = datetime.now(UTC)
    start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = (now + timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    return await run_ingest(start, end)


async def backfill(start: datetime, end: datetime, country: str = config.COUNTRY_LABEL) -> list[dict]:
    """Backfill a date range in daily chunks via the same idempotent upsert path as live ingestion."""
    results = []
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=1), end)
        results.append(await run_ingest(cursor, chunk_end, country))
        cursor = chunk_end
    return results
