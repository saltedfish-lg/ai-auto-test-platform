"""Runner process lifecycle only; registration and execution are intentionally absent."""

from __future__ import annotations

import logging

from platform_runner.config import RunnerSettings

LOGGER = logging.getLogger(__name__)


class RunnerApplication:
    def __init__(self, settings: RunnerSettings) -> None:
        self.settings = settings
        self.started = False

    async def start(self) -> None:
        if self.started:
            raise RuntimeError("runner agent is already started")
        self.started = True
        LOGGER.info("runner agent started", extra={"service": self.settings.service_name})

    async def stop(self) -> None:
        if not self.started:
            return
        LOGGER.info("runner agent stopped", extra={"service": self.settings.service_name})
        self.started = False
