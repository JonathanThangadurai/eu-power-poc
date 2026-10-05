import os

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/eupower"
)

ENERGYZERO_BASE_URL = os.environ.get("ENERGYZERO_BASE_URL", "https://api.energyzero.nl/v1/energyprices")
COUNTRY_LABEL = os.environ.get("COUNTRY_LABEL", "NL")
USAGE_TYPE = os.environ.get("USAGE_TYPE", "1")  # 1 = electricity

# Hourly: catches next-day prices as soon as EnergyZero publishes them.
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", str(60 * 60)))

FRESHNESS_THRESHOLD_MINUTES = int(os.environ.get("FRESHNESS_THRESHOLD_MINUTES", str(36 * 60)))

HTTP_TIMEOUT_SECONDS = float(os.environ.get("HTTP_TIMEOUT_SECONDS", "30"))
RETRY_BACKOFF_SECONDS = float(os.environ.get("RETRY_BACKOFF_SECONDS", "2"))

DISABLE_SCHEDULER = os.environ.get("DISABLE_SCHEDULER", "false").lower() == "true"
