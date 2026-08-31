"""Runner Foundation runtime: registration, capability report, and heartbeat only."""

from __future__ import annotations

import asyncio
import importlib.metadata
import logging
import os
import platform
import uuid
from collections.abc import Awaitable, Callable
from contextlib import suppress

from platform_runner.config import RunnerSettings
from platform_runner.credentials import AgentCredentialStore, StoredAgentIdentity
from platform_runner.transport import (
    HttpPlatformTransport,
    PlatformTransportError,
    RegistrationResult,
)

LOGGER = logging.getLogger(__name__)


class RunnerApplication:
    def __init__(
        self,
        settings: RunnerSettings,
        transport: HttpPlatformTransport | None = None,
        credential_store: AgentCredentialStore | None = None,
        capability_probe: Callable[[], Awaitable[list[dict[str, object]]]] | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.settings = settings
        self.transport = transport or HttpPlatformTransport(str(settings.platform_url))
        self.credential_store = credential_store or AgentCredentialStore(
            settings.work_dir / "agent-identity.json"
        )
        self.capability_probe = capability_probe or self._capabilities
        self._sleep = sleep
        self.started = False
        self.identity: StoredAgentIdentity | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None

    async def start(self, *, runtime_enabled: bool = False) -> None:
        if self.started:
            raise RuntimeError("runner agent is already started")
        self.settings.work_dir.mkdir(parents=True, exist_ok=True)
        self.started = True
        LOGGER.info("runner agent started", extra={"service": self.settings.service_name})
        if not runtime_enabled:
            return
        capabilities = await self.capability_probe()
        self.identity = self.credential_store.load()
        if self.identity is None:
            enrollment = self.settings.enrollment_credential
            if enrollment is None:
                self.started = False
                raise RuntimeError(
                    "Runner enrollment credential or stored Agent identity is required"
                )
            registered = await self._register_with_retry(
                enrollment.get_secret_value(), capabilities
            )
            self.identity = StoredAgentIdentity(
                registered.runner_id, registered.agent_token, registered.token_version
            )
            self.credential_store.save(self.identity)
        await self.transport.report_capabilities(
            self.identity.runner_id, self.identity.agent_token, capabilities
        )
        await self.transport.heartbeat(
            self.identity.runner_id,
            self.identity.agent_token,
            self._agent_version(),
            self._runtime_metadata(),
            capabilities,
        )
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self) -> None:
        if not self.started:
            return
        if self._heartbeat_task is not None:
            if not self._heartbeat_task.done():
                self._heartbeat_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await self._heartbeat_task
            self._heartbeat_task = None
        LOGGER.info("runner agent stopped", extra={"service": self.settings.service_name})
        self.started = False

    async def _heartbeat_loop(self) -> None:
        retry_delay = 1.0
        while True:
            await self._sleep(self.settings.heartbeat_interval_seconds)
            identity = self.identity
            if identity is None:
                raise RuntimeError("Runner Agent identity disappeared")
            capabilities = await self.capability_probe()
            try:
                await self.transport.heartbeat(
                    identity.runner_id,
                    identity.agent_token,
                    self._agent_version(),
                    self._runtime_metadata(),
                    capabilities,
                )
                retry_delay = 1.0
            except PlatformTransportError as error:
                if error.status in {401, 403}:
                    raise RuntimeError(
                        "Runner Agent authentication was rejected; import the current token"
                    ) from error
                LOGGER.warning(
                    "runner heartbeat failed; retrying",
                    extra={"status": error.status, "code": error.code},
                )
                await self._sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30.0)

    async def wait_for_runtime_failure(self) -> None:
        task = self._heartbeat_task
        if task is None:
            raise RuntimeError("Runner Agent heartbeat supervision is not active")
        await task
        raise RuntimeError("Runner Agent heartbeat task stopped unexpectedly")

    async def _register_with_retry(
        self, enrollment_credential: str, capabilities: list[dict[str, object]]
    ) -> RegistrationResult:
        retry_delay = 1.0
        while True:
            try:
                return await self.transport.register(
                    enrollment_credential,
                    self._machine_fingerprint(),
                    self._agent_version(),
                    self._runtime_metadata(),
                    capabilities,
                )
            except PlatformTransportError as error:
                if error.status is not None and error.status < 500:
                    raise
                LOGGER.warning(
                    "runner registration delivery failed; retrying idempotently",
                    extra={"status": error.status, "code": error.code},
                )
                await self._sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30.0)

    async def _capabilities(self) -> list[dict[str, object]]:
        capabilities: dict[str, dict[str, object]] = {
            "AGENT_VERSION": {
                "capability_code": "AGENT_VERSION",
                "availability_status": "CONFIGURED",
                "observed_version": self._agent_version(),
                "observed_metadata": None,
            },
            "PLAYWRIGHT_VERSION": {
                "capability_code": "PLAYWRIGHT_VERSION",
                "availability_status": "CONFIGURED",
                "observed_version": _package_version("playwright"),
                "observed_metadata": None,
            },
        }
        for code in self.settings.declared_capabilities:
            capabilities[code] = {
                "capability_code": code,
                "availability_status": "CONFIGURED",
                "observed_version": None,
                "observed_metadata": None,
            }
        return list(capabilities.values())

    @staticmethod
    def _agent_version() -> str:
        return _package_version("platform-runner")

    @staticmethod
    def _machine_fingerprint() -> str:
        material = f"{platform.system()}|{platform.machine()}|{platform.node()}|{uuid.getnode()}"
        return material

    @staticmethod
    def _runtime_metadata() -> dict[str, object]:
        return {
            "os": platform.system(),
            "os_release": platform.release(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "process_id": os.getpid(),
        }


def _package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"
