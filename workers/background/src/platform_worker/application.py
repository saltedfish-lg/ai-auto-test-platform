"""Background worker process lifecycle only."""

from __future__ import annotations

import logging

from platform_worker.config import WorkerSettings

LOGGER = logging.getLogger(__name__)


class WorkerApplication:
    def __init__(self, settings: WorkerSettings) -> None:
        self.settings = settings
        self.started = False

    async def start(self) -> None:
        if self.started:
            raise RuntimeError("background worker is already started")
        self.started = True
        LOGGER.info("background worker started", extra={"service": self.settings.service_name})

    async def stop(self) -> None:
        if not self.started:
            return
        LOGGER.info("background worker stopped", extra={"service": self.settings.service_name})
        self.started = False
