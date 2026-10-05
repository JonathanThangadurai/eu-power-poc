"""Normalize EnergyZero's rows into typed price records. No pivoting needed -
EnergyZero already returns one row per hour with the price, unlike CAISO's
one-row-per-price-component CSV."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class PriceHour:
    country: str
    hour_start_utc: datetime
    price_excl_vat_eur_per_kwh: float
    price_incl_vat_eur_per_kwh: float | None


def normalize_rows(rows: list[dict], country: str) -> list[PriceHour]:
    hours = [
        PriceHour(
            country=country,
            hour_start_utc=datetime.fromisoformat(r["reading_date_utc"].replace("Z", "+00:00")),
            price_excl_vat_eur_per_kwh=float(r["price_excl_vat_eur_per_kwh"]),
            price_incl_vat_eur_per_kwh=(
                float(r["price_incl_vat_eur_per_kwh"])
                if r["price_incl_vat_eur_per_kwh"] is not None
                else None
            ),
        )
        for r in rows
    ]
    hours.sort(key=lambda h: h.hour_start_utc)
    return hours
