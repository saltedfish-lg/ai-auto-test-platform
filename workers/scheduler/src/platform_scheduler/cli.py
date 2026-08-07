"""Scheduler CLI with graceful signal-driven shutdown."""

from __future__ import annotations

import argparse
import asyncio
import json
import signal
from contextlib import suppress

from platform_observability import configure_logging

from platform_scheduler.application import SchedulerApplication
from platform_scheduler.config import SchedulerSettings


async def _run(settings: SchedulerSettings, check_only: bool) -> None:
    application = SchedulerApplication(settings)
    await application.start()
    if check_only:
        await application.stop()
        print(json.dumps({"service": settings.service_name, "status": "ready"}))
        return
    stop_requested = asyncio.Event()
    loop = asyncio.get_running_loop()
    for handled_signal in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(handled_signal, stop_requested.set)
    try:
        await stop_requested.wait()
    finally:
        await application.stop()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    settings = SchedulerSettings()
    configure_logging(settings.log_level)
    try:
        asyncio.run(_run(settings, args.check))
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
