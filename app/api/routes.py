from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query

from app import config, db
from app.models import PipelineStatus, PriceRow

router = APIRouter()


@router.get("/health")
def health():
    try:
        db.max_hour_start(config.COUNTRY_LABEL)
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "ok" if db_ok else "unreachable",
        "country": config.COUNTRY_LABEL,
        "time": datetime.now(UTC),
    }


@router.get("/prices", response_model=list[PriceRow])
def get_prices(
    country: str = Query(config.COUNTRY_LABEL),
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
):
    return db.query_prices(country, start, end, limit, offset)


@router.get("/price/current")
def get_current_price(country: str = Query(config.COUNTRY_LABEL)):
    """The single price covering right now - meant for other services (e.g. a REC
    marketplace) to consume as 'the current market price', not for dashboards."""
    row = db.current_price(country, datetime.now(UTC))
    if row is None:
        raise HTTPException(status_code=503, detail="no current price available")
    return row


@router.get("/pipeline/status", response_model=PipelineStatus)
def pipeline_status():
    latest = db.latest_pipeline_run()
    recent = db.recent_pipeline_runs(10)
    return {"latest_run": latest, "recent_runs": recent}


@router.get("/mart/daily-summary")
def mart_daily_summary(
    country: str | None = None,
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
):
    return db.query_mart_daily_summary(country, limit, offset)
