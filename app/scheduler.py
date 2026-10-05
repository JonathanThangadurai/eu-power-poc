"""Scheduler running inside the app process, same pattern as the CAISO POC."""

from __future__ import annotations

import asyncio
import logging

from app import config
from app.ingest import ingest_latest

logger = logging.getLogger("scheduler")

_tasks: list[asyncio.Task] = []


async def _poll_loop() -> None:
    while True:
        try:
            await ingest_latest()
        except Exception:  # noqa: BLE001 - never let the loop die
            logger.exception("ingest loop iteration failed")
        await asyncio.sleep(config.POLL_SECONDS)


def start() -> None:
    if config.DISABLE_SCHEDULER:
        logger.info("Scheduler disabled via DISABLE_SCHEDULER")
        return
    _tasks.append(asyncio.create_task(_poll_loop()))
    logger.info("Scheduler started: polling every %ss", config.POLL_SECONDS)


def stop() -> None:
    for task in _tasks:
        task.cancel()
    _tasks.clear()
