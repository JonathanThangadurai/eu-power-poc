"""raw/quarantine zones and a mart view

Same layering added to the companion us-power-poc repo:
  - raw_prices: the untouched EnergyZero response, once per pipeline_runs row.
  - quarantine_prices: a batch that fails a data-quality check lands here instead
    of (the prior behavior) being written into `prices` before the checks had
    even run.
  - mart_daily_summary: daily avg/min/max/stddev, a view other consumers read
    instead of recomputing aggregates inline.

Purely additive - safe to run with zero coordination with a deploy.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-07

"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

UPGRADE_SQL = """
CREATE TABLE IF NOT EXISTS raw_prices (
    id                SERIAL PRIMARY KEY,
    pipeline_run_id   INTEGER REFERENCES pipeline_runs(id),
    fetched_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    raw_payload       JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_raw_prices_run ON raw_prices (pipeline_run_id);

CREATE TABLE IF NOT EXISTS quarantine_prices (
    id                           SERIAL PRIMARY KEY,
    pipeline_run_id              INTEGER REFERENCES pipeline_runs(id),
    country                      TEXT,
    hour_start_utc                TIMESTAMPTZ,
    price_excl_vat_eur_per_kwh    DOUBLE PRECISION,
    price_incl_vat_eur_per_kwh    DOUBLE PRECISION,
    quarantined_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    reason                        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_quarantine_prices_run ON quarantine_prices (pipeline_run_id);

CREATE OR REPLACE VIEW mart_daily_summary AS
SELECT
    country,
    date_trunc('day', hour_start_utc) AS day_utc,
    avg(price_excl_vat_eur_per_kwh) AS avg_price,
    min(price_excl_vat_eur_per_kwh) AS min_price,
    max(price_excl_vat_eur_per_kwh) AS max_price,
    stddev_pop(price_excl_vat_eur_per_kwh) AS stddev_price,
    count(*) AS hour_count
FROM prices
WHERE price_excl_vat_eur_per_kwh IS NOT NULL
GROUP BY country, date_trunc('day', hour_start_utc);
"""

DOWNGRADE_SQL = """
DROP VIEW IF EXISTS mart_daily_summary;
DROP TABLE IF EXISTS quarantine_prices;
DROP TABLE IF EXISTS raw_prices;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
