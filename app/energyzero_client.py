"""Client for EnergyZero's public day-ahead electricity price API (NL).

Public, anonymous, no API key - https://api.energyzero.nl/v1/energyprices

Unlike CAISO, an empty result here is usually a *legitimate* answer: tomorrow's
day-ahead prices aren't published until ~15:00 CET the day before, so querying
a future date before publication correctly returns `"Prices": []` with HTTP 200.
The caller decides whether an empty result for a given window is expected
(far future) or a fault (today/yesterday, which must already be published).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import httpx

from app import config

logger = logging.getLogger("energyzero_client")


class EnergyZeroClientError(Exception):
    pass


@dataclass
class EnergyZeroResult:
    http_status: int
    raw_json: dict
    rows: list[dict]  # [{"reading_date_utc": datetime, "price_eur_per_kwh": float}, ...]


async def _fetch_one(start: datetime, end: datetime, incl_btw: bool) -> dict:
    params = {
        "fromDate": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "tillDate": end.strftime("%Y-%m-%dT%H:%M:%S.999Z"),
        "interval": "4",  # hourly
        "usageType": config.USAGE_TYPE,
        "inclBtw": "true" if incl_btw else "false",
    }
    async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT_SECONDS) as client:
        resp = await client.get(config.ENERGYZERO_BASE_URL, params=params)
    resp.raise_for_status()
    return resp.json()


async def fetch(start: datetime, end: datetime, max_attempts: int = 2) -> EnergyZeroResult:
    """Fetch NL day-ahead hourly prices for [start, end), both incl. and excl. VAT."""
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            excl = await _fetch_one(start, end, incl_btw=False)
            incl = await _fetch_one(start, end, incl_btw=True)
            break
        except httpx.HTTPError as exc:
            last_exc = exc
            logger.warning("EnergyZero fetch attempt %d/%d failed: %s", attempt, max_attempts, exc)
            if attempt < max_attempts:
                import asyncio

                await asyncio.sleep(config.RETRY_BACKOFF_SECONDS * attempt)
    else:
        raise EnergyZeroClientError(f"EnergyZero fetch failed after {max_attempts} attempts: {last_exc}")

    incl_by_time = {p["readingDate"]: p["price"] for p in incl["Prices"]}
    rows = [
        {
            "reading_date_utc": p["readingDate"],
            "price_excl_vat_eur_per_kwh": p["price"],
            "price_incl_vat_eur_per_kwh": incl_by_time.get(p["readingDate"]),
        }
        for p in excl["Prices"]
    ]
    return EnergyZeroResult(http_status=200, raw_json={"excl": excl, "incl": incl}, rows=rows)
