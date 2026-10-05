"""Three data-quality checks run after every load. Results feed /pipeline/status."""

from __future__ import annotations

from datetime import UTC, datetime

from app import config
from app.transform import PriceHour


def check_duplicate_keys(hours: list[PriceHour]) -> dict:
    keys = [(h.country, h.hour_start_utc) for h in hours]
    duplicates = len(keys) - len(set(keys))
    return {"name": "duplicate_keys", "passed": duplicates == 0, "duplicate_count": duplicates}


def check_null_prices(hours: list[PriceHour]) -> dict:
    null_count = sum(1 for h in hours if h.price_excl_vat_eur_per_kwh is None)
    return {
        "name": "null_prices",
        "passed": null_count == 0,
        "null_count": null_count,
        "total": len(hours),
    }


def check_freshness(latest_hour_start_utc: datetime | None, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    threshold_minutes = config.FRESHNESS_THRESHOLD_MINUTES

    if latest_hour_start_utc is None:
        return {
            "name": "freshness",
            "passed": False,
            "age_minutes": None,
            "threshold_minutes": threshold_minutes,
        }

    age_minutes = (now - latest_hour_start_utc).total_seconds() / 60
    return {
        "name": "freshness",
        "passed": age_minutes <= threshold_minutes,
        "age_minutes": round(age_minutes, 1),
        "threshold_minutes": threshold_minutes,
    }


def run_all_checks(hours: list[PriceHour], latest_hour_start_utc: datetime | None) -> dict:
    checks = [
        check_freshness(latest_hour_start_utc),
        check_duplicate_keys(hours),
        check_null_prices(hours),
    ]
    return {"checks": checks, "all_passed": all(c["passed"] for c in checks)}
