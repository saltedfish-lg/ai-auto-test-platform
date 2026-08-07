"""Scheduler process lifecycle only."""

from __future__ import annotations

import logging

from platform_scheduler.config import SchedulerSettings

LOGGER = logging.getLogger(__name__)


class SchedulerApplication:
    def __init__(self, settings: SchedulerSettings) -> None:
        self.settings = settings
        self.started = False

    async def start(self) -> None:
        if self.started:
            raise RuntimeError("scheduler is already started")
        self.started = True
        LOGGER.info("scheduler process started", extra={"service": self.settings.service_name})

    async def stop(self) -> None:
        if not self.started:
            return
        LOGGER.info("scheduler process stopped", extra={"service": self.settings.service_name})
        self.started = False
