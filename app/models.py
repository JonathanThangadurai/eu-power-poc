from datetime import datetime

from pydantic import BaseModel


class PriceRow(BaseModel):
    country: str
    hour_start_utc: datetime
    price_excl_vat_eur_per_kwh: float | None
    price_incl_vat_eur_per_kwh: float | None


class PipelineRun(BaseModel):
    id: int
    started_at: datetime
    finished_at: datetime | None
    status: str
    rows_loaded: int
    source_http_status: int | None
    error_message: str | None
    checks: dict | None


class PipelineStatus(BaseModel):
    latest_run: PipelineRun | None
    recent_runs: list[PipelineRun]
