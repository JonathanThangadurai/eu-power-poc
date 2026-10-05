-- EU power POC schema (NL day-ahead prices via EnergyZero). Plain SQL, no migration framework.

CREATE TABLE IF NOT EXISTS prices (
    country                     TEXT NOT NULL,
    hour_start_utc               TIMESTAMPTZ NOT NULL,
    price_excl_vat_eur_per_kwh   DOUBLE PRECISION,
    price_incl_vat_eur_per_kwh   DOUBLE PRECISION,
    raw_payload                  JSONB,
    ingested_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (country, hour_start_utc)
);

CREATE INDEX IF NOT EXISTS idx_prices_time ON prices (hour_start_utc);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                   SERIAL PRIMARY KEY,
    started_at           TIMESTAMPTZ NOT NULL,
    finished_at          TIMESTAMPTZ,
    status               TEXT NOT NULL CHECK (status IN ('running', 'success', 'failure')),
    rows_loaded          INTEGER NOT NULL DEFAULT 0,
    source_http_status   INTEGER,
    error_message        TEXT,
    checks               JSONB
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started ON pipeline_runs (started_at DESC);
