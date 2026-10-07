"""A batch that fails a data-quality check must land in quarantine_prices, not prices."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from app import config, db
from app.ingest import run_ingest

COUNTRY = "ZZ-TEST-QUARANTINE"


def _responder(prices: list[dict]):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"Prices": prices})

    return handler


@pytest.mark.asyncio
@respx.mock
async def test_duplicate_batch_is_quarantined_not_loaded_into_prices():
    hour = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(hours=3)
    reading = hour.strftime("%Y-%m-%dT%H:%M:%SZ")
    # Same reading twice - duplicate_keys must catch this.
    prices = [{"readingDate": reading, "price": 0.10}, {"readingDate": reading, "price": 0.11}]
    respx.get(config.ENERGYZERO_BASE_URL).mock(side_effect=_responder(prices))

    result = await run_ingest(hour, hour + timedelta(hours=1), country=COUNTRY)

    assert result["status"] == "failure"
    assert result["rows_loaded"] == 0
    dup_check = next(c for c in result["checks"]["checks"] if c["name"] == "duplicate_keys")
    assert dup_check["passed"] is False

    with db.get_cursor() as cur:
        cur.execute(
            "SELECT count(*) AS n FROM prices WHERE country=%s AND hour_start_utc=%s", (COUNTRY, hour)
        )
        assert cur.fetchone()["n"] == 0, "failing batch must not reach the prices table"

        cur.execute(
            "SELECT count(*) AS n FROM quarantine_prices WHERE country=%s AND hour_start_utc=%s",
            (COUNTRY, hour),
        )
        assert cur.fetchone()["n"] >= 2, "both rows of the failing batch should be quarantined"

        cur.execute("SELECT status, rows_loaded FROM pipeline_runs ORDER BY id DESC LIMIT 1")
        run_row = cur.fetchone()
        assert run_row["status"] == "failure"
        assert run_row["rows_loaded"] == 0

        cur.execute("SELECT count(*) AS n FROM raw_prices")
        assert cur.fetchone()["n"] >= 1, "raw payload should be recorded even for a failing run"
