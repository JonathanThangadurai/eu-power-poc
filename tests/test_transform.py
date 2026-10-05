from app.transform import normalize_rows
from tests.conftest import load_fixture


def _build_client_rows() -> list[dict]:
    excl = load_fixture("energyzero_excl_vat.json")["Prices"]
    incl_by_time = {p["readingDate"]: p["price"] for p in load_fixture("energyzero_incl_vat.json")["Prices"]}
    return [
        {
            "reading_date_utc": p["readingDate"],
            "price_excl_vat_eur_per_kwh": p["price"],
            "price_incl_vat_eur_per_kwh": incl_by_time.get(p["readingDate"]),
        }
        for p in excl
    ]


def test_normalize_rows_produces_24_sorted_hourly_rows():
    hours = normalize_rows(_build_client_rows(), "NL")

    assert len(hours) == 24
    for h in hours:
        assert h.country == "NL"
        assert h.price_excl_vat_eur_per_kwh is not None
        assert h.price_incl_vat_eur_per_kwh is not None
        # VAT-inclusive price should never be cheaper than excl-VAT
        assert h.price_incl_vat_eur_per_kwh >= h.price_excl_vat_eur_per_kwh

    deltas = {
        (b.hour_start_utc - a.hour_start_utc).total_seconds() for a, b in zip(hours, hours[1:], strict=False)
    }
    assert deltas == {3600.0}


def test_normalize_rows_handles_empty_input():
    assert normalize_rows([], "NL") == []
