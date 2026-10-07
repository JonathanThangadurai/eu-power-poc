from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app import config
from app.transform import PriceHour

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(config.DATABASE_URL, min_size=1, max_size=5, open=True)
    return _pool


@contextmanager
def get_cursor():
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            yield cur


def init_schema() -> None:
    """Brings the schema up to the latest Alembic revision. Safe on every startup:
    a fresh database gets the full history; an already-current one (its tables
    predate Alembic's adoption here) has revision 0001 recorded as satisfied since
    it's written as CREATE TABLE IF NOT EXISTS, then later revisions run for real."""
    from alembic import command
    from alembic.config import Config

    project_root = Path(__file__).resolve().parent.parent
    cfg = Config(str(project_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(project_root / "migrations"))
    command.upgrade(cfg, "head")


def upsert_prices(hours: list[PriceHour], raw_payload: dict | None = None) -> int:
    if not hours:
        return 0
    raw_json = json.dumps(raw_payload) if raw_payload is not None else None
    with get_cursor() as cur:
        for h in hours:
            cur.execute(
                """
                INSERT INTO prices (country, hour_start_utc, price_excl_vat_eur_per_kwh,
                                     price_incl_vat_eur_per_kwh, raw_payload)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (country, hour_start_utc) DO UPDATE SET
                    price_excl_vat_eur_per_kwh = EXCLUDED.price_excl_vat_eur_per_kwh,
                    price_incl_vat_eur_per_kwh = EXCLUDED.price_incl_vat_eur_per_kwh,
                    raw_payload = EXCLUDED.raw_payload,
                    ingested_at = now()
                """,
                (
                    h.country,
                    h.hour_start_utc,
                    h.price_excl_vat_eur_per_kwh,
                    h.price_incl_vat_eur_per_kwh,
                    raw_json,
                ),
            )
    return len(hours)


def insert_raw_price(pipeline_run_id: int, raw_payload: dict) -> None:
    """The raw zone: the untouched EnergyZero response, kept once per run rather
    than duplicated inline on every conformed row."""
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO raw_prices (pipeline_run_id, raw_payload) VALUES (%s, %s)",
            (pipeline_run_id, json.dumps(raw_payload)),
        )


def insert_quarantine_batch(pipeline_run_id: int, hours: list[PriceHour], reason: str) -> int:
    """A batch that failed a data-quality check lands here instead of `prices`."""
    if not hours:
        return 0
    with get_cursor() as cur:
        for h in hours:
            cur.execute(
                """
                INSERT INTO quarantine_prices (pipeline_run_id, country, hour_start_utc,
                                                price_excl_vat_eur_per_kwh,
                                                price_incl_vat_eur_per_kwh, reason)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    pipeline_run_id,
                    h.country,
                    h.hour_start_utc,
                    h.price_excl_vat_eur_per_kwh,
                    h.price_incl_vat_eur_per_kwh,
                    reason,
                ),
            )
    return len(hours)


def query_mart_daily_summary(country: str | None, limit: int, offset: int) -> list[dict]:
    clauses = []
    params: list = []
    if country:
        clauses.append("country = %s")
        params.append(country)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT country, day_utc, avg_price, min_price, max_price, stddev_price, hour_count
        FROM mart_daily_summary
        {where}
        ORDER BY day_utc DESC
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])
    with get_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def query_prices(
    country: str | None, start: datetime | None, end: datetime | None, limit: int, offset: int
) -> list[dict]:
    clauses = []
    params: list = []
    if country:
        clauses.append("country = %s")
        params.append(country)
    if start:
        clauses.append("hour_start_utc >= %s")
        params.append(start)
    if end:
        clauses.append("hour_start_utc < %s")
        params.append(end)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT country, hour_start_utc, price_excl_vat_eur_per_kwh, price_incl_vat_eur_per_kwh
        FROM prices
        {where}
        ORDER BY hour_start_utc DESC
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])
    with get_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def current_price(country: str, now: datetime) -> dict | None:
    """The price row for the hour containing `now` - what a live consumer should treat as 'current'."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT country, hour_start_utc, price_excl_vat_eur_per_kwh, price_incl_vat_eur_per_kwh
            FROM prices
            WHERE country = %s AND hour_start_utc <= %s
            ORDER BY hour_start_utc DESC
            LIMIT 1
            """,
            (country, now),
        )
        return cur.fetchone()


def insert_pipeline_run(started_at: datetime, status: str, **kwargs) -> int:
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO pipeline_runs (started_at, finished_at, status, rows_loaded,
                                        source_http_status, error_message, checks)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                started_at,
                kwargs.get("finished_at"),
                status,
                kwargs.get("rows_loaded", 0),
                kwargs.get("source_http_status"),
                kwargs.get("error_message"),
                json.dumps(kwargs["checks"]) if kwargs.get("checks") is not None else None,
            ),
        )
        return cur.fetchone()["id"]


def latest_pipeline_run() -> dict | None:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 1")
        return cur.fetchone()


def recent_pipeline_runs(limit: int = 10) -> list[dict]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT %s", (limit,))
        return cur.fetchall()


def max_hour_start(country: str) -> datetime | None:
    with get_cursor() as cur:
        cur.execute("SELECT max(hour_start_utc) AS m FROM prices WHERE country = %s", (country,))
        row = cur.fetchone()
        return row["m"] if row else None
