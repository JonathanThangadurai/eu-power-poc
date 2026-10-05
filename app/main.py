import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import db, scheduler
from app.api.routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_schema()
    scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(
    title="EU Power POC (NL day-ahead prices)",
    description=(
        "Proof of concept: live NL day-ahead electricity prices via EnergyZero's public API. "
        "Companion to the US Power POC (CAISO) - same architecture, swapped data source. "
        "Data courtesy of EnergyZero (api.energyzero.nl)."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)
