"""Runner Agent CLI with graceful signal-driven shutdown."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import signal
from contextlib import suppress

from platform_observability import configure_logging

from platform_runner.application import RunnerApplication
from platform_runner.config import RunnerSettings
from platform_runner.credentials import AgentCredentialStore, StoredAgentIdentity


async def _run(settings: RunnerSettings, check_only: bool) -> None:
    application = RunnerApplication(settings)
    await application.start(runtime_enabled=not check_only)
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
        stop_waiter = asyncio.create_task(stop_requested.wait())
        failure_waiter = asyncio.create_task(application.wait_for_runtime_failure())
        done, pending = await asyncio.wait(
            {stop_waiter, failure_waiter}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        if failure_waiter in done:
            await failure_waiter
    finally:
        await application.stop()


def _install_token(settings: RunnerSettings, runner_id: str, token_version: int) -> None:
    token = getpass.getpass("Runner Agent token: ").strip()
    if (
        len(runner_id) != 26
        or not token.startswith("rat_")
        or len(token) < 32
        or token_version < 1
    ):
        raise ValueError("A valid Runner ID and opaque rat_ Agent token are required")
    store = AgentCredentialStore(settings.work_dir / "agent-identity.json")
    existing = store.load()
    if existing is not None and existing.runner_id != runner_id:
        raise ValueError("The credential store belongs to a different Runner")
    if existing is not None and token_version <= existing.token_version:
        raise ValueError("The imported token version must be newer than the stored version")
    store.save(StoredAgentIdentity(runner_id, token, token_version))
    print(json.dumps({"runner_id": runner_id, "token_version": token_version, "status": "saved"}))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--install-token", action="store_true")
    parser.add_argument("--runner-id")
    parser.add_argument("--token-version", type=int)
    args = parser.parse_args()
    settings = RunnerSettings()
    configure_logging(settings.log_level)
    if args.install_token:
        if args.check or args.runner_id is None or args.token_version is None:
            parser.error("--install-token requires --runner-id and --token-version")
        _install_token(settings, args.runner_id, args.token_version)
        return 0
    try:
        asyncio.run(_run(settings, args.check))
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
