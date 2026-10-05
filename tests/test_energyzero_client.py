from datetime import UTC, datetime

import httpx
import pytest
import respx

from app import config
from app.energyzero_client import fetch
from tests.conftest import load_fixture

START = datetime(2026, 10, 5, tzinfo=UTC)
END = datetime(2026, 10, 6, tzinfo=UTC)


def _responder(excl_fixture: str, incl_fixture: str):
    def handler(request: httpx.Request) -> httpx.Response:
        incl_btw = request.url.params.get("inclBtw")
        body = load_fixture(incl_fixture if incl_btw == "true" else excl_fixture)
        return httpx.Response(200, json=body)

    return handler


@pytest.mark.asyncio
@respx.mock
async def test_fetch_parses_recorded_response_both_vat_variants():
    respx.get(config.ENERGYZERO_BASE_URL).mock(
        side_effect=_responder("energyzero_excl_vat.json", "energyzero_incl_vat.json")
    )

    result = await fetch(START, END)

    assert result.http_status == 200
    assert len(result.rows) == 24  # one calendar day, hourly
    first = result.rows[0]
    assert first["price_excl_vat_eur_per_kwh"] < first["price_incl_vat_eur_per_kwh"]


@pytest.mark.asyncio
@respx.mock
async def test_fetch_returns_empty_rows_for_unpublished_future_date():
    """A future date EnergyZero hasn't published yet is a legitimate empty answer, not an error."""
    respx.get(config.ENERGYZERO_BASE_URL).mock(
        side_effect=_responder("energyzero_empty_future.json", "energyzero_empty_future.json")
    )

    result = await fetch(datetime(2026, 10, 20, tzinfo=UTC), datetime(2026, 10, 21, tzinfo=UTC))

    assert result.rows == []
